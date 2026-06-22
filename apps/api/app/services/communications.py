import hashlib
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import CommunicationMessage, MessageEvent, MessageStatus
from app.services.audit import audit

TERMINAL_FAILURES = {MessageStatus.BOUNCED, MessageStatus.DEAD_LETTER}
STATUS_RANK = {
    MessageStatus.DRAFT: 0,
    MessageStatus.APPROVED: 1,
    MessageStatus.QUEUED: 2,
    MessageStatus.SENT: 3,
    MessageStatus.DELIVERED: 4,
    MessageStatus.READ: 5,
    MessageStatus.OPENED: 5,
    MessageStatus.CLICKED: 6,
    MessageStatus.REPLIED: 7,
}


async def record_message_event(
    db: AsyncSession,
    message: CommunicationMessage,
    event_status: MessageStatus,
    *,
    event_id: str | None = None,
    occurred_at: datetime | None = None,
    metadata: dict | None = None,
    payload_digest: str | None = None,
) -> MessageEvent:
    timestamp = occurred_at or datetime.now(UTC)
    event = MessageEvent(
        tenant_id=message.tenant_id,
        lead_id=message.lead_id,
        message_id=message.id,
        channel=message.channel,
        provider=message.provider,
        provider_event_id=event_id or f"internal-{uuid4()}",
        status=event_status,
        occurred_at=timestamp,
        metadata_json=metadata or {},
        payload_digest=payload_digest or hashlib.sha256(str(uuid4()).encode()).hexdigest(),
    )
    db.add(event)
    current_rank = STATUS_RANK.get(message.status, -1)
    incoming_rank = STATUS_RANK.get(event_status, -1)
    if event_status in TERMINAL_FAILURES or event_status == MessageStatus.FAILED:
        message.status = event_status
    elif incoming_rank >= current_rank:
        message.status = event_status
    if event_status == MessageStatus.SENT:
        message.sent_at = timestamp
    elif event_status == MessageStatus.DELIVERED:
        message.delivered_at = timestamp
    elif event_status in {MessageStatus.READ, MessageStatus.OPENED}:
        message.read_at = timestamp
    elif event_status == MessageStatus.REPLIED:
        message.replied_at = timestamp
    await db.flush()
    return event


async def queue_and_deliver(
    db: AsyncSession, message: CommunicationMessage, actor_id=None
) -> CommunicationMessage:
    if message.status not in {MessageStatus.APPROVED, MessageStatus.FAILED}:
        raise ValueError("Only approved or failed messages can be sent")
    message.attempt_count += 1
    message.last_error = None
    await record_message_event(db, message, MessageStatus.QUEUED)
    try:
        if message.provider == "outage":
            raise ConnectionError("Communication provider is unavailable")
        if message.provider != "mock" and not settings.delivery_enabled:
            raise PermissionError("External delivery is disabled")
        message.provider_message_id = message.provider_message_id or f"{message.provider}-{uuid4()}"
        await record_message_event(db, message, MessageStatus.SENT)
        await audit(
            db,
            tenant_id=message.tenant_id,
            actor_id=actor_id,
            action="communication.sent",
            resource_type="communication_message",
            resource_id=str(message.id),
            details={"channel": message.channel.value, "provider": message.provider},
        )
    except Exception as exc:
        message.last_error = str(exc)
        if message.attempt_count >= settings.message_max_attempts:
            await record_message_event(db, message, MessageStatus.DEAD_LETTER)
        else:
            message.next_retry_at = datetime.now(UTC) + timedelta(
                minutes=2 ** (message.attempt_count - 1)
            )
            await record_message_event(db, message, MessageStatus.FAILED)
        await audit(
            db,
            tenant_id=message.tenant_id,
            actor_id=actor_id,
            action="communication.delivery_failed",
            resource_type="communication_message",
            resource_id=str(message.id),
            details={"error": message.last_error, "attempt": message.attempt_count},
        )
    await db.commit()
    await db.refresh(message)
    return message


async def process_due_retries(db: AsyncSession, limit: int = 20) -> int:
    query = (
        select(CommunicationMessage)
        .where(
            CommunicationMessage.status == MessageStatus.FAILED,
            CommunicationMessage.next_retry_at <= datetime.now(UTC),
        )
        .order_by(CommunicationMessage.next_retry_at)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    messages = list((await db.scalars(query)).all())
    for message in messages:
        await queue_and_deliver(db, message)
    return len(messages)
