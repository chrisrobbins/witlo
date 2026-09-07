"""Application entry point.

Startup does three things and refuses to continue if any of them fails: build
the providers (which cross-checks that the deployment cannot charge without
being able to mail), confirm the letter template parses, and log exactly what
this deployment is capable of. A server that will not print letters should say
so in its first line of output, not at the moment someone pays.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.letters.content import content_version, load_content
from app.providers.factory import get_providers

log = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    load_content()
    mail, payments = get_providers()

    log.info(
        "starting in %s mode | mail=%s (real mail: %s) | "
        "payments=%s (real money: %s) | template v%s",
        settings.app_mode,
        mail.name,
        mail.can_send_real_mail,
        payments.name if payments else "none",
        bool(payments and payments.can_charge_real_money),
        content_version(),
    )
    if not mail.can_send_real_mail:
        log.warning("This deployment CANNOT send real mail. Nothing will reach a mailbox.")
    yield


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Why Is This Light On? API",
        version="1.0.0",
        description=(
            "Composes, prices and mails friendly letters about outdoor lighting. "
            "The letter text is assembled from a fixed template; no language model is "
            "involved anywhere in this service."
        ),
        lifespan=lifespan,
        docs_url="/docs" if settings.app_mode != "live" else None,
        redoc_url=None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,  # no cookies; nothing to protect with credentials
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Idempotency-Key", "Accept"],
        max_age=600,
    )

    app.include_router(router)

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Pydantic's default body echoes the offending input, which for this API
        # means echoing a recipient address into a response and a log line.
        first = exc.errors()[0] if exc.errors() else {}
        field = ".".join(str(p) for p in first.get("loc", ())[1:]) or "request"
        return JSONResponse(
            status_code=422,
            content={"code": "invalid_request", "detail": f"Check the {field} field."},
        )

    @app.get("/", include_in_schema=False)
    async def root() -> dict:
        return {
            "service": "Why Is This Light On? API",
            "docs": "/docs",
            "health": "/api/v1/health",
        }

    return app


app = create_app()
