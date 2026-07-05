"""
Repository layer — isolates SQLAlchemy/DB details from the service layer.
Swapping SQLite for Postgres later only touches app/db.py + here.
"""
from __future__ import annotations  # avoids class-body name-shadowing of `list` (methods named `list`) in type hints
import uuid
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db import PromotionORM, CustomerTierORM, AuditLogORM


class PromotionRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, data: dict) -> PromotionORM:
        promo = PromotionORM(id=str(uuid.uuid4()), **data)
        self.db.add(promo)
        self.db.commit()
        self.db.refresh(promo)
        return promo

    def get(self, promo_id: str) -> PromotionORM | None:
        stmt = select(PromotionORM).where(PromotionORM.id == promo_id, PromotionORM.is_deleted == False)  # noqa: E712
        return self.db.execute(stmt).scalar_one_or_none()

    def list(self, is_active: bool | None = None, discount_type: str | None = None,
              store_id: str | None = None) -> list[PromotionORM]:
        stmt = select(PromotionORM).where(PromotionORM.is_deleted == False)  # noqa: E712
        if is_active is not None:
            stmt = stmt.where(PromotionORM.is_active == is_active)
        if discount_type is not None:
            stmt = stmt.where(PromotionORM.discount_type == discount_type)
        results = list(self.db.execute(stmt).scalars().all())
        if store_id is not None:
            results = [p for p in results if not p.store_ids or store_id in p.store_ids]
        return results

    def update(self, promo: PromotionORM, changes: dict) -> PromotionORM:
        for key, value in changes.items():
            if value is not None:
                setattr(promo, key, value)
        promo.version += 1
        promo.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(promo)
        return promo

    def set_active(self, promo: PromotionORM, active: bool) -> PromotionORM:
        promo.is_active = active
        promo.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(promo)
        return promo

    def soft_delete(self, promo: PromotionORM) -> PromotionORM:
        promo.is_deleted = True
        promo.is_active = False
        promo.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(promo)
        return promo


class CustomerTierRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, tier_id: str, label: str, slabs: list[dict]) -> CustomerTierORM:
        tier = CustomerTierORM(id=tier_id, label=label, slabs=slabs)
        self.db.add(tier)
        self.db.commit()
        self.db.refresh(tier)
        return tier

    def get(self, tier_id: str) -> CustomerTierORM | None:
        return self.db.get(CustomerTierORM, tier_id)

    def list(self) -> list[CustomerTierORM]:
        return list(self.db.execute(select(CustomerTierORM)).scalars().all())

    def update(self, tier: CustomerTierORM, label: str | None, slabs: list[dict] | None) -> CustomerTierORM:
        if label is not None:
            tier.label = label
        if slabs is not None:
            tier.slabs = slabs
        tier.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(tier)
        return tier


class AuditLogRepository:
    def __init__(self, db: Session):
        self.db = db

    def record(self, entity_type: str, entity_id: str, action: str,
               diff: dict, correlation_id: str, actor: str = "system"):
        log = AuditLogORM(
            entity_type=entity_type, entity_id=entity_id, action=action,
            diff=diff, correlation_id=correlation_id, actor=actor,
        )
        self.db.add(log)
        self.db.commit()

    def list_for_entity(self, entity_id: str) -> list[AuditLogORM]:
        stmt = select(AuditLogORM).where(AuditLogORM.entity_id == entity_id).order_by(AuditLogORM.created_at.desc())
        return list(self.db.execute(stmt).scalars().all())
