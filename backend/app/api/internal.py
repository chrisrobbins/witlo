"""Internal operations, driven by a scheduler rather than a browser.

On a serverless host there is no worker process and no shell, so the two
recurring jobs from the deployment guide — submit letters that were paid for but
not yet handed to the printer, and erase personal data past its retention date —
run as HTTP endpoints hit by a cron. A one-shot migration endpoint is here for
the same reason: `alembic upgrade head` with nowhere to SSH into.

Every route requires `Authorization: Bearer <CRON_SECRET>`. With no
`CRON_SECRET` configured the whole router 404s, so it cannot be probed on a
deployment that never meant to enable it. Vercel Cron sends this header
automatically when the project has a `CRON_SECRET` environment variable.
"""

from __future__ import annotations

import logging
import secrets

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import settings_dep
from app.core.config import Settings, get_settings
from app.db.session import get_db, session_scope
from app.providers.factory import get_providers
from app.services import mailing

log = logging.getLogger("app.internal")

router = APIRouter(prefix="/api/v1/internal", include_in_schema=False)


def _require_cron_secret(
    authorization: str = Header(default=""),
    settings: Settings = Depends(settings_dep),
) -> None:
    expected = settings.cron_secret
    if not expected:
        # Feature is off; do not reveal that these routes exist.
        raise HTTPException(status_code=404, detail={"code": "not_found", "detail": "Not found."})
    scheme, _, presented = authorization.partition(" ")
    if scheme != "Bearer" or not presented or not secrets.compare_digest(presented, expected):
        raise HTTPException(
            status_code=401, detail={"code": "unauthorized", "detail": "Bad or missing token."}
        )


@router.api_route(
    "/submit-pending", methods=["GET", "POST"], dependencies=[Depends(_require_cron_secret)]
)
def submit_pending(older_than_minutes: int = 5, db: Session = Depends(get_db)) -> dict:
    """Pick up letters stuck in `paid` or `submitting` and hand them to the
    provider. Idempotent: the provider's idempotency key is the letter id, so a
    letter that was in fact already submitted cannot get a second envelope."""
    settings = get_settings()
    mail, payments = get_providers()
    letters = mailing.find_retryable(db, older_than_minutes=older_than_minutes)
    submitted = 0
    for letter in letters:
        try:
            mailing.submit_letter(
                db, settings=settings, mail=mail, payments=payments, letter=letter
            )
            db.commit()
            submitted += 1
        except Exception:
            # One bad letter must not stop the rest of the batch.
            db.rollback()
            log.exception("submit-pending failed for letter %s", letter.id)
    return {"found": len(letters), "submitted": submitted}


@router.api_route(
    "/purge-expired", methods=["GET", "POST"], dependencies=[Depends(_require_cron_secret)]
)
def purge_expired() -> dict:
    """Blank the address, letter text and email on letters past retention. The
    row, the address hash and the outcome are kept."""
    with session_scope() as db:
        purged = mailing.purge_expired(db)
    return {"purged": purged}


@router.api_route("/migrate", methods=["GET", "POST"], dependencies=[Depends(_require_cron_secret)])
def migrate() -> dict:
    """`alembic upgrade head`, for hosts with no shell. Safe to call repeatedly."""
    from pathlib import Path

    from alembic import command
    from alembic.config import Config

    root = Path(__file__).resolve().parents[2]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))
    cfg.set_main_option("sqlalchemy.url", get_settings().database_url)
    command.upgrade(cfg, "head")
    return {"migrated": True}
