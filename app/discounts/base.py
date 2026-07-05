"""
Base abstractions for the discount engine.

Every discount type (slab, flat, percentage, category, BxGy, time-based)
implements the `DiscountStrategy` interface. This is what makes the engine
extensible: adding a new discount type never requires touching existing
discount classes or the orchestration logic in BillService — it's a new
class + a factory registration.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional
from datetime import datetime


@dataclass
class CartItem:
    sku: str
    name: str
    category: str
    unit_price: Decimal
    quantity: int

    @property
    def line_total(self) -> Decimal:
        return self.unit_price * self.quantity


@dataclass
class DiscountContext:
    """Everything a discount strategy might need to decide if/how it applies."""
    cart_items: list[CartItem]
    cart_total: Decimal
    customer_tier: str  # "REGULAR" or "PREMIUM" (extensible to more tiers)
    now: datetime = field(default_factory=datetime.utcnow)
    store_id: Optional[str] = None
    coupon_codes: list[str] = field(default_factory=list)


@dataclass
class DiscountResult:
    """Outcome of applying a single discount — used for the breakdown shown to cashiers/finance."""
    discount_id: str
    discount_name: str
    discount_type: str
    amount_off: Decimal
    priority: int
    stacked: bool = True
    detail: str = ""


class DiscountStrategy(ABC):
    """
    Contract every discount type must satisfy.

    discount_type: a stable string identifier used in config/API payloads
                    (e.g. "SLAB", "FLAT", "PERCENTAGE", "CATEGORY",
                    "BUY_X_GET_Y", "TIME_BASED").
    """

    discount_type: str = "BASE"

    def __init__(self, discount_id: str, name: str, priority: int = 100,
                 stackable: bool = True, config: Optional[dict] = None):
        self.discount_id = discount_id
        self.name = name
        self.priority = priority          # lower number = applied earlier
        self.stackable = stackable
        self.config = config or {}

    @abstractmethod
    def is_applicable(self, context: DiscountContext) -> bool:
        """Whether this discount should even be considered for this cart/context."""
        raise NotImplementedError

    @abstractmethod
    def calculate(self, context: DiscountContext, running_total: Decimal) -> DiscountResult:
        """
        Compute the discount amount given the *current* running total
        (i.e. after any higher-priority discounts have already been applied,
        when stacking sequentially). Must never return a negative amount_off
        or one that exceeds running_total.
        """
        raise NotImplementedError
