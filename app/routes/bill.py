import uuid
from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.request_models import BillCalculateRequest
from app.models.response_models import BillCalculateResponse
from app.services.bill_service import BillService, BillCalculationError
from app.services.promotion_service import PromotionService

router = APIRouter(prefix="/api/v1/bills", tags=["Bills"])


@router.post("/calculate", response_model=BillCalculateResponse)
def calculate_bill(payload: BillCalculateRequest, request: Request, db: Session = Depends(get_db)):
    """
    Calculate the final bill for a cart, applying the customer's tier slab
    discount plus any active, applicable promotions (stacked per priority
    and stacking rules, capped at the configured max discount rate).

    `preview: true` runs the exact same logic without any side effects
    (nothing is written to the DB either way — this endpoint is always
    idempotent/side-effect-free; `preview` exists to make that contract
    explicit to callers such as the Marketing Manager's what-if tooling).
    """
    correlation_id = request.headers.get("X-Correlation-Id", str(uuid.uuid4()))
    promo_service = PromotionService(db)
    bill_service = BillService(
        promotion_provider=promo_service.active_promotions_for,
        tier_provider=promo_service.tiers_as_dict if promo_service.list_tiers() else None,
    )
    try:
        result = bill_service.calculate(
            cart_items_in=[item.model_dump() for item in payload.cart_items],
            customer_tier=payload.customer_tier,
            store_id=payload.store_id,
            coupon_codes=payload.coupon_codes,
            now=payload.now,
            correlation_id=correlation_id,
        )
    except BillCalculationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return result
