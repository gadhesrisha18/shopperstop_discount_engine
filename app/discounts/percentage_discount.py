from decimal import Decimal
from app.discounts.base import DiscountStrategy, DiscountContext, DiscountResult


class PercentageDiscount(DiscountStrategy):
    """e.g. 15% off entire cart, optionally capped at a max amount."""
    discount_type = "PERCENTAGE"

    def __init__(self, discount_id: str, name: str, rate: Decimal,
                 max_discount_amount: Decimal | None = None,
                 min_cart_value: Decimal = Decimal("0"),
                 priority: int = 50, stackable: bool = True, config: dict | None = None):
        super().__init__(discount_id, name, priority, stackable, config)
        self.rate = Decimal(str(rate))
        self.max_discount_amount = Decimal(str(max_discount_amount)) if max_discount_amount is not None else None
        self.min_cart_value = Decimal(str(min_cart_value))

    def is_applicable(self, context: DiscountContext) -> bool:
        return context.cart_total >= self.min_cart_value

    def calculate(self, context: DiscountContext, running_total: Decimal) -> DiscountResult:
        amount_off = running_total * self.rate
        if self.max_discount_amount is not None:
            amount_off = min(amount_off, self.max_discount_amount)
        amount_off = min(amount_off, running_total)
        return DiscountResult(
            discount_id=self.discount_id,
            discount_name=self.name,
            discount_type=self.discount_type,
            amount_off=amount_off,
            priority=self.priority,
            stacked=self.stackable,
            detail=f"{self.rate*100:.0f}% off" + (f" (capped at ₹{self.max_discount_amount})" if self.max_discount_amount else ""),
        )
