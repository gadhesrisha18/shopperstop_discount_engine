from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime


class CartItemIn(BaseModel):
    sku: str
    name: str
    category: str = "GENERAL"
    unit_price: float = Field(..., gt=0, description="Must be a positive number")
    quantity: int = Field(..., gt=0, description="Must be at least 1")

    @field_validator("unit_price")
    @classmethod
    def price_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError("unit_price must be greater than 0")
        return v


class BillCalculateRequest(BaseModel):
    cart_items: list[CartItemIn] = Field(..., min_length=1)
    customer_tier: str = Field(default="REGULAR", description="e.g. REGULAR, PREMIUM")
    store_id: Optional[str] = None
    coupon_codes: list[str] = Field(default_factory=list)
    now: Optional[datetime] = Field(default=None, description="Override evaluation time, mainly for testing time-based promos")
    preview: bool = Field(default=False, description="If true, calculation is not persisted/counted anywhere (idempotent preview)")

    @field_validator("cart_items")
    @classmethod
    def cart_not_empty(cls, v):
        if not v:
            raise ValueError("cart_items must not be empty")
        return v


class SlabIn(BaseModel):
    min: float = Field(..., ge=0)
    max: Optional[float] = None
    rate: float = Field(..., ge=0, le=1)


class PromotionCreateRequest(BaseModel):
    name: str
    discount_type: str = Field(..., description="SLAB | FLAT | PERCENTAGE | CATEGORY | BUY_X_GET_Y | TIME_BASED")
    description: str = ""
    params: dict = Field(..., description="Type-specific parameters, see API docs for schema per type")
    priority: int = Field(default=100, ge=0)
    stackable: bool = True
    store_ids: list[str] = Field(default_factory=list)
    customer_tiers: list[str] = Field(default_factory=list)
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    is_active: bool = False

    @field_validator("discount_type")
    @classmethod
    def valid_discount_type(cls, v):
        allowed = {"SLAB", "FLAT", "PERCENTAGE", "CATEGORY", "BUY_X_GET_Y", "TIME_BASED"}
        if v not in allowed:
            raise ValueError(f"discount_type must be one of {sorted(allowed)}")
        return v


class PromotionUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    params: Optional[dict] = None
    priority: Optional[int] = None
    stackable: Optional[bool] = None
    store_ids: Optional[list[str]] = None
    customer_tiers: Optional[list[str]] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None


class CustomerTierCreateRequest(BaseModel):
    id: str
    label: str
    slabs: list[SlabIn]


class CustomerTierUpdateRequest(BaseModel):
    label: Optional[str] = None
    slabs: Optional[list[SlabIn]] = None


class PromotionSimulateRequest(BaseModel):
    """Lets marketing test a NOT-YET-SAVED promotion config against a sample cart."""
    promotion: PromotionCreateRequest
    cart_items: list[CartItemIn] = Field(..., min_length=1)
    customer_tier: str = "REGULAR"
    now: Optional[datetime] = None
