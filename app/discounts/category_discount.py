from decimal import Decimal
from app.discounts.base import DiscountStrategy, DiscountContext, DiscountResult


class CategoryDiscount(DiscountStrategy):
    """e.g. 25% off Electronics — only applies to matching category line items."""
    discount_type = "CATEGORY"

    def __init__(self, discount_id: str, name: str, category: str, rate: Decimal,
                 priority: int = 40, stackable: bool = True, config: dict | None = None):
        super().__init__(discount_id, name, priority, stackable, config)
        self.category = category
        self.rate = Decimal(str(rate))

    def _matching_total(self, context: DiscountContext) -> Decimal:
        return sum(
            (item.line_total for item in context.cart_items if item.category.lower() == self.category.lower()),
            Decimal("0"),
        )

    def is_applicable(self, context: DiscountContext) -> bool:
        return self._matching_total(context) > 0

    def calculate(self, context: DiscountContext, running_total: Decimal) -> DiscountResult:
        category_total = self._matching_total(context)
        amount_off = category_total * self.rate
        amount_off = min(amount_off, running_total)
        return DiscountResult(
            discount_id=self.discount_id,
            discount_name=self.name,
            discount_type=self.discount_type,
            amount_off=amount_off,
            priority=self.priority,
            stacked=self.stackable,
            detail=f"{self.rate*100:.0f}% off {self.category} (₹{category_total} eligible)",
        )
