import uuid
from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.request_models import CustomerTierCreateRequest, CustomerTierUpdateRequest
from app.models.response_models import CustomerTierOut
from app.services.promotion_service import PromotionService, PromotionNotFoundError

router = APIRouter(prefix="/api/v1/customer-tiers", tags=["Customer Tiers"])


@router.get("", response_model=list[CustomerTierOut])
def list_tiers(db: Session = Depends(get_db)):
    service = PromotionService(db)
    return service.list_tiers()


@router.post("", response_model=CustomerTierOut, status_code=201)
def create_tier(payload: CustomerTierCreateRequest, request: Request, db: Session = Depends(get_db)):
    service = PromotionService(db)
    correlation_id = request.headers.get("X-Correlation-Id", str(uuid.uuid4()))
    slabs = [s.model_dump() for s in payload.slabs]
    return service.create_tier(payload.id, payload.label, slabs, correlation_id=correlation_id)


@router.put("/{tier_id}", response_model=CustomerTierOut)
def update_tier(tier_id: str, payload: CustomerTierUpdateRequest, request: Request, db: Session = Depends(get_db)):
    service = PromotionService(db)
    correlation_id = request.headers.get("X-Correlation-Id", str(uuid.uuid4()))
    slabs = [s.model_dump() for s in payload.slabs] if payload.slabs is not None else None
    try:
        return service.update_tier(tier_id, payload.label, slabs, correlation_id=correlation_id)
    except PromotionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
