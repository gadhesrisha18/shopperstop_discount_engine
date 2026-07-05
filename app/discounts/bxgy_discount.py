from decimal import Decimal
from app.discounts.base import DiscountStrategy, DiscountContext, DiscountResult


class BuyXGetYDiscount(DiscountStrategy):
    """
    e.g. Buy 2 shirts, get 1 free (of the same or a target SKU/category).
    free_qty units are given free for every buy_qty units purchased of the trigger item/category.
    """
    discount_type = "BUY_X_GET_Y"

    def __init__(self, discount_id: str, name: str, buy_qty: int, free_qty: int,
                 applies_to_category: str | None = None, applies_to_sku: str | None = None,
                 priority: int = 30, stackable: bool = True, config: dict | None = None):
        super().__init__(discount_id, name, priority, stackable, config)
        self.buy_qty = buy_qty
        self.free_qty = free_qty
        self.applies_to_category = applies_to_category
        self.applies_to_sku = applies_to_sku

    def _matching_items(self, context: DiscountContext):
        for item in context.cart_items:
            if self.applies_to_sku and item.sku == self.applies_to_sku:
                yield item
            elif self.applies_to_category and item.category.lower() == self.applies_to_category.lower():
                yield item

    def is_applicable(self, context: DiscountContext) -> bool:
        total_qty = sum(item.quantity for item in self._matching_items(context))
        return total_qty >= (self.buy_qty + self.free_qty)

    def calculate(self, context: DiscountContext, running_total: Decimal) -> DiscountResult:
        matching = list(self._matching_items(context))
        total_qty = sum(item.quantity for item in matching)
        group_size = self.buy_qty + self.free_qty
        num_free_groups = total_qty // group_size
        free_units = num_free_groups * self.free_qty

        # Free units are valued at the cheapest matching unit price (standard retail practice)
        if not matching:
            amount_off = Decimal("0")
        else:
            cheapest_unit_price = min(item.unit_price for item in matching)
            amount_off = cheapest_unit_price * free_units

        amount_off = min(amount_off, running_total)
        return DiscountResult(
            discount_id=self.discount_id,
            discount_name=self.name,
            discount_type=self.discount_type,
            amount_off=amount_off,
            priority=self.priority,
            stacked=self.stackable,
            detail=f"Buy {self.buy_qty} Get {self.free_qty} free — {free_units} unit(s) free",
        )
