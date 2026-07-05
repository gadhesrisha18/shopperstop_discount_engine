from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class DiscountBreakdownOut(BaseModel):
    discount_id: str
    discount_name: str
    discount_type: str
    amount_off: float
    priority: int
    applied: bool
    detail: str = ""
    skipped_reason: Optional[str] = None


class BillCalculateResponse(BaseModel):
    cart_subtotal: float
    total_discount: float
    final_amount: float
    customer_tier: str
    discounts_breakdown: list[DiscountBreakdownOut]
    capped: bool = False
    cap_rate: Optional[float] = None
    correlation_id: str


class PromotionOut(BaseModel):
    id: str
    name: str
    discount_type: str
    description: str
    params: dict
    priority: int
    stackable: bool
    is_active: bool
    store_ids: list[str]
    customer_tiers: list[str]
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    version: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PromotionListResponse(BaseModel):
    items: list[PromotionOut]
    total: int


class CustomerTierOut(BaseModel):
    id: str
    label: str
    slabs: list[dict]

    class Config:
        from_attributes = True


class ErrorResponse(BaseModel):
    error: str
    message: str
    correlation_id: Optional[str] = None
    details: Optional[dict] = None


class HealthResponse(BaseModel):
    status: str
    version: str
    db: str
