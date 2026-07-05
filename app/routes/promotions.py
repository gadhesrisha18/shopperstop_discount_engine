import uuid
from fastapi import APIRouter, Depends, Request, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.db import get_db
from app.models.request_models import (
    PromotionCreateRequest, PromotionUpdateRequest, PromotionSimulateRequest,
)
from app.models.response_models import PromotionOut, PromotionListResponse, BillCalculateResponse
from app.services.promotion_service import PromotionService, PromotionNotFoundError, PromotionValidationError
from app.services.bill_service import BillService, BillCalculationError

router = APIRouter(prefix="/api/v1/promotions", tags=["Promotions"])


def _correlation_id(request: Request) -> str:
    return request.headers.get("X-Correlation-Id", str(uuid.uuid4()))


@router.post("", response_model=PromotionOut, status_code=201)
def create_promotion(payload: PromotionCreateRequest, request: Request, db: Session = Depends(get_db)):
    service = PromotionService(db)
    try:
        promo = service.create_promotion(payload.model_dump(), correlation_id=_correlation_id(request))
    except PromotionValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return promo


@router.get("", response_model=PromotionListResponse)
def list_promotions(
    is_active: Optional[bool] = Query(default=None),
    discount_type: Optional[str] = Query(default=None),
    store_id: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    service = PromotionService(db)
    items = service.list_promotions(is_active=is_active, discount_type=discount_type, store_id=store_id)
    return PromotionListResponse(items=items, total=len(items))


@router.get("/{promo_id}", response_model=PromotionOut)
def get_promotion(promo_id: str, db: Session = Depends(get_db)):
    service = PromotionService(db)
    try:
        return service.get_promotion(promo_id)
    except PromotionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/{promo_id}", response_model=PromotionOut)
def update_promotion(promo_id: str, payload: PromotionUpdateRequest, request: Request, db: Session = Depends(get_db)):
    service = PromotionService(db)
    changes = {k: v for k, v in payload.model_dump().items() if v is not None}
    try:
        return service.update_promotion(promo_id, changes, correlation_id=_correlation_id(request))
    except PromotionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PromotionValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.delete("/{promo_id}", status_code=204)
def delete_promotion(promo_id: str, request: Request, db: Session = Depends(get_db)):
    service = PromotionService(db)
    try:
        service.delete_promotion(promo_id, correlation_id=_correlation_id(request))
    except PromotionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return None


@router.post("/{promo_id}/activate", response_model=PromotionOut)
def activate_promotion(promo_id: str, request: Request, db: Session = Depends(get_db)):
    service = PromotionService(db)
    try:
        return service.activate(promo_id, correlation_id=_correlation_id(request))
    except PromotionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{promo_id}/deactivate", response_model=PromotionOut)
def deactivate_promotion(promo_id: str, request: Request, db: Session = Depends(get_db)):
    service = PromotionService(db)
    try:
        return service.deactivate(promo_id, correlation_id=_correlation_id(request))
    except PromotionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/simulate", response_model=BillCalculateResponse)
def simulate_promotion(payload: PromotionSimulateRequest, db: Session = Depends(get_db)):
    """
    Lets Marketing preview the effect of a promotion config BEFORE saving/activating it.
    Combines the draft promotion with the store's currently active promotions
    so marketing can see the *real* stacked outcome, not just the new promo in isolation.
    """
    service = PromotionService(db)
    draft = payload.promotion.model_dump()
    draft["id"] = "DRAFT"

    def provider(store_id, customer_tier, now):
        existing = service.active_promotions_for(store_id, customer_tier, now)
        return existing + [draft]

    bill_service = BillService(
        promotion_provider=provider,
        tier_provider=service.tiers_as_dict if service.list_tiers() else None,
    )
    try:
        result = bill_service.calculate(
            cart_items_in=[item.model_dump() for item in payload.cart_items],
            customer_tier=payload.customer_tier,
            now=payload.now,
        )
    except BillCalculationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return result
