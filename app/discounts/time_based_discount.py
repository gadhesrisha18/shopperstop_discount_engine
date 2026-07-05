from decimal import Decimal
from datetime import time
from app.discounts.base import DiscountStrategy, DiscountContext, DiscountResult


class TimeBasedDiscount(DiscountStrategy):
    """e.g. Happy Hour: 5 PM - 8 PM, extra 5% off. Window is local-time-of-day based."""
    discount_type = "TIME_BASED"

    def __init__(self, discount_id: str, name: str, rate: Decimal,
                 start_time: time, end_time: time,
                 days_of_week: list[int] | None = None,  # 0=Mon .. 6=Sun; None = every day
                 priority: int = 60, stackable: bool = True, config: dict | None = None):
        super().__init__(discount_id, name, priority, stackable, config)
        self.rate = Decimal(str(rate))
        self.start_time = start_time
        self.end_time = end_time
        self.days_of_week = days_of_week

    def is_applicable(self, context: DiscountContext) -> bool:
        now = context.now
        if self.days_of_week is not None and now.weekday() not in self.days_of_week:
            return False
        current_time = now.time()
        if self.start_time <= self.end_time:
            return self.start_time <= current_time <= self.end_time
        # window spans midnight
        return current_time >= self.start_time or current_time <= self.end_time

    def calculate(self, context: DiscountContext, running_total: Decimal) -> DiscountResult:
        amount_off = min(running_total * self.rate, running_total)
        return DiscountResult(
            discount_id=self.discount_id,
            discount_name=self.name,
            discount_type=self.discount_type,
            amount_off=amount_off,
            priority=self.priority,
            stacked=self.stackable,
            detail=f"Happy Hour {self.start_time}-{self.end_time}: {self.rate*100:.0f}% off",
        )
