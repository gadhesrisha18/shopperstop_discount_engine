import logging
import time
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger("ppe")
logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "message": %(message)s}',
)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Attaches an X-Correlation-Id to every request/response and logs each call structurally."""

    async def dispatch(self, request: Request, call_next):
        correlation_id = request.headers.get("X-Correlation-Id", str(uuid.uuid4()))
        start = time.time()
        response = await call_next(request)
        duration_ms = round((time.time() - start) * 1000, 2)
        response.headers["X-Correlation-Id"] = correlation_id
        logger.info(json_log(
            correlation_id=correlation_id, method=request.method, path=request.url.path,
            status_code=response.status_code, duration_ms=duration_ms,
        ))
        return response


def json_log(**kwargs) -> str:
    import json
    return json.dumps(kwargs)
