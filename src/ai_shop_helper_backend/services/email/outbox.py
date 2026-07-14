import asyncio
import json
import logging
from datetime import timedelta

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from ai_shop_helper_backend.core.config import settings
from ai_shop_helper_backend.core.db import AsyncSessionLocal
from ai_shop_helper_backend.core.email_types import EmailType
from ai_shop_helper_backend.core.utils import get_datetime_utc
from ai_shop_helper_backend.models.auth_email import EmailOutbox
from ai_shop_helper_backend.services.email.provider import EmailDeliveryError, notifuse_provider

logger = logging.getLogger(__name__)


async def enqueue(
    session: AsyncSession,
    *,
    email_type: EmailType,
    to_email: str,
    first_name: str | None,
    locale: str,
    data: dict,
    external_id: str,
) -> EmailOutbox:
    """Add an email to the outbox within the caller's transaction.

    Returns the existing row if external_id is already present (idempotent).
    Does not commit or rollback — the caller's transaction owns that.
    """
    existing_result = await session.exec(
        select(EmailOutbox).where(EmailOutbox.external_id == external_id)
    )
    existing = existing_result.first()
    if existing is not None:
        return existing

    row = EmailOutbox(
        email_type=email_type.value,
        to_email=to_email,
        first_name=first_name,
        locale=locale,
        data_json=json.dumps(data),
        external_id=external_id,
        status="pending",
        next_attempt_at=get_datetime_utc(),
    )
    session.add(row)
    await session.flush()
    return row


def _backoff_seconds(attempts: int) -> int:
    """Exponential backoff capped at one hour."""
    return min(60 * (2 ** (attempts - 1)), 3600)


async def deliver_one(session: AsyncSession, row: EmailOutbox) -> None:
    """Attempt delivery of a single outbox row; mutates row state in place."""
    try:
        await notifuse_provider.send(
            to_email=row.to_email,
            first_name=row.first_name or "",
            locale=row.locale,
            template_slug=row.email_type,
            data=json.loads(row.data_json),
            external_id=row.external_id,
        )
        row.status = "sent"
        row.sent_at = get_datetime_utc()
        row.last_error = None
    except EmailDeliveryError as exc:
        row.attempts += 1
        row.last_error = str(exc)[:2048]
        if row.attempts >= settings.EMAIL_MAX_ATTEMPTS:
            row.status = "failed"
            logger.error(
                "email permanently failed after %d attempts: %s — %s",
                row.attempts,
                row.external_id,
                row.last_error,
            )
        else:
            row.next_attempt_at = get_datetime_utc() + timedelta(
                seconds=_backoff_seconds(row.attempts)
            )
    session.add(row)


async def _drain_once() -> int:
    """Fetch and attempt delivery of due pending rows; commits on completion."""
    async with AsyncSessionLocal() as session:
        result = await session.exec(
            select(EmailOutbox)
            .where(
                EmailOutbox.status == "pending",
                EmailOutbox.next_attempt_at <= get_datetime_utc(),
            )
            .order_by(EmailOutbox.created_at)
            .with_for_update(skip_locked=True)
            .limit(20)
        )
        rows = result.all()
        for row in rows:
            await deliver_one(session, row)
        await session.commit()
        return len(rows)


async def run_poller() -> None:
    """Long-running asyncio task that drains the email outbox on each tick."""
    while True:
        if not settings.NOTIFUSE_API_KEY:
            await asyncio.sleep(settings.EMAIL_POLL_INTERVAL_S)
            continue
        try:
            await _drain_once()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("email poller iteration failed")
        await asyncio.sleep(settings.EMAIL_POLL_INTERVAL_S)
