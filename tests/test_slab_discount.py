"""Unit tests for progressive slab discount math — the foundation requirement (Part 1)."""
from decimal import Decimal
import pytest
from app.discounts.slab_discount import SlabDiscount
from app.discounts.base import DiscountContext, CartItem

REGULAR_SLABS = [
    {"min": 0, "max": 5000, "rate": 0.0},
    {"min": 5000, "max": 10000, "rate": 0.10},
    {"min": 10000, "max": None, "rate": 0.20},
]

PREMIUM_SLABS = [
    {"min": 0, "max": 5000, "rate": 0.10},
    {"min": 5000, "max": 10000, "rate": 0.20},
    {"min": 10000, "max": None, "rate": 0.30},
]


def make_context(cart_total: Decimal, tier: str = "REGULAR") -> DiscountContext:
    item = CartItem(sku="X", name="X", category="General", unit_price=cart_total, quantity=1)
    return DiscountContext(cart_items=[item], cart_total=cart_total, customer_tier=tier)


class TestRegularSlabs:
    def test_within_first_slab_no_discount(self):
        strategy = SlabDiscount("t1", "Regular", REGULAR_SLABS)
        discount = strategy.compute_progressive_discount(Decimal("5000"))
        assert discount == Decimal("0")

    def test_below_first_slab_boundary(self):
        strategy = SlabDiscount("t1", "Regular", REGULAR_SLABS)
        discount = strategy.compute_progressive_discount(Decimal("3000"))
        assert discount == Decimal("0")

    def test_multi_slab_15000(self):
        """The canonical example from the spec: 15000 -> 13500 final."""
        strategy = SlabDiscount("t1", "Regular", REGULAR_SLABS)
        discount = strategy.compute_progressive_discount(Decimal("15000"))
        assert discount == Decimal("1500")
        assert Decimal("15000") - discount == Decimal("13500")

    def test_exact_slab_boundary_10000(self):
        strategy = SlabDiscount("t1", "Regular", REGULAR_SLABS)
        # First 5000 @ 0%, next 5000 @ 10% = 500
        discount = strategy.compute_progressive_discount(Decimal("10000"))
        assert discount == Decimal("500")

    def test_large_amount_uses_top_slab(self):
        strategy = SlabDiscount("t1", "Regular", REGULAR_SLABS)
        # 0-5000@0 -> 0; 5000-10000@10% -> 500; 10000-50000 (40000)@20% -> 8000
        discount = strategy.compute_progressive_discount(Decimal("50000"))
        assert discount == Decimal("8500")


class TestPremiumSlabs:
    def test_premium_15000(self):
        """Canonical example: Premium, 15000 -> 12000 final."""
        strategy = SlabDiscount("t2", "Premium", PREMIUM_SLABS)
        discount = strategy.compute_progressive_discount(Decimal("15000"))
        assert discount == Decimal("3000")
        assert Decimal("15000") - discount == Decimal("12000")

    def test_premium_gets_discount_even_in_first_slab(self):
        strategy = SlabDiscount("t2", "Premium", PREMIUM_SLABS)
        discount = strategy.compute_progressive_discount(Decimal("2000"))
        assert discount == Decimal("200")  # 10% of 2000


class TestSlabEdgeCases:
    def test_zero_cart_total(self):
        strategy = SlabDiscount("t1", "Regular", REGULAR_SLABS)
        discount = strategy.compute_progressive_discount(Decimal("0"))
        assert discount == Decimal("0")

    def test_calculate_via_strategy_interface(self):
        strategy = SlabDiscount("t1", "Regular", REGULAR_SLABS)
        context = make_context(Decimal("15000"))
        result = strategy.calculate(context, running_total=Decimal("15000"))
        assert result.amount_off == Decimal("1500")
        assert result.discount_type == "SLAB"

    def test_amount_off_never_exceeds_running_total(self):
        """If prior discounts already reduced running_total below the slab discount, cap it."""
        strategy = SlabDiscount("t1", "Regular", REGULAR_SLABS)
        context = make_context(Decimal("15000"))
        result = strategy.calculate(context, running_total=Decimal("100"))
        assert result.amount_off <= Decimal("100")

    def test_is_applicable_false_for_zero_cart(self):
        strategy = SlabDiscount("t1", "Regular", REGULAR_SLABS)
        context = make_context(Decimal("0"))
        assert strategy.is_applicable(context) is False
