from decimal import Decimal
from datetime import datetime, time
from app.discounts.base import DiscountContext, CartItem
from app.discounts.flat_discount import FlatDiscount
from app.discounts.percentage_discount import PercentageDiscount
from app.discounts.category_discount import CategoryDiscount
from app.discounts.bxgy_discount import BuyXGetYDiscount
from app.discounts.time_based_discount import TimeBasedDiscount


def ctx(items, tier="REGULAR", now=None):
    total = sum((i.line_total for i in items), Decimal("0"))
    return DiscountContext(cart_items=items, cart_total=total, customer_tier=tier, now=now or datetime.utcnow())


class TestFlatDiscount:
    def test_applies_above_threshold(self):
        item = CartItem("A", "A", "General", Decimal("4000"), 1)
        c = ctx([item])
        d = FlatDiscount("f1", "500 off 3000", amount_off=Decimal("500"), min_cart_value=Decimal("3000"))
        assert d.is_applicable(c) is True
        result = d.calculate(c, running_total=c.cart_total)
        assert result.amount_off == Decimal("500")

    def test_not_applicable_below_threshold(self):
        item = CartItem("A", "A", "General", Decimal("1000"), 1)
        c = ctx([item])
        d = FlatDiscount("f1", "500 off 3000", amount_off=Decimal("500"), min_cart_value=Decimal("3000"))
        assert d.is_applicable(c) is False

    def test_never_exceeds_running_total(self):
        item = CartItem("A", "A", "General", Decimal("100"), 1)
        c = ctx([item])
        d = FlatDiscount("f1", "500 off 0", amount_off=Decimal("500"), min_cart_value=Decimal("0"))
        result = d.calculate(c, running_total=Decimal("100"))
        assert result.amount_off == Decimal("100")


class TestPercentageDiscount:
    def test_basic_percentage(self):
        item = CartItem("A", "A", "General", Decimal("1000"), 1)
        c = ctx([item])
        d = PercentageDiscount("p1", "15% off", rate=Decimal("0.15"))
        result = d.calculate(c, running_total=Decimal("1000"))
        assert result.amount_off == Decimal("150.00")

    def test_max_cap_applies(self):
        item = CartItem("A", "A", "General", Decimal("100000"), 1)
        c = ctx([item])
        d = PercentageDiscount("p1", "10% coupon", rate=Decimal("0.10"), max_discount_amount=Decimal("2000"))
        result = d.calculate(c, running_total=Decimal("100000"))
        assert result.amount_off == Decimal("2000")


class TestCategoryDiscount:
    def test_only_matching_category_discounted(self):
        electronics = CartItem("E1", "TV", "Electronics", Decimal("10000"), 1)
        apparel = CartItem("A1", "Shirt", "Apparel", Decimal("1000"), 1)
        c = ctx([electronics, apparel])
        d = CategoryDiscount("c1", "25% off Electronics", category="Electronics", rate=Decimal("0.25"))
        result = d.calculate(c, running_total=c.cart_total)
        assert result.amount_off == Decimal("2500.00")

    def test_not_applicable_when_no_matching_items(self):
        apparel = CartItem("A1", "Shirt", "Apparel", Decimal("1000"), 1)
        c = ctx([apparel])
        d = CategoryDiscount("c1", "25% off Electronics", category="Electronics", rate=Decimal("0.25"))
        assert d.is_applicable(c) is False


class TestBuyXGetYDiscount:
    def test_free_unit_granted(self):
        shirts = CartItem("S1", "Shirt", "Apparel", Decimal("500"), 3)  # buy 2 get 1
        c = ctx([shirts])
        d = BuyXGetYDiscount("b1", "B2G1", buy_qty=2, free_qty=1, applies_to_category="Apparel")
        assert d.is_applicable(c) is True
        result = d.calculate(c, running_total=c.cart_total)
        assert result.amount_off == Decimal("500")

    def test_not_enough_quantity(self):
        shirts = CartItem("S1", "Shirt", "Apparel", Decimal("500"), 2)  # need 3 for 1 free
        c = ctx([shirts])
        d = BuyXGetYDiscount("b1", "B2G1", buy_qty=2, free_qty=1, applies_to_category="Apparel")
        assert d.is_applicable(c) is False

    def test_multiple_groups(self):
        shirts = CartItem("S1", "Shirt", "Apparel", Decimal("100"), 6)  # 2 groups of 3 -> 2 free
        c = ctx([shirts])
        d = BuyXGetYDiscount("b1", "B2G1", buy_qty=2, free_qty=1, applies_to_category="Apparel")
        result = d.calculate(c, running_total=c.cart_total)
        assert result.amount_off == Decimal("200")


class TestTimeBasedDiscount:
    def test_applies_within_window(self):
        item = CartItem("A", "A", "General", Decimal("1000"), 1)
        happy_hour_time = datetime(2026, 7, 3, 18, 0)  # 6 PM
        c = ctx([item], now=happy_hour_time)
        d = TimeBasedDiscount("h1", "Happy Hour", rate=Decimal("0.05"), start_time=time(17, 0), end_time=time(20, 0))
        assert d.is_applicable(c) is True
        result = d.calculate(c, running_total=Decimal("1000"))
        assert result.amount_off == Decimal("50.00")

    def test_not_applicable_outside_window(self):
        item = CartItem("A", "A", "General", Decimal("1000"), 1)
        morning = datetime(2026, 7, 3, 9, 0)
        c = ctx([item], now=morning)
        d = TimeBasedDiscount("h1", "Happy Hour", rate=Decimal("0.05"), start_time=time(17, 0), end_time=time(20, 0))
        assert d.is_applicable(c) is False
