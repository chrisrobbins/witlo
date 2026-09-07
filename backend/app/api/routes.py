"""HTTP routes.

Shape of the API:

    POST /api/v1/addresses/verify   check an address, cooldown and suppression
    POST /api/v1/letters            compose and store a draft (server-side)
    POST /api/v1/letters/{id}/checkout   open a hosted payment session
    GET  /api/v1/letters/{id}/status     what has actually happened
    POST /api/v1/suppressions       a recipient asking not to be written to
    POST /api/v1/webhooks/payments  verified payment events
    POST /api/v1/webhooks/mail      verified mailing-provider events
    GET  /api/v1/health             what this deployment is capable of

Two conventions worth knowing. Webhook routes read the raw body and never a
parsed model, because signatures are computed over exact bytes. And every
webhook returns 200 once the event has been recorded, even when the event was a
duplicate or referred to nothing — retries from a provider are not errors, and
returning 500 for them just produces more retries.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.api import schemas
from app.api.deps import (
    client_hash,
    mail_provider_dep,
    payment_provider_dep,
    rate_limit,
    settings_dep,
    verify_bot_token,
)
from app.core.config import Settings
from app.db.models import Letter
from app.db.session import get_db, session_scope
from app.letters.address import AddressError, address_hash, validate_us_address
from app.letters.content import content_version
from app.payments.base import PaymentError, PaymentProvider
from app.providers.base import MailProvider, MailProviderError
from app.providers.factory import get_providers
from app.services import mailing
from app.services.state import LetterStatus

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1")

STATUS_LABELS: dict[str, str] = {
    "draft": "Not sent",
    "pending_payment": "Waiting on payment",
    "paid": "Paid — queued for printing",
    "submitting": "Being submitted",
    "submitted": "Submitted to the mailing provider",
    "in_transit": "In transit",
    "in_local_area": "In the destination area",
    "processed_for_delivery": "Processed for delivery",
    "returned_to_sender": "Returned to sender",
    "failed": "Not mailed",
    "canceled": "Canceled",
}


def _service_error(exc: mailing.ServiceError) -> HTTPException:
    return HTTPException(
        status_code=exc.status_code, detail={"code": exc.code, "detail": str(exc)}
    )


# --------------------------------------------------------------------------


@router.get("/health", response_model=schemas.HealthResponse)
def health(settings: Settings = Depends(settings_dep)) -> schemas.HealthResponse:
    mail, payments = get_providers()
    return schemas.HealthResponse(
        status="ok",
        mode=settings.app_mode,
        mailProvider=mail.name,
        paymentProvider=payments.name if payments else "none",
        canSendRealMail=mail.can_send_real_mail,
        canChargeRealMoney=bool(payments and payments.can_charge_real_money),
        contentVersion=content_version(),
    )


@router.post(
    "/addresses/verify",
    response_model=schemas.VerifyAddressResponse,
    dependencies=[Depends(rate_limit("verify", "rate_limit_per_ip_per_hour", 3600))],
)
def verify_address(
    payload: schemas.VerifyAddressRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
    mail: MailProvider = Depends(mail_provider_dep),
) -> schemas.VerifyAddressResponse:
    try:
        address = validate_us_address(payload.address.to_domain())
    except AddressError as exc:
        raise HTTPException(
            status_code=400, detail={"code": "invalid_address", "detail": str(exc)}
        ) from exc

    hashed = address_hash(address, settings.address_pepper)
    suppressed = mailing.is_suppressed(db, hashed)
    ends = mailing.cooldown_until(db, hashed, settings)

    try:
        verification = mail.verify_address(address)
    except MailProviderError as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "provider_unavailable", "detail": str(exc)},
        ) from exc

    return schemas.VerifyAddressResponse(
        status=verification.status.value,
        message=(
            "This address has asked not to receive letters from this service."
            if suppressed
            else verification.message
        ),
        standardized=(
            schemas.AddressIn.from_domain(verification.standardized)
            if verification.standardized
            else None
        ),
        suppressed=suppressed,
        cooldownUntil=ends.date().isoformat() if ends else None,
    )


@router.post(
    "/letters",
    response_model=schemas.LetterOut,
    dependencies=[Depends(rate_limit("draft", "rate_limit_drafts_per_ip_per_day", 86400))],
)
def create_letter(
    payload: schemas.CreateLetterRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
    hashed_client: str = Depends(client_hash),
) -> schemas.LetterOut:
    verify_bot_token(payload.botToken, settings)

    try:
        address = validate_us_address(payload.address.to_domain())
    except AddressError as exc:
        raise HTTPException(
            status_code=400, detail={"code": "invalid_address", "detail": str(exc)}
        ) from exc

    try:
        letter, quote = mailing.create_draft(
            db,
            settings=settings,
            address=address,
            observations=list(payload.observations),
            note=payload.note,
            suggestions=list(payload.suggestions),
            client_fingerprint=payload.letterFingerprint or None,
            sender_email=str(payload.senderEmail or ""),
            client_hash=hashed_client,
        )
    except mailing.ServiceError as exc:
        raise _service_error(exc) from exc

    db.commit()
    db.refresh(letter)

    return schemas.LetterOut(
        id=letter.id,
        status=letter.status,
        letterText=letter.letter_text,
        letterFingerprint=letter.letter_fingerprint,
        address=schemas.AddressIn.from_domain(mailing.recipient_address(letter)),
        quote=_quote_out(quote),
    )


@router.post("/letters/{letter_id}/checkout", response_model=schemas.CheckoutOut)
def checkout(
    letter_id: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
    payments: PaymentProvider | None = Depends(payment_provider_dep),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> schemas.CheckoutOut:
    if payments is None:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "payments_disabled",
                "detail": "This deployment cannot take payments, so it cannot mail letters.",
            },
        )
    if not idempotency_key or len(idempotency_key) > 120:
        raise HTTPException(
            status_code=400,
            detail={"code": "idempotency_required", "detail": "An Idempotency-Key header is required."},
        )

    letter = db.get(Letter, letter_id)
    if letter is None:
        raise HTTPException(status_code=404, detail={"code": "not_found", "detail": "No such letter."})

    try:
        result = mailing.start_checkout(
            db,
            settings=settings,
            payments=payments,
            letter=letter,
            idempotency_key=idempotency_key,
        )
    except mailing.ServiceError as exc:
        raise _service_error(exc) from exc
    except PaymentError as exc:
        raise HTTPException(
            status_code=502, detail={"code": "payment_provider_error", "detail": str(exc)}
        ) from exc

    db.commit()
    return schemas.CheckoutOut(**result)


@router.get("/letters/{letter_id}/status", response_model=schemas.LetterStatusOut)
def letter_status(letter_id: str, db: Session = Depends(get_db)) -> schemas.LetterStatusOut:
    letter = db.get(Letter, letter_id)
    if letter is None:
        raise HTTPException(status_code=404, detail={"code": "not_found", "detail": "No such letter."})

    return schemas.LetterStatusOut(
        id=letter.id,
        status=letter.status,
        statusLabel=STATUS_LABELS.get(letter.status, letter.status),
        statusDetail=letter.status_detail,
        submittedAt=letter.submitted_at.date().isoformat() if letter.submitted_at else None,
        expectedDeliveryDate=letter.expected_delivery_date,
        providerReference=letter.provider_letter_id,
        amountPaidCents=letter.amount_paid_cents,
    )


@router.post(
    "/suppressions",
    response_model=schemas.OkResponse,
    dependencies=[Depends(rate_limit("suppress", "rate_limit_per_ip_per_hour", 3600))],
)
def create_suppression(
    payload: schemas.SuppressionRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
) -> schemas.OkResponse:
    """Add an address to the do-not-mail list.

    Unauthenticated on purpose. The only thing this endpoint can do is prevent
    letters, so the worst an abuser achieves is stopping mail to an address —
    which is the outcome we would rather err towards.
    """
    try:
        address = validate_us_address(payload.address.to_domain())
    except AddressError as exc:
        raise HTTPException(
            status_code=400, detail={"code": "invalid_address", "detail": str(exc)}
        ) from exc

    mailing.add_suppression(
        db, address_hash(address, settings.address_pepper), source="web", note=payload.reason
    )
    db.commit()
    return schemas.OkResponse()


# --------------------------------------------------------------------------
# webhooks
# --------------------------------------------------------------------------


@router.post("/webhooks/payments")
async def payments_webhook(
    request: Request,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
    payments: PaymentProvider | None = Depends(payment_provider_dep),
) -> Response:
    if payments is None:
        raise HTTPException(status_code=404, detail={"code": "not_found", "detail": "Not enabled."})

    body = await request.body()
    try:
        event = payments.parse_webhook(dict(request.headers), body)
    except PaymentError as exc:
        # A bad signature is the one webhook case that must not return 200.
        log.warning("rejected payment webhook: %s", exc)
        raise HTTPException(
            status_code=400, detail={"code": "invalid_signature", "detail": "Signature check failed."}
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail={"code": "invalid_payload", "detail": "Malformed payload."}
        ) from exc

    letter = mailing.handle_payment_event(db, settings=settings, event=event)
    db.commit()

    # Mail after responding: the provider wants a fast 200, and the submission
    # is idempotent and independently retried, so nothing is lost if this task
    # never runs.
    if letter is not None and letter.status == LetterStatus.PAID.value:
        background.add_task(_submit_in_background, letter.id)

    return Response(status_code=200, content='{"received":true}', media_type="application/json")


@router.post("/webhooks/mail")
async def mail_webhook(
    request: Request,
    db: Session = Depends(get_db),
    mail: MailProvider = Depends(mail_provider_dep),
) -> Response:
    body = await request.body()
    try:
        event = mail.parse_webhook(dict(request.headers), body)
    except MailProviderError as exc:
        log.warning("rejected mail webhook: %s", exc)
        raise HTTPException(
            status_code=400, detail={"code": "invalid_signature", "detail": "Signature check failed."}
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail={"code": "invalid_payload", "detail": "Malformed payload."}
        ) from exc

    mailing.handle_mail_event(db, event=event)
    db.commit()
    return Response(status_code=200, content='{"received":true}', media_type="application/json")


def _submit_in_background(letter_id: str) -> None:
    settings = settings_dep()
    mail, payments = get_providers()
    with session_scope() as db:
        letter = db.get(Letter, letter_id)
        if letter is None:
            return
        try:
            mailing.submit_letter(
                db, settings=settings, mail=mail, payments=payments, letter=letter
            )
        except Exception:  # noqa: BLE001 - background tasks must not crash the worker
            log.exception("submission failed for letter %s", letter_id)


def _quote_out(quote) -> schemas.QuoteOut:
    return schemas.QuoteOut(
        currency=quote.currency,
        totalCents=quote.total_cents,
        lines=[schemas.QuoteLineOut(label=line.label, cents=line.cents) for line in quote.lines],
        deliveryEstimate=quote.delivery_estimate,
        disclaimer=quote.disclaimer,
    )
