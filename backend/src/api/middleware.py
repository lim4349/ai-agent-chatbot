"""FastAPI middleware."""

import time
from typing import override

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = structlog.get_logger()


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging requests and responses."""

    # Skip logging for health checks and monitoring endpoints to reduce noise
    SKIP_PATHS = {"/api/v1/health", "/api/v1/logs", "/docs", "/redoc", "/openapi.json"}

    @override
    async def dispatch(self, request: Request, call_next) -> Response:
        start_time = time.perf_counter()
        path = request.url.path

        # Skip logging for health checks and monitoring endpoints
        if path in self.SKIP_PATHS:
            return await call_next(request)

        # Log request
        logger.info(
            "request_started",
            method=request.method,
            path=path,
            query=str(request.query_params) if request.query_params else None,
        )

        try:
            response = await call_next(request)

            # Calculate duration
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Log response
            logger.info(
                "request_completed",
                method=request.method,
                path=path,
                status_code=response.status_code,
                duration_ms=round(duration_ms, 2),
            )

            # Add timing header
            response.headers["X-Process-Time-Ms"] = f"{duration_ms:.2f}"

            return response

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                "request_failed",
                method=request.method,
                path=path,
                error=str(e),
                duration_ms=round(duration_ms, 2),
            )
            raise


class ExceptionHandlerMiddleware(BaseHTTPMiddleware):
    """Middleware for handling exceptions globally."""

    @override
    async def dispatch(self, request: Request, call_next) -> Response:
        try:
            return await call_next(request)
        except Exception as e:
            logger.exception("unhandled_exception", path=request.url.path, error=str(e))

            from fastapi.responses import JSONResponse

            # Check if it's our custom exception
            if hasattr(e, "to_dict"):
                return JSONResponse(status_code=500, content=e.to_dict())

            return JSONResponse(
                status_code=500,
                content={"error": {"code": "INTERNAL_ERROR", "message": str(e)}},
            )
