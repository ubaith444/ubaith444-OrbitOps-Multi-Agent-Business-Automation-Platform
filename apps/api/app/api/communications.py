import hashlib
import hmac
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.communication import classify_reply
from app.api.dependencies import current_user, require_roles
from app.core.config import settings
from app.core.database import get_db
from app.models import (
    AuditLog,
    CommunicationChannel,
    CommunicationMessage,
    Lead,
    MessageDirection,
    MessageEvent,
    MessageStatus,
    Report,
    Role,
    User,
    WorkflowRun,
)
from app.schemas import (
    CommunicationCreate,
    CommunicationRead,
    MessageEventRead,
    TimelineItem,
    WebhookEvent,
    WebhookResult,
)
from app.services.audit import audit
from app.services.communications import queue_and_deliver, record_message_event
from app.services.reports import render_executive_pdf

router = APIRouter()


@router.get("/communications", response_model=list[CommunicationRead], tags=["communications"])
async def list_communications(
    lead_id: UUID | None = None,
    channel: CommunicationChannel | None = None,
    message_status: MessageStatus | None = Query(default=None, alias="status"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
) -> list[CommunicationMessage]:
    query = select(CommunicationMessage).where(CommunicationMessage.tenant_id == user.tenant_id)
    if lead_id:
        query = query.where(CommunicationMessage.lead_id == lead_id)
    if channel:
        query = query.where(CommunicationMessage.channel == channel)
    if message_status:
        query = query.where(CommunicationMessage.status == message_status)
    query = query.order_by(CommunicationMessage.created_at.desc()).limit(200)
    return list((await db.scalars(query)).all())


@router.post(
    "/communications", response_model=CommunicationRead, status_code=201, tags=["communications"]
)
async def create_communication(
    payload: CommunicationCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(Role.ADMIN, Role.MANAGER)),
) -> CommunicationMessage:
    lead = await db.scalar(
        select(Lead).where(Lead.id == payload.lead_id, Lead.tenant_id == user.tenant_id)
    )
    if lead is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lead not found")
    message = CommunicationMessage(
        tenant_id=user.tenant_id,
        lead_id=lead.id,
        channel=payload.channel,
        provider=payload.provider,
        subject=payload.subject,
        body=payload.body,
    )
    db.add(message)
    await db.flush()
    await record_message_event(db, message, MessageStatus.DRAFT)
    await audit(
        db,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="communication.drafted",
        resource_type="communication_message",
        resource_id=str(message.id),
        details={"channel": message.channel.value},
    )
    await db.commit()
    await db.refresh(message)
    return message


@router.post(
    "/communications/{message_id}/approve",
    response_model=CommunicationRead,
    tags=["communications"],
)
async def approve_communication(
    message_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(Role.ADMIN, Role.MANAGER)),
) -> CommunicationMessage:
    message = await tenant_message(db, message_id, user.tenant_id)
    if message.status == MessageStatus.APPROVED:
        return message
    if message.status != MessageStatus.DRAFT:
        raise HTTPException(status.HTTP_409_CONFLICT, "Only drafts can be approved")
    await record_message_event(db, message, MessageStatus.APPROVED)
    await audit(
        db,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="communication.approved",
        resource_type="communication_message",
        resource_id=str(message.id),
    )
    await db.commit()
    await db.refresh(message)
    return message


@router.post(
    "/communications/{message_id}/send",
    response_model=CommunicationRead,
    tags=["communications"],
)
async def send_communication(
    message_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(Role.ADMIN, Role.MANAGER)),
) -> CommunicationMessage:
    message = await tenant_message(db, message_id, user.tenant_id)
    try:
        return await queue_and_deliver(db, message, user.id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc


@router.post(
    "/communications/{message_id}/retry",
    response_model=CommunicationRead,
    tags=["communications"],
)
async def retry_communication(
    message_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(Role.ADMIN, Role.MANAGER)),
) -> CommunicationMessage:
    message = await tenant_message(db, message_id, user.tenant_id)
    if message.status == MessageStatus.DEAD_LETTER:
        raise HTTPException(status.HTTP_409_CONFLICT, "Message is in the dead-letter queue")
    if message.status != MessageStatus.FAILED:
        raise HTTPException(status.HTTP_409_CONFLICT, "Only failed messages can be retried")
    return await queue_and_deliver(db, message, user.id)


@router.get(
    "/communications/{message_id}/events",
    response_model=list[MessageEventRead],
    tags=["communications"],
)
async def list_message_events(
    message_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
) -> list[MessageEvent]:
    await tenant_message(db, message_id, user.tenant_id)
    query = (
        select(MessageEvent)
        .where(MessageEvent.message_id == message_id, MessageEvent.tenant_id == user.tenant_id)
        .order_by(MessageEvent.occurred_at)
    )
    return list((await db.scalars(query)).all())


@router.get("/leads/{lead_id}/timeline", response_model=list[TimelineItem], tags=["leads"])
async def lead_timeline(
    lead_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
) -> list[TimelineItem]:
    lead = await db.scalar(select(Lead).where(Lead.id == lead_id, Lead.tenant_id == user.tenant_id))
    if lead is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lead not found")
    audit_items = list(
        (
            await db.scalars(
                select(AuditLog).where(
                    AuditLog.tenant_id == user.tenant_id,
                    AuditLog.resource_id == str(lead_id),
                )
            )
        ).all()
    )
    runs = list(
        (
            await db.scalars(
                select(WorkflowRun).where(
                    WorkflowRun.tenant_id == user.tenant_id, WorkflowRun.lead_id == lead_id
                )
            )
        ).all()
    )
    events = list(
        (
            await db.scalars(
                select(MessageEvent).where(
                    MessageEvent.tenant_id == user.tenant_id, MessageEvent.lead_id == lead_id
                )
            )
        ).all()
    )
    timeline = [
        TimelineItem(
            id=str(item.id),
            kind="audit",
            label=item.action.replace(".", " ").title(),
            status="completed",
            timestamp=item.created_at,
            details=item.details,
        )
        for item in audit_items
    ]
    for run in runs:
        for index, item in enumerate(run.state_snapshot.get("events", [])):
            timeline.append(
                TimelineItem(
                    id=f"{run.id}-{index}",
                    kind="agent",
                    label=f"{item.get('agent', 'Agent').title()} Agent",
                    status="completed",
                    timestamp=datetime.fromisoformat(item["at"]),
                    details={"message": item.get("message", "")},
                )
            )
    timeline.extend(
        TimelineItem(
            id=str(item.id),
            kind=item.channel.value,
            label=f"{item.channel.value.title()} {item.status.value.replace('_', ' ').title()}",
            status=item.status.value,
            timestamp=item.occurred_at,
            details=item.metadata_json,
        )
        for item in events
    )
    return sorted(
        timeline,
        key=lambda item: (
            item.timestamp if item.timestamp.tzinfo else item.timestamp.replace(tzinfo=UTC)
        ),
    )


async def tenant_message(
    db: AsyncSession, message_id: UUID, tenant_id: UUID
) -> CommunicationMessage:
    message = await db.scalar(
        select(CommunicationMessage).where(
            CommunicationMessage.id == message_id,
            CommunicationMessage.tenant_id == tenant_id,
        )
    )
    if message is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Communication not found")
    return message


def verify_webhook_signature(raw: bytes, timestamp: str, signature: str, secret: str) -> str:
    try:
        sent_at = datetime.fromtimestamp(int(timestamp), UTC)
    except (ValueError, OSError) as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid webhook timestamp") from exc
    if abs((datetime.now(UTC) - sent_at).total_seconds()) > settings.webhook_tolerance_seconds:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Webhook timestamp outside tolerance")
    digest = hashlib.sha256(raw).hexdigest()
    expected = hmac.new(
        secret.encode(), timestamp.encode() + b"." + raw, hashlib.sha256
    ).hexdigest()
    supplied = signature.removeprefix("sha256=")
    if not hmac.compare_digest(expected, supplied):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid webhook signature")
    return digest


@router.post("/webhooks/{channel}", response_model=WebhookResult, tags=["webhooks"])
async def communication_webhook(
    channel: CommunicationChannel,
    request: Request,
    db: AsyncSession = Depends(get_db),
    webhook_timestamp: str = Header(alias="X-OrbitOps-Timestamp"),
    webhook_signature: str = Header(alias="X-OrbitOps-Signature"),
) -> WebhookResult:
    raw = await request.body()
    secret = (
        settings.email_webhook_secret
        if channel == CommunicationChannel.EMAIL
        else settings.whatsapp_webhook_secret
    )
    if not secret:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Webhook channel not configured")
    digest = verify_webhook_signature(raw, webhook_timestamp, webhook_signature, secret)
    try:
        payload = WebhookEvent.model_validate_json(raw)
    except ValidationError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid webhook payload"
        ) from exc
    allowed = {
        CommunicationChannel.EMAIL: {
            MessageStatus.SENT,
            MessageStatus.DELIVERED,
            MessageStatus.OPENED,
            MessageStatus.CLICKED,
            MessageStatus.REPLIED,
            MessageStatus.BOUNCED,
            MessageStatus.FAILED,
        },
        CommunicationChannel.WHATSAPP: {
            MessageStatus.SENT,
            MessageStatus.DELIVERED,
            MessageStatus.READ,
            MessageStatus.REPLIED,
            MessageStatus.FAILED,
        },
    }
    if payload.status not in allowed[channel]:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Unsupported provider status")
    existing = await db.scalar(
        select(MessageEvent).where(MessageEvent.provider_event_id == payload.event_id)
    )
    if existing:
        if existing.payload_digest != digest:
            raise HTTPException(status.HTTP_409_CONFLICT, "Webhook event replay conflict")
        message = await db.get(CommunicationMessage, existing.message_id)
        return WebhookResult(duplicate=True, message_id=message.id, status=message.status)
    message = await db.scalar(
        select(CommunicationMessage).where(
            CommunicationMessage.provider_message_id == payload.message_id,
            CommunicationMessage.channel == channel,
        )
    )
    if message is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Provider message not found")
    await record_message_event(
        db,
        message,
        payload.status,
        event_id=payload.event_id,
        occurred_at=payload.timestamp,
        metadata=payload.metadata,
        payload_digest=digest,
    )
    await audit(
        db,
        tenant_id=message.tenant_id,
        actor_id=None,
        action=f"communication.{payload.status.value}",
        resource_type="communication_message",
        resource_id=str(message.id),
        details={"channel": channel.value, "provider_event_id": payload.event_id},
    )
    if payload.status == MessageStatus.REPLIED:
        if not payload.reply_text:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Reply text is required")
        lead = await db.get(Lead, message.lead_id)
        classification = classify_reply(payload.reply_text, lead.score)
        inbound = CommunicationMessage(
            tenant_id=message.tenant_id,
            lead_id=message.lead_id,
            run_id=message.run_id,
            channel=channel,
            direction=MessageDirection.INBOUND,
            provider=message.provider,
            provider_message_id=f"{payload.message_id}:reply:{payload.event_id}",
            subject=f"Re: {message.subject}" if message.subject else None,
            body=payload.reply_text,
            status=MessageStatus.REPLIED,
            classification=classification,
            replied_at=payload.timestamp,
        )
        db.add(inbound)
        lead.score = classification["lead_score"]
        lead.qualification_status = "customer-replied"
        lead.recommended_action = classification["next_action"]
        lead.attributes = {**lead.attributes, "response_intent": classification["intent"]}
        if message.run_id:
            run = await db.get(WorkflowRun, message.run_id)
            report = await db.scalar(select(Report).where(Report.run_id == message.run_id))
            if run and report:
                state = dict(run.state_snapshot)
                report_data = dict(state.get("report", {}))
                report_data["executive_summary"] = (
                    f"{report_data.get('executive_summary', '')} Customer replied with "
                    f"{classification['intent']} intent."
                ).strip()
                report_data["score"] = classification["lead_score"]
                report_data["recommended_action"] = classification["next_action"]
                report_data["customer_response"] = payload.reply_text
                state["report"] = report_data
                run.state_snapshot = state
                content = render_executive_pdf(report_data)
                report.content = content
                report.size_bytes = len(content)
                report.metadata_json = {
                    **report.metadata_json,
                    "response_intent": classification["intent"],
                    "reply_processed_at": payload.timestamp.isoformat(),
                }
                await audit(
                    db,
                    tenant_id=message.tenant_id,
                    actor_id=None,
                    action="report.regenerated_from_reply",
                    resource_type="report",
                    resource_id=str(report.id),
                )
        await db.flush()
        await audit(
            db,
            tenant_id=message.tenant_id,
            actor_id=None,
            action="communication.reply_classified",
            resource_type="lead",
            resource_id=str(lead.id),
            details=classification,
        )
    await db.commit()
    return WebhookResult(message_id=message.id, status=message.status)
