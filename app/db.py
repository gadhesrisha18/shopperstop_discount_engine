"""
Embedded SQLite database — no external DB setup needed for reviewers.
Uses SQLAlchemy's ORM for clarity; a fresh DB is created on startup and
seeded with demo data (see app/seed.py).
"""
from sqlalchemy import create_engine, Column, String, Integer, Float, Boolean, DateTime, Text, JSON
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

DATABASE_URL = "sqlite:///./shopperstop.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class PromotionORM(Base):
    __tablename__ = "promotions"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    discount_type = Column(String, nullable=False, index=True)
    description = Column(String, default="")
    params = Column(JSON, nullable=False)          # type-specific config, e.g. slabs / rate / etc.
    priority = Column(Integer, default=100)
    stackable = Column(Boolean, default=True)
    is_active = Column(Boolean, default=False, index=True)
    store_ids = Column(JSON, default=list)          # empty list = all stores
    customer_tiers = Column(JSON, default=list)      # empty list = all tiers
    starts_at = Column(DateTime, nullable=True)
    ends_at = Column(DateTime, nullable=True)
    version = Column(Integer, default=1)
    is_deleted = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CustomerTierORM(Base):
    __tablename__ = "customer_tiers"

    id = Column(String, primary_key=True, index=True)
    label = Column(String, nullable=False)
    slabs = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AuditLogORM(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_type = Column(String, nullable=False)     # "PROMOTION" | "CUSTOMER_TIER"
    entity_id = Column(String, nullable=False, index=True)
    action = Column(String, nullable=False)           # CREATE | UPDATE | ACTIVATE | DEACTIVATE | DELETE
    actor = Column(String, default="system")
    diff = Column(JSON, default=dict)
    correlation_id = Column(String, index=True, default="")
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
