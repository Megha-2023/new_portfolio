import logging
from collections.abc import Callable
from typing import Any

from fastapi import Body, FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from .config import Settings, get_settings
from .database import ContactRepository
from .email_service import GmailNotifier
from .email_validation import (
    EmailDomainUnreachableError,
    InvalidEmailError,
    get_email_domain_validator,
    normalize_email_address,
)
from .schemas import ContactRequest, ContactResponse
from .security import get_client_ip, hash_client_ip


logger = logging.getLogger(__name__)

RepositoryFactory = Callable[[Settings], ContactRepository]
NotifierFactory = Callable[[Settings], GmailNotifier]


def create_app(settings: Settings | None = None) -> FastAPI:
    active_settings = settings or get_settings()
    application = FastAPI(
        title="Megha Panchal portfolio contact API",
        version="1.0.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=active_settings.cors_origins,
        allow_credentials=False,
        allow_methods=["POST", "GET"],
        allow_headers=["Content-Type"],
        max_age=86400,
    )
    application.state.settings = active_settings
    application.state.repository_factory = ContactRepository
    application.state.notifier_factory = GmailNotifier
    application.state.email_domain_validator = get_email_domain_validator()

    @application.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        response.headers["Permissions-Policy"] = "camera=(), geolocation=(), microphone=()"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        if request.url.path == "/api/contact":
            response.headers["Cache-Control"] = "no-store"
        return response

    @application.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.post(
        "/api/contact",
        response_model=ContactResponse,
        responses={400: {"description": "Invalid JSON"}, 422: {"description": "Validation error"}, 429: {"description": "Rate limited"}},
    )
    async def contact(request: Request, raw_submission: dict[str, Any] = Body(...)) -> JSONResponse:
        website = raw_submission.get("website")
        if isinstance(website, str) and website.strip():
            return JSONResponse({"ok": True})

        try:
            normalized_email = normalize_email_address(raw_submission.get("email"))
        except EmailDomainUnreachableError:
            return JSONResponse(
                {"error": "email_domain_unreachable", "field": "email"},
                status_code=422,
            )
        except InvalidEmailError:
            return JSONResponse(
                {"error": "invalid_email", "field": "email"},
                status_code=422,
            )

        try:
            submission = ContactRequest.model_validate({
                **raw_submission,
                "email": normalized_email,
            })
        except ValidationError:
            return JSONResponse({"error": "validation_error"}, status_code=422)

        request_settings: Settings = request.app.state.settings
        missing = request_settings.missing_required_values()
        if missing:
            logger.error("Contact API configuration is incomplete: %s", ", ".join(missing))
            return JSONResponse({"error": "server_error"}, status_code=503)

        repository_factory: RepositoryFactory = request.app.state.repository_factory
        notifier_factory: NotifierFactory = request.app.state.notifier_factory

        try:
            repository = repository_factory(request_settings)
            client_ip = get_client_ip(request, request_settings.trust_proxy_headers)
            ip_hash = hash_client_ip(client_ip, request_settings.rate_limit_salt)
            accepted = await run_in_threadpool(repository.consume_rate_limit, ip_hash)
            if not accepted:
                return JSONResponse({"error": "rate_limit"}, status_code=429)

            try:
                await run_in_threadpool(
                    request.app.state.email_domain_validator.validate,
                    submission.email,
                )
            except EmailDomainUnreachableError:
                return JSONResponse(
                    {"error": "email_domain_unreachable", "field": "email"},
                    status_code=422,
                )
            except Exception:
                logger.exception(
                    "Unexpected temporary failure during email-domain validation; "
                    "continuing with the syntactically valid enquiry"
                )

            enquiry = await run_in_threadpool(repository.save_enquiry, submission)
        except Exception:
            logger.exception("Contact enquiry storage failed")
            return JSONResponse({"error": "server_error"}, status_code=503)

        notification_sent = False
        try:
            notifier = notifier_factory(request_settings)
            await run_in_threadpool(notifier.send, enquiry)
            await run_in_threadpool(repository.mark_notification_sent, enquiry.id)
            notification_sent = True
        except Exception:
            logger.exception("Gmail notification failed for enquiry %s", enquiry.id)
            try:
                await run_in_threadpool(
                    repository.mark_notification_failed,
                    enquiry.id,
                    "gmail_delivery_failed",
                )
            except Exception:
                logger.exception("Could not record notification failure for enquiry %s", enquiry.id)

        return JSONResponse({"ok": True, "notification_sent": notification_sent})

    return application


app = create_app()
