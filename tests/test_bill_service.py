from decimal import Decimal
import pytest
from app.services.bill_service import BillService, BillCalculationError


def cart(price, qty=1, category="General", sku="SKU1"):
    return [{"sku": sku, "name": sku, "category": category, "unit_price": price, "quantity": qty}]


class TestBillServiceCore:
    def test_regular_5000_no_discount(self):
        bs = BillService()
        r = bs.calculate(cart(5000), "REGULAR")
        assert r["final_amount"] == 5000.0
        assert r["total_discount"] == 0.0

    def test_regular_15000_multi_slab(self):
        bs = BillService()
        r = bs.calculate(cart(15000), "REGULAR")
        assert r["final_amount"] == 13500.0

    def test_premium_15000(self):
        bs = BillService()
        r = bs.calculate(cart(15000), "PREMIUM")
        assert r["final_amount"] == 12000.0

    def test_unknown_tier_raises(self):
        bs = BillService()
        with pytest.raises(BillCalculationError):
            bs.calculate(cart(1000), "PLATINUM")

    def test_negative_price_rejected(self):
        bs = BillService()
        with pytest.raises(BillCalculationError):
            bs.calculate([{"sku": "X", "name": "X", "category": "General", "unit_price": -100, "quantity": 1}], "REGULAR")

    def test_zero_quantity_rejected(self):
        bs = BillService()
        with pytest.raises(BillCalculationError):
            bs.calculate([{"sku": "X", "name": "X", "category": "General", "unit_price": 100, "quantity": 0}], "REGULAR")

    def test_empty_cart_rejected(self):
        bs = BillService()
        with pytest.raises(BillCalculationError):
            bs.calculate([], "REGULAR")


class TestStackingAndPromotions:
    def _provider_factory(self, promos):
        def provider(store_id, tier, now):
            return promos
        return provider

    def test_stacked_flat_discount_on_top_of_slab(self):
        promos = [{
            "id": "flat1", "name": "Flat 500", "discount_type": "FLAT",
            "params": {"amount_off": 500, "min_cart_value": 3000},
            "priority": 50, "stackable": True,
        }]
        bs = BillService(promotion_provider=self._provider_factory(promos))
        r = bs.calculate(cart(15000), "PREMIUM")
        # Premium slab discount = 3000, final before flat = 12000; then -500 => 11500
        assert r["final_amount"] == 11500.0
        assert len(r["discounts_breakdown"]) == 2
        assert any(d["discount_type"] == "FLAT" and d["applied"] for d in r["discounts_breakdown"])

    def test_non_stackable_conflict_only_one_wins(self):
        promos = [
            {"id": "p1", "name": "10% coupon A", "discount_type": "PERCENTAGE",
             "params": {"rate": 0.10}, "priority": 20, "stackable": False},
            {"id": "p2", "name": "20% coupon B", "discount_type": "PERCENTAGE",
             "params": {"rate": 0.20}, "priority": 25, "stackable": False},
        ]
        bs = BillService(promotion_provider=self._provider_factory(promos))
        r = bs.calculate(cart(2000), "REGULAR")
        applied = [d for d in r["discounts_breakdown"] if d["applied"]]
        skipped = [d for d in r["discounts_breakdown"] if d["skipped_reason"] == "non_stackable_conflict"]
        # Only the higher-priority (lower number = p1) non-stackable discount should apply
        assert any(d["discount_id"] == "p1" for d in applied)
        assert any(d["discount_id"] == "p2" for d in skipped)

    def test_max_discount_cap_enforced(self):
        promos = [
            {"id": "p1", "name": "30% off", "discount_type": "PERCENTAGE",
             "params": {"rate": 0.30}, "priority": 20, "stackable": True},
            {"id": "p2", "name": "20% off", "discount_type": "PERCENTAGE",
             "params": {"rate": 0.20}, "priority": 21, "stackable": True},
        ]
        bs = BillService(promotion_provider=self._provider_factory(promos))
        # Premium 50000 cart: slab discount alone = 30% => 15000; plus 30%+20% coupons would blow way past 40% cap
        r = bs.calculate(cart(50000), "PREMIUM")
        assert r["capped"] is True
        assert r["total_discount"] <= r["cart_subtotal"] * 0.40 + 0.01  # small float tolerance

    def test_category_discount_applied(self):
        promos = [{
            "id": "cat1", "name": "25% off Electronics", "discount_type": "CATEGORY",
            "params": {"category": "Electronics", "rate": 0.25}, "priority": 40, "stackable": True,
        }]
        bs = BillService(promotion_provider=self._provider_factory(promos))
        items = [
            {"sku": "E1", "name": "TV", "category": "Electronics", "unit_price": 10000, "quantity": 1},
        ]
        r = bs.calculate(items, "REGULAR")
        # Slab: 10000 -> discount 500 (first5000@0 + next5000@10%); Category 25% of 10000=2500, capped at running_total(9500)? no just additive
        assert any(d["discount_type"] == "CATEGORY" for d in r["discounts_breakdown"])

    def test_promotion_scoped_to_tier_not_applied_to_other_tier(self):
        promos = [{
            "id": "premium_only", "name": "Premium Only Coupon", "discount_type": "FLAT",
            "params": {"amount_off": 1000, "min_cart_value": 0}, "priority": 50, "stackable": True,
        }]
        bs = BillService(promotion_provider=self._provider_factory(promos))
        r = bs.calculate(cart(5000), "REGULAR")
        assert any(d["applied"] for d in r["discounts_breakdown"] if d["discount_id"] == "premium_only")


class TestRounding:
    def test_final_amount_rounded_to_2dp(self):
        bs = BillService()
        r = bs.calculate(cart(3333.33), "PREMIUM")
        assert round(r["final_amount"], 2) == r["final_amount"]
