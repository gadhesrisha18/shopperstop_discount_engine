import datetime as dt
from sqlalchemy.orm import Session

from app.repository.promotion_repository import PromotionRepository, CustomerTierRepository, AuditLogRepository
from app.discounts.factory import build_strategy, STRATEGY_REGISTRY


class PromotionNotFoundError(Exception):
    pass


class PromotionValidationError(Exception):
    pass


class PromotionService:
    def __init__(self, db: Session):
        self.db = db
        self.promo_repo = PromotionRepository(db)
        self.tier_repo = CustomerTierRepository(db)
        self.audit_repo = AuditLogRepository(db)

    def _validate_params(self, discount_type: str, params: dict):
        """Sanity-check params by attempting to build the strategy (fail fast on bad config)."""
        fake_promo = {"id": "validate", "name": "validate", "discount_type": discount_type,
                      "params": params, "priority": 0, "stackable": True}
        try:
            build_strategy(fake_promo)
        except (KeyError, ValueError) as e:
            raise PromotionValidationError(f"Invalid params for {discount_type}: {e}")

    def create_promotion(self, data: dict, correlation_id: str, actor: str = "system"):
        self._validate_params(data["discount_type"], data["params"])
        promo = self.promo_repo.create(data)
        self.audit_repo.record("PROMOTION", promo.id, "CREATE", diff=data,
                                correlation_id=correlation_id, actor=actor)
        return promo

    def get_promotion(self, promo_id: str):
        promo = self.promo_repo.get(promo_id)
        if not promo:
            raise PromotionNotFoundError(f"Promotion '{promo_id}' not found")
        return promo

    def list_promotions(self, is_active=None, discount_type=None, store_id=None):
        return self.promo_repo.list(is_active=is_active, discount_type=discount_type, store_id=store_id)

    def update_promotion(self, promo_id: str, changes: dict, correlation_id: str, actor: str = "system"):
        promo = self.get_promotion(promo_id)
        if changes.get("params") is not None:
            dtype = changes.get("discount_type") or promo.discount_type
            self._validate_params(dtype, changes["params"])
        updated = self.promo_repo.update(promo, changes)
        self.audit_repo.record("PROMOTION", promo_id, "UPDATE", diff=changes,
                                correlation_id=correlation_id, actor=actor)
        return updated

    def activate(self, promo_id: str, correlation_id: str, actor: str = "system"):
        promo = self.get_promotion(promo_id)
        updated = self.promo_repo.set_active(promo, True)
        self.audit_repo.record("PROMOTION", promo_id, "ACTIVATE", diff={"is_active": True},
                                correlation_id=correlation_id, actor=actor)
        return updated

    def deactivate(self, promo_id: str, correlation_id: str, actor: str = "system"):
        promo = self.get_promotion(promo_id)
        updated = self.promo_repo.set_active(promo, False)
        self.audit_repo.record("PROMOTION", promo_id, "DEACTIVATE", diff={"is_active": False},
                                correlation_id=correlation_id, actor=actor)
        return updated

    def delete_promotion(self, promo_id: str, correlation_id: str, actor: str = "system"):
        promo = self.get_promotion(promo_id)
        deleted = self.promo_repo.soft_delete(promo)
        self.audit_repo.record("PROMOTION", promo_id, "DELETE", diff={"is_deleted": True},
                                correlation_id=correlation_id, actor=actor)
        return deleted

    def active_promotions_for(self, store_id: str | None, customer_tier: str, now: dt.datetime) -> list[dict]:
        """Used by BillService as the promotion_provider callback."""
        promos = self.promo_repo.list(is_active=True, store_id=store_id)
        results = []
        for p in promos:
            if p.customer_tiers and customer_tier not in p.customer_tiers:
                continue
            if p.starts_at and now < p.starts_at:
                continue
            if p.ends_at and now > p.ends_at:
                continue
            results.append({
                "id": p.id, "name": p.name, "discount_type": p.discount_type,
                "params": p.params, "priority": p.priority, "stackable": p.stackable,
            })
        return results

    # --- Customer tiers ---
    def create_tier(self, tier_id: str, label: str, slabs: list[dict], correlation_id: str, actor: str = "system"):
        tier = self.tier_repo.create(tier_id, label, slabs)
        self.audit_repo.record("CUSTOMER_TIER", tier_id, "CREATE",
                                diff={"label": label, "slabs": slabs}, correlation_id=correlation_id, actor=actor)
        return tier

    def list_tiers(self):
        return self.tier_repo.list()

    def update_tier(self, tier_id: str, label: str | None, slabs: list[dict] | None,
                     correlation_id: str, actor: str = "system"):
        tier = self.tier_repo.get(tier_id)
        if not tier:
            raise PromotionNotFoundError(f"Customer tier '{tier_id}' not found")
        updated = self.tier_repo.update(tier, label, slabs)
        self.audit_repo.record("CUSTOMER_TIER", tier_id, "UPDATE",
                                diff={"label": label, "slabs": slabs}, correlation_id=correlation_id, actor=actor)
        return updated

    def tiers_as_dict(self) -> dict:
        return {t.id: {"label": t.label, "slabs": t.slabs} for t in self.tier_repo.list()}
