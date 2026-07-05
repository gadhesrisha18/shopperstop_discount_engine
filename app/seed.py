"""Seeds the database with the default customer tiers and a handful of demo promotions."""
import json
import datetime as dt
from pathlib import Path
from sqlalchemy.orm import Session

from app.db import SessionLocal, CustomerTierORM, PromotionORM

CONFIG_PATH = Path(__file__).resolve().parent / "config" / "discount_rules.json"


def seed_if_empty():
    db: Session = SessionLocal()
    try:
        if db.query(CustomerTierORM).count() == 0:
            config = json.loads(CONFIG_PATH.read_text())
            for tier_id, tier in config["customer_tiers"].items():
                db.add(CustomerTierORM(id=tier_id, label=tier["label"], slabs=tier["slabs"]))
            db.commit()

        if db.query(PromotionORM).count() == 0:
            now = dt.datetime.utcnow()
            demo_promotions = [
                PromotionORM(
                    id="promo-flat-500", name="Flat 500 off over 3000", discount_type="FLAT",
                    description="₹500 off on orders above ₹3,000",
                    params={"amount_off": 500, "min_cart_value": 3000},
                    priority=50, stackable=True, is_active=True,
                    store_ids=[], customer_tiers=[],
                ),
                PromotionORM(
                    id="promo-electronics-25", name="25% off Electronics", discount_type="CATEGORY",
                    description="25% off Electronics category items",
                    params={"category": "Electronics", "rate": 0.25},
                    priority=40, stackable=True, is_active=True,
                    store_ids=[], customer_tiers=[],
                ),
                PromotionORM(
                    id="promo-happy-hour", name="Happy Hour 5-8 PM", discount_type="TIME_BASED",
                    description="Extra 5% off between 5 PM and 8 PM",
                    params={"rate": 0.05, "start_time": "17:00", "end_time": "20:00"},
                    priority=60, stackable=True, is_active=True,
                    store_ids=[], customer_tiers=[],
                ),
                PromotionORM(
                    id="promo-bxgy-shirts", name="Buy 2 Get 1 Free - Shirts", discount_type="BUY_X_GET_Y",
                    description="Buy 2 shirts, get 1 free",
                    params={"buy_qty": 2, "free_qty": 1, "applies_to_category": "Apparel"},
                    priority=30, stackable=True, is_active=True,
                    store_ids=[], customer_tiers=[],
                ),
                PromotionORM(
                    id="promo-coupon10", name="10% Coupon (non-stackable)", discount_type="PERCENTAGE",
                    description="10% off entire cart, does not stack with other percentage offers",
                    params={"rate": 0.10, "max_discount_amount": 2000},
                    priority=45, stackable=False, is_active=False,  # inactive by default; activate to test coupons
                    store_ids=[], customer_tiers=["PREMIUM"],
                ),
            ]
            db.add_all(demo_promotions)
            db.commit()
    finally:
        db.close()
