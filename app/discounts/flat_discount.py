from decimal import Decimal
from app.discounts.base import DiscountStrategy, DiscountContext, DiscountResult


class FlatDiscount(DiscountStrategy):
    """e.g. ₹500 off on orders above ₹3,000."""
    discount_type = "FLAT"

    def __init__(self, discount_id: str, name: str, amount_off: Decimal,
                 min_cart_value: Decimal = Decimal("0"),
                 priority: int = 50, stackable: bool = True, config: dict | None = None):
        super().__init__(discount_id, name, priority, stackable, config)
        self.amount_off_config = Decimal(str(amount_off))
        self.min_cart_value = Decimal(str(min_cart_value))

    def is_applicable(self, context: DiscountContext) -> bool:
        return context.cart_total >= self.min_cart_value

    def calculate(self, context: DiscountContext, running_total: Decimal) -> DiscountResult:
        amount_off = min(self.amount_off_config, running_total)
        return DiscountResult(
            discount_id=self.discount_id,
            discount_name=self.name,
            discount_type=self.discount_type,
            amount_off=amount_off,
            priority=self.priority,
            stacked=self.stackable,
            detail=f"Flat ₹{self.amount_off_config} off orders ≥ ₹{self.min_cart_value}",
        )
