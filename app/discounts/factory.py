"""
Maps a promotion's stored config (as it comes out of the DB / JSON config)
into a live DiscountStrategy instance. This is the single place you touch
when adding a brand-new discount type: register it in STRATEGY_REGISTRY and
implement its DiscountStrategy subclass — nothing else in the engine changes.
"""
from datetime import time
from decimal import Decimal

from app.discounts.base import DiscountStrategy
from app.discounts.slab_discount import SlabDiscount
from app.discounts.flat_discount import FlatDiscount
from app.discounts.percentage_discount import PercentageDiscount
from app.discounts.category_discount import CategoryDiscount
from app.discounts.bxgy_discount import BuyXGetYDiscount
from app.discounts.time_based_discount import TimeBasedDiscount


def _build_slab(promo: dict) -> SlabDiscount:
    return SlabDiscount(
        discount_id=promo["id"], name=promo["name"], slabs=promo["params"]["slabs"],
        priority=promo.get("priority", 10), stackable=promo.get("stackable", True),
    )


def _build_flat(promo: dict) -> FlatDiscount:
    p = promo["params"]
    return FlatDiscount(
        discount_id=promo["id"], name=promo["name"],
        amount_off=Decimal(str(p["amount_off"])),
        min_cart_value=Decimal(str(p.get("min_cart_value", 0))),
        priority=promo.get("priority", 50), stackable=promo.get("stackable", True),
    )


def _build_percentage(promo: dict) -> PercentageDiscount:
    p = promo["params"]
    return PercentageDiscount(
        discount_id=promo["id"], name=promo["name"],
        rate=Decimal(str(p["rate"])),
        max_discount_amount=Decimal(str(p["max_discount_amount"])) if p.get("max_discount_amount") is not None else None,
        min_cart_value=Decimal(str(p.get("min_cart_value", 0))),
        priority=promo.get("priority", 50), stackable=promo.get("stackable", True),
    )


def _build_category(promo: dict) -> CategoryDiscount:
    p = promo["params"]
    return CategoryDiscount(
        discount_id=promo["id"], name=promo["name"],
        category=p["category"], rate=Decimal(str(p["rate"])),
        priority=promo.get("priority", 40), stackable=promo.get("stackable", True),
    )


def _build_bxgy(promo: dict) -> BuyXGetYDiscount:
    p = promo["params"]
    return BuyXGetYDiscount(
        discount_id=promo["id"], name=promo["name"],
        buy_qty=p["buy_qty"], free_qty=p["free_qty"],
        applies_to_category=p.get("applies_to_category"),
        applies_to_sku=p.get("applies_to_sku"),
        priority=promo.get("priority", 30), stackable=promo.get("stackable", True),
    )


def _parse_time(value: str) -> time:
    hh, mm = value.split(":")
    return time(int(hh), int(mm))


def _build_time_based(promo: dict) -> TimeBasedDiscount:
    p = promo["params"]
    return TimeBasedDiscount(
        discount_id=promo["id"], name=promo["name"],
        rate=Decimal(str(p["rate"])),
        start_time=_parse_time(p["start_time"]), end_time=_parse_time(p["end_time"]),
        days_of_week=p.get("days_of_week"),
        priority=promo.get("priority", 60), stackable=promo.get("stackable", True),
    )


STRATEGY_REGISTRY = {
    "SLAB": _build_slab,
    "FLAT": _build_flat,
    "PERCENTAGE": _build_percentage,
    "CATEGORY": _build_category,
    "BUY_X_GET_Y": _build_bxgy,
    "TIME_BASED": _build_time_based,
}


def build_strategy(promo: dict) -> DiscountStrategy:
    discount_type = promo["discount_type"]
    builder = STRATEGY_REGISTRY.get(discount_type)
    if builder is None:
        raise ValueError(f"Unknown discount_type '{discount_type}'. "
                          f"Known types: {list(STRATEGY_REGISTRY.keys())}")
    return builder(promo)
