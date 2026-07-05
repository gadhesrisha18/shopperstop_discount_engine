"""
Slab (progressive/tiered) discount.

This is the foundation requirement: discount rate increases progressively
as the cart value crosses configured slab boundaries — similar to income
tax slabs. Each portion of the cart value is discounted at the rate of the
slab it falls into, NOT a single flat rate applied to the whole cart.
"""
from decimal import Decimal
from app.discounts.base import DiscountStrategy, DiscountContext, DiscountResult


class SlabDiscount(DiscountStrategy):
    discount_type = "SLAB"

    def __init__(self, discount_id: str, name: str, slabs: list[dict],
                 priority: int = 10, stackable: bool = True, config: dict | None = None):
        """
        slabs: list of {"min": Decimal, "max": Decimal|None, "rate": Decimal}
               sorted ascending by "min". "max": None means unbounded (Above X).
               rate is a fraction, e.g. 0.10 for 10%.
        """
        super().__init__(discount_id, name, priority, stackable, config)
        self.slabs = sorted(slabs, key=lambda s: s["min"])

    def is_applicable(self, context: DiscountContext) -> bool:
        return context.cart_total > 0

    def calculate(self, context: DiscountContext, running_total: Decimal) -> DiscountResult:
        amount_off = self.compute_progressive_discount(context.cart_total)
        # Slab discounts are computed off the original cart_total (not running_total),
        # since slabs represent the base pricing policy, not a stacked coupon.
        amount_off = min(amount_off, running_total)
        return DiscountResult(
            discount_id=self.discount_id,
            discount_name=self.name,
            discount_type=self.discount_type,
            amount_off=amount_off,
            priority=self.priority,
            stacked=self.stackable,
            detail=self._breakdown_text(context.cart_total),
        )

    def compute_progressive_discount(self, cart_total: Decimal) -> Decimal:
        """
        Walk each slab, discount the portion of cart_total that falls within it.

        Example (Regular, 5000/10%/10000/20% slabs) with cart_total=15000:
          0-5000      -> 0%  off 5000  -> 0
          5000-10000  -> 10% off 5000  -> 500
          10000+      -> 20% off 5000  -> 1000
          total discount = 1500  => final = 13500
        """
        total_discount = Decimal("0")
        for slab in self.slabs:
            slab_min = Decimal(str(slab["min"]))
            slab_max = Decimal(str(slab["max"])) if slab["max"] is not None else None
            rate = Decimal(str(slab["rate"]))

            if cart_total <= slab_min:
                continue

            portion_top = cart_total if slab_max is None else min(cart_total, slab_max)
            portion_in_slab = portion_top - slab_min
            if portion_in_slab <= 0:
                continue

            total_discount += portion_in_slab * rate

        return total_discount

    def _breakdown_text(self, cart_total: Decimal) -> str:
        parts = []
        for slab in self.slabs:
            slab_min = Decimal(str(slab["min"]))
            slab_max = Decimal(str(slab["max"])) if slab["max"] is not None else None
            rate = Decimal(str(slab["rate"]))
            if cart_total <= slab_min:
                continue
            portion_top = cart_total if slab_max is None else min(cart_total, slab_max)
            portion = portion_top - slab_min
            if portion <= 0:
                continue
            label = f"₹{slab_min}-{'∞' if slab_max is None else '₹'+str(slab_max)}"
            parts.append(f"{label} @ {rate*100:.0f}% on ₹{portion}")
        return "; ".join(parts)
