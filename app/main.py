import uuid
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from pydantic import ValidationError as PydanticValidationError

from app.db import init_db, engine
from app.seed import seed_if_empty
from app.middleware import CorrelationIdMiddleware
from app.routes import bill, promotions, customer_tiers
from app.models.response_models import HealthResponse

logger = logging.getLogger("ppe")

app = FastAPI(
    title="ShopperStop Promotional Pricing Engine",
    description="Configurable, API-driven discount engine for tiered, stacked and time-based promotions.",
    version="1.0.0",
)

app.add_middleware(CorrelationIdMiddleware)

app.include_router(bill.router)
app.include_router(promotions.router)
app.include_router(customer_tiers.router)


@app.on_event("startup")
def on_startup():
    init_db()
    seed_if_empty()


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    correlation_id = request.headers.get("X-Correlation-Id", str(uuid.uuid4()))
    return JSONResponse(
        status_code=422,
        content={
            "error": "VALIDATION_ERROR",
            "message": "Request payload failed validation.",
            "correlation_id": correlation_id,
            "details": {"errors": jsonable_encoder(exc.errors())},
        },
    )


@app.exception_handler(PydanticValidationError)
async def pydantic_validation_exception_handler(request: Request, exc: PydanticValidationError):
    correlation_id = request.headers.get("X-Correlation-Id", str(uuid.uuid4()))
    return JSONResponse(
        status_code=422,
        content={"error": "VALIDATION_ERROR", "message": str(exc), "correlation_id": correlation_id},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    correlation_id = request.headers.get("X-Correlation-Id", str(uuid.uuid4()))
    logger.error(f'{{"correlation_id": "{correlation_id}", "error": "{str(exc)}"}}')
    return JSONResponse(
        status_code=500,
        content={"error": "INTERNAL_ERROR", "message": "An unexpected error occurred.",
                  "correlation_id": correlation_id},
    )


@app.get("/health", response_model=HealthResponse, tags=["System"])
def health():
    db_status = "ok"
    try:
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
    except Exception:
        db_status = "unavailable"
    return HealthResponse(status="ok" if db_status == "ok" else "degraded", version="1.0.0", db=db_status)


@app.get("/", tags=["System"])
def root():
    return {"service": "ShopperStop Promotional Pricing Engine", "docs": "/docs", "health": "/health"}
