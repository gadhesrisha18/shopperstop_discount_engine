"""
BillService orchestrates the discount engine:

1. Build a DiscountContext from the request.
2. Always apply the customer tier's SLAB discount first (base pricing policy).
3. Gather all ACTIVE promotions applicable to this store/tier/time.
4. Sort by priority (ascending = applied first) and run them sequentially,
   each computing its discount off the running total after prior discounts.
5. Non-stackable discounts: if a non-stackable discount has already been
   applied, subsequent non-stackable discounts are skipped (only one
   non-stackable discount wins — the highest-priority one).
6. Enforce the configured max_total_discount_rate cap; if exceeded, the
   total discount is scaled back to the cap and this is reported to the caller.
"""
import json
import uuid
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from app.discounts.base import DiscountContext, CartItem, DiscountResult
from app.discounts.slab_discount import SlabDiscount
from app.discounts.factory import build_strategy
from app.discounts.base import DiscountStrategy

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "discount_rules.json"


def _round(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class BillCalculationError(Exception):
    """Raised for invalid business-rule inputs (e.g. unknown customer tier)."""


class BillService:
    def __init__(self, promotion_provider=None, tier_provider=None):
        """
        promotion_provider: callable(store_id, customer_tier, now) -> list[dict] of active promo configs.
                             If None, only the default config file's tiers are used (no dynamic promotions).
        tier_provider: callable() -> dict[tier_id, {"label", "slabs"}]. If None, falls back to the JSON config.
        """
        self._promotion_provider = promotion_provider
        self._tier_provider = tier_provider
        self._default_config = json.loads(CONFIG_PATH.read_text())

    def _get_tier_slabs(self, customer_tier: str) -> list[dict]:
        if self._tier_provider:
            tiers = self._tier_provider()
            if customer_tier in tiers:
                return tiers[customer_tier]["slabs"]
        tiers = self._default_config["customer_tiers"]
        if customer_tier not in tiers:
            raise BillCalculationError(
                f"Unknown customer_tier '{customer_tier}'. Known tiers: {list(tiers.keys())}"
            )
        return tiers[customer_tier]["slabs"]

    def _get_max_discount_rate(self) -> Decimal:
        return Decimal(str(self._default_config["stacking_rules"]["max_total_discount_rate"]))

    def calculate(self, cart_items_in: list[dict], customer_tier: str,
                   store_id: str | None = None, coupon_codes: list[str] | None = None,
                   now=None, correlation_id: str | None = None) -> dict:
        correlation_id = correlation_id or str(uuid.uuid4())

        if not cart_items_in:
            raise BillCalculationError("cart_items must not be empty")

        cart_items = []
        for item in cart_items_in:
            unit_price = Decimal(str(item["unit_price"]))
            quantity = int(item["quantity"])
            if unit_price <= 0:
                raise BillCalculationError(f"Invalid unit_price for SKU {item.get('sku')}: must be > 0")
            if quantity <= 0:
                raise BillCalculationError(f"Invalid quantity for SKU {item.get('sku')}: must be > 0")
            cart_items.append(CartItem(
                sku=item["sku"], name=item.get("name", item["sku"]),
                category=item.get("category", "GENERAL"),
                unit_price=unit_price, quantity=quantity,
            ))

        cart_total = sum((i.line_total for i in cart_items), Decimal("0"))

        import datetime as _dt
        context = DiscountContext(
            cart_items=cart_items, cart_total=cart_total, customer_tier=customer_tier,
            now=now or _dt.datetime.utcnow(), store_id=store_id, coupon_codes=coupon_codes or [],
        )

        # 1. Base tier slab discount (always evaluated first, priority 0)
        slabs = self._get_tier_slabs(customer_tier)
        tier_slab_strategy = SlabDiscount(
            discount_id=f"TIER_SLAB_{customer_tier}", name=f"{customer_tier} Tier Slab Discount",
            slabs=slabs, priority=0, stackable=True,
        )

        strategies: list[DiscountStrategy] = [tier_slab_strategy]

        # 2. Dynamic promotions (from DB), if a provider was supplied
        if self._promotion_provider:
            promo_configs = self._promotion_provider(store_id, customer_tier, context.now)
            for promo in promo_configs:
                try:
                    strategies.append(build_strategy(promo))
                except ValueError:
                    continue  # unknown discount type — skip defensively rather than fail the whole bill

        strategies.sort(key=lambda s: s.priority)

        breakdown: list[DiscountResult] = []
        skipped: list[dict] = []
        running_total = cart_total
        non_stackable_used = False

        for strategy in strategies:
            if not strategy.is_applicable(context):
                skipped.append({"discount_id": strategy.discount_id, "discount_name": strategy.name,
                                 "discount_type": strategy.discount_type, "reason": "not_applicable"})
                continue
            if not strategy.stackable and non_stackable_used:
                skipped.append({"discount_id": strategy.discount_id, "discount_name": strategy.name,
                                 "discount_type": strategy.discount_type,
                                 "reason": "non_stackable_conflict"})
                continue

            result = strategy.calculate(context, running_total)
            amount_off = max(Decimal("0"), min(result.amount_off, running_total))
            running_total -= amount_off
            breakdown.append(DiscountResult(
                discount_id=result.discount_id, discount_name=result.discount_name,
                discount_type=result.discount_type, amount_off=amount_off,
                priority=result.priority, stacked=result.stacked, detail=result.detail,
            ))
            if not strategy.stackable:
                non_stackable_used = True

        total_discount = cart_total - running_total

        # Enforce max discount cap
        max_rate = self._get_max_discount_rate()
        capped = False
        if cart_total > 0 and (total_discount / cart_total) > max_rate:
            capped = True
            allowed_discount = cart_total * max_rate
            # Scale back each applied discount proportionally so the breakdown still sums correctly
            scale = allowed_discount / total_discount if total_discount > 0 else Decimal("0")
            for r in breakdown:
                r.amount_off = _round(r.amount_off * scale)
            total_discount = sum((r.amount_off for r in breakdown), Decimal("0"))
            running_total = cart_total - total_discount

        final_amount = _round(running_total)
        total_discount = _round(total_discount)
        cart_total = _round(cart_total)

        return {
            "cart_subtotal": float(cart_total),
            "total_discount": float(total_discount),
            "final_amount": float(final_amount),
            "customer_tier": customer_tier,
            "discounts_breakdown": [
                {
                    "discount_id": r.discount_id, "discount_name": r.discount_name,
                    "discount_type": r.discount_type, "amount_off": float(_round(r.amount_off)),
                    "priority": r.priority, "applied": r.amount_off > 0, "detail": r.detail,
                    "skipped_reason": None,
                } for r in breakdown
            ] + [
                {
                    "discount_id": s["discount_id"], "discount_name": s["discount_name"],
                    "discount_type": s["discount_type"], "amount_off": 0.0,
                    "priority": 0, "applied": False, "detail": "", "skipped_reason": s["reason"],
                } for s in skipped
            ],
            "capped": capped,
            "cap_rate": float(max_rate) if capped else None,
            "correlation_id": correlation_id,
        }
