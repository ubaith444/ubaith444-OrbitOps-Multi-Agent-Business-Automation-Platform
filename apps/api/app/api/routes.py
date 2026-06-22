import hashlib
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.ai_operations import router as ai_operations_router
from app.api.communications import router as communication_router
from app.api.dependencies import current_user, require_roles
from app.core.database import get_db
from app.core.security import TokenType, create_token, decode_token, hash_password, verify_password
from app.models import (
    AgentExecution,
    Approval,
    ApprovalStatus,
    AuditLog,
    CommunicationChannel,
    CommunicationMessage,
    Lead,
    LeadPriority,
    MemoryRecord,
    MessageEvent,
    MessageStatus,
    ModelRoute,
    PromptVersion,
    Report,
    Role,
    RunStatus,
    Tenant,
    User,
    WorkflowRun,
)
from app.schemas import (
    AgentMetric,
    ApprovalDecision,
    ApprovalRead,
    AuditLogRead,
    ChartPoint,
    CommunicationAnalytics,
    DashboardSummary,
    LeadCreate,
    LeadRead,
    LeadUpdate,
    LoginRequest,
    RefreshRequest,
    ReportPreview,
    ReportRead,
    TenantSettings,
    TenantSettingsUpdate,
    TokenPair,
    UserCreate,
    UserRead,
    UserUpdate,
    WorkflowRead,
    WorkflowStart,
)
from app.services.audit import audit
from app.services.communications import record_message_event
from app.services.orchestration import execute_run, generate_report, initial_state

router = APIRouter()
router.include_router(ai_operations_router)
router.include_router(communication_router)


@router.post("/auth/login", response_model=TokenPair, tags=["authentication"])
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenPair:
    user = await db.scalar(
        select(User)
        .join(Tenant, Tenant.id == User.tenant_id)
        .where(
            User.email == payload.email,
            User.active.is_(True),
            Tenant.slug == payload.workspace,
            Tenant.active.is_(True),
        )
    )
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    await audit(
        db,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="auth.login",
        resource_type="user",
        resource_id=str(user.id),
    )
    await db.commit()
    return TokenPair(
        access_token=create_token(user.id, user.tenant_id, user.role.value, TokenType.ACCESS),
        refresh_token=create_token(user.id, user.tenant_id, user.role.value, TokenType.REFRESH),
    )


@router.post("/auth/refresh", response_model=TokenPair, tags=["authentication"])
async def refresh(payload: RefreshRequest, db: AsyncSession = Depends(get_db)) -> TokenPair:
    try:
        claims = decode_token(payload.refresh_token, TokenType.REFRESH)
        user_id, tenant_id = UUID(claims["sub"]), UUID(claims["tenant"])
    except Exception as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Invalid or expired refresh token"
        ) from exc
    user = await db.scalar(
        select(User).where(User.id == user_id, User.tenant_id == tenant_id, User.active.is_(True))
    )
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User is inactive or missing")
    return TokenPair(
        access_token=create_token(user.id, user.tenant_id, user.role.value, TokenType.ACCESS),
        refresh_token=create_token(user.id, user.tenant_id, user.role.value, TokenType.REFRESH),
    )


@router.get("/auth/me", response_model=UserRead, tags=["authentication"])
async def me(user: User = Depends(current_user)) -> User:
    return user


@router.post("/leads", response_model=LeadRead, status_code=201, tags=["leads"])
async def create_lead(
    payload: LeadCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(Role.ADMIN, Role.MANAGER)),
) -> Lead:
    lead = Lead(
        tenant_id=user.tenant_id,
        owner_id=user.id,
        **payload.model_dump(mode="json"),
    )
    db.add(lead)
    await db.flush()
    await audit(
        db,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="lead.created",
        resource_type="lead",
        resource_id=str(lead.id),
    )
    await db.commit()
    await db.refresh(lead)
    return lead


@router.get("/leads", response_model=list[LeadRead], tags=["leads"])
async def list_leads(
    priority: LeadPriority | None = None,
    search: str | None = Query(default=None, max_length=120),
    qualification_status: str | None = Query(default=None, max_length=120),
    include_archived: bool = False,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
) -> list[Lead]:
    query = select(Lead).where(Lead.tenant_id == user.tenant_id).order_by(Lead.created_at.desc())
    if priority:
        query = query.where(Lead.priority == priority)
    leads = list((await db.scalars(query.limit(200))).all())
    if not include_archived:
        leads = [lead for lead in leads if not lead.attributes.get("archived", False)]
    if search:
        term = search.casefold()
        leads = [
            lead
            for lead in leads
            if term in lead.name.casefold() or term in lead.company.casefold()
        ]
    if qualification_status:
        leads = [lead for lead in leads if lead.qualification_status == qualification_status]
    return leads[offset : offset + limit]


@router.get("/leads/{lead_id}", response_model=LeadRead, tags=["leads"])
async def get_lead(
    lead_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
) -> Lead:
    lead = await db.scalar(select(Lead).where(Lead.id == lead_id, Lead.tenant_id == user.tenant_id))
    if not lead:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lead not found")
    return lead


@router.patch("/leads/{lead_id}", response_model=LeadRead, tags=["leads"])
async def update_lead(
    lead_id: UUID,
    payload: LeadUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(Role.ADMIN, Role.MANAGER)),
) -> Lead:
    lead = await db.scalar(select(Lead).where(Lead.id == lead_id, Lead.tenant_id == user.tenant_id))
    if lead is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lead not found")
    changes = payload.model_dump(exclude_unset=True, mode="json")
    for field, value in changes.items():
        setattr(lead, field, value)
    await audit(
        db,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="lead.updated",
        resource_type="lead",
        resource_id=str(lead.id),
        details={"fields": sorted(changes)},
    )
    await db.commit()
    await db.refresh(lead)
    return lead


@router.delete("/leads/{lead_id}", status_code=204, tags=["leads"])
async def archive_lead(
    lead_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(Role.ADMIN, Role.MANAGER)),
) -> Response:
    lead = await db.scalar(select(Lead).where(Lead.id == lead_id, Lead.tenant_id == user.tenant_id))
    if lead is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lead not found")
    lead.attributes = {
        **lead.attributes,
        "archived": True,
        "archived_at": datetime.now(UTC).isoformat(),
    }
    await audit(
        db,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="lead.archived",
        resource_type="lead",
        resource_id=str(lead.id),
    )
    await db.commit()
    return Response(status_code=204)


@router.post("/workflows", response_model=WorkflowRead, status_code=202, tags=["workflows"])
async def start_workflow(
    payload: WorkflowStart,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(Role.ADMIN, Role.MANAGER)),
) -> WorkflowRun:
    lead = await db.scalar(
        select(Lead).where(Lead.id == payload.lead_id, Lead.tenant_id == user.tenant_id)
    )
    if not lead:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lead not found")
    run = WorkflowRun(
        tenant_id=user.tenant_id,
        lead_id=lead.id,
        initiated_by=user.id,
        graph_thread_id=str(uuid4()),
    )
    db.add(run)
    await db.flush()
    await audit(
        db,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="workflow.started",
        resource_type="workflow_run",
        resource_id=str(run.id),
    )
    await db.commit()
    state = initial_state(run, lead)
    configured_routes = list(
        (
            await db.scalars(
                select(ModelRoute).where(
                    ModelRoute.tenant_id == user.tenant_id, ModelRoute.active.is_(True)
                )
            )
        ).all()
    )
    state["model_routes"] = {
        route.agent_name: [
            {"provider": route.primary_provider, "model": route.primary_model},
            *route.fallback_order,
        ]
        for route in configured_routes
    }
    active_prompts = list(
        (
            await db.scalars(
                select(PromptVersion).where(
                    PromptVersion.tenant_id == user.tenant_id,
                    PromptVersion.active.is_(True),
                )
            )
        ).all()
    )
    state["prompt_templates"] = {item.agent_name: item.content for item in active_prompts}
    run = await execute_run(db, run, state)
    if run.state_snapshot.get("lead_score") is not None:
        lead.score = run.state_snapshot["lead_score"]
        lead.priority = LeadPriority(run.state_snapshot["priority"])
        lead.qualification_status = run.state_snapshot["qualification_status"]
        lead.recommended_action = run.state_snapshot["recommended_action"]
        await db.commit()
    return run


@router.get("/workflows", response_model=list[WorkflowRead], tags=["workflows"])
async def list_workflows(
    lead_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
) -> list[WorkflowRun]:
    query = select(WorkflowRun).where(WorkflowRun.tenant_id == user.tenant_id)
    if lead_id:
        query = query.where(WorkflowRun.lead_id == lead_id)
    query = query.order_by(WorkflowRun.created_at.desc()).limit(100)
    return list((await db.scalars(query)).all())


@router.get("/approvals", response_model=list[ApprovalRead], tags=["approvals"])
async def list_approvals(
    approval_status: ApprovalStatus | None = Query(default=None, alias="status"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
) -> list[Approval]:
    query = select(Approval).where(Approval.tenant_id == user.tenant_id)
    if approval_status:
        query = query.where(Approval.status == approval_status)
    query = query.order_by(Approval.created_at.desc()).limit(100)
    return list((await db.scalars(query)).all())


@router.post("/approvals/{approval_id}/decision", response_model=WorkflowRead, tags=["approvals"])
async def decide_approval(
    approval_id: UUID,
    payload: ApprovalDecision,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(Role.ADMIN, Role.MANAGER)),
) -> WorkflowRun:
    approval = await db.scalar(
        select(Approval)
        .where(
            Approval.id == approval_id,
            Approval.tenant_id == user.tenant_id,
        )
        .with_for_update()
    )
    if not approval:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Approval not found")
    run = await db.scalar(
        select(WorkflowRun).where(
            WorkflowRun.id == approval.run_id, WorkflowRun.tenant_id == user.tenant_id
        )
    )
    action = payload.action or ("approve" if payload.approved else "reject")
    desired_status = {
        "approve": ApprovalStatus.APPROVED,
        "reject": ApprovalStatus.REJECTED,
        "request_changes": ApprovalStatus.CHANGES_REQUESTED,
    }[action]
    if approval.status != ApprovalStatus.PENDING:
        if approval.status == desired_status:
            return run
        raise HTTPException(status.HTTP_409_CONFLICT, "Approval already has a different decision")
    approval.status = desired_status
    approval.decided_by = user.id
    approval.decision_note = payload.note
    approval.decided_at = datetime.now(UTC)
    communication = await db.scalar(
        select(CommunicationMessage).where(CommunicationMessage.approval_id == approval.id)
    )
    if communication:
        await record_message_event(
            db,
            communication,
            MessageStatus.APPROVED if action == "approve" else MessageStatus.FAILED,
            metadata={"approval_action": action, "note": payload.note},
        )
    await audit(
        db,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action=f"approval.{approval.status.value}",
        resource_type="approval",
        resource_id=str(approval.id),
    )
    if action != "approve":
        run.status = RunStatus.CANCELLED
        if action == "request_changes":
            run.error = "Changes requested by reviewer"
        run.finished_at = datetime.now(UTC)
        await db.commit()
        return run
    state = dict(run.state_snapshot)
    approved = list(state.get("approved_actions", []))
    approved.append(approval.kind.value)
    state["approved_actions"] = list(dict.fromkeys(approved))
    state["pending_approval"] = None
    await db.commit()
    return await execute_run(db, run, state)


@router.post("/workflows/{run_id}/retry", response_model=WorkflowRead, tags=["workflows"])
async def retry_workflow(
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(Role.ADMIN, Role.MANAGER)),
) -> WorkflowRun:
    run = await db.scalar(
        select(WorkflowRun).where(
            WorkflowRun.id == run_id,
            WorkflowRun.tenant_id == user.tenant_id,
            WorkflowRun.status == RunStatus.FAILED,
        )
    )
    if not run:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Failed workflow not found")
    await audit(
        db,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="workflow.retry_requested",
        resource_type="workflow_run",
        resource_id=str(run.id),
    )
    await db.commit()
    return await execute_run(db, run, dict(run.state_snapshot))


@router.get("/reports", response_model=list[ReportRead], tags=["reports"])
async def list_reports(
    lead_id: UUID | None = None,
    search: str | None = Query(default=None, max_length=120),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
) -> list[Report]:
    query = (
        select(Report)
        .where(Report.tenant_id == user.tenant_id)
        .order_by(Report.created_at.desc())
        .limit(100)
    )
    reports = list((await db.scalars(query)).all())
    if lead_id:
        reports = [report for report in reports if report.lead_id == lead_id]
    if search:
        term = search.casefold()
        reports = [report for report in reports if term in report.title.casefold()]
    return reports


@router.get("/reports/{report_id}/preview", response_model=ReportPreview, tags=["reports"])
async def preview_report(
    report_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
) -> ReportPreview:
    report = await db.scalar(
        select(Report).where(Report.id == report_id, Report.tenant_id == user.tenant_id)
    )
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found")
    run = await db.scalar(
        select(WorkflowRun).where(
            WorkflowRun.id == report.run_id, WorkflowRun.tenant_id == user.tenant_id
        )
    )
    return ReportPreview(
        id=report.id,
        title=report.title,
        lead_id=report.lead_id,
        report=dict(run.state_snapshot.get("report", {})) if run else {},
        metadata=report.metadata_json,
    )


@router.post("/reports/{report_id}/regenerate", response_model=ReportRead, tags=["reports"])
async def regenerate_report(
    report_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(Role.ADMIN, Role.MANAGER)),
) -> Report:
    report = await db.scalar(
        select(Report).where(Report.id == report_id, Report.tenant_id == user.tenant_id)
    )
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found")
    run = await db.scalar(
        select(WorkflowRun).where(
            WorkflowRun.id == report.run_id, WorkflowRun.tenant_id == user.tenant_id
        )
    )
    await db.delete(report)
    await db.flush()
    regenerated = await generate_report(db, run, dict(run.state_snapshot))
    await audit(
        db,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="report.regenerated",
        resource_type="report",
        resource_id=str(regenerated.id),
    )
    await db.commit()
    await db.refresh(regenerated)
    return regenerated


@router.get("/reports/{report_id}/download", tags=["reports"])
async def download_report(
    report_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
) -> Response:
    report = await db.scalar(
        select(Report).where(Report.id == report_id, Report.tenant_id == user.tenant_id)
    )
    if report is None or report.content is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found")
    return Response(
        content=report.content,
        media_type=report.content_type,
        headers={"Content-Disposition": f'attachment; filename="{report.file_name}"'},
    )


@router.get("/audit-logs", response_model=list[AuditLogRead], tags=["audit"])
async def list_audit_logs(
    limit: int = Query(100, ge=1, le=500),
    action: str | None = Query(default=None, max_length=120),
    resource_type: str | None = Query(default=None, max_length=80),
    actor_id: UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(Role.ADMIN, Role.MANAGER)),
) -> list[AuditLog]:
    query = select(AuditLog).where(AuditLog.tenant_id == user.tenant_id)
    if action:
        query = query.where(AuditLog.action == action)
    if resource_type:
        query = query.where(AuditLog.resource_type == resource_type)
    if actor_id:
        query = query.where(AuditLog.actor_id == actor_id)
    if date_from:
        query = query.where(AuditLog.created_at >= date_from)
    if date_to:
        query = query.where(AuditLog.created_at <= date_to)
    query = query.order_by(AuditLog.created_at.desc()).limit(limit)
    return list((await db.scalars(query)).all())


@router.get("/dashboard/summary", response_model=DashboardSummary, tags=["dashboard"])
async def dashboard(
    db: AsyncSession = Depends(get_db), user: User = Depends(current_user)
) -> DashboardSummary:
    tenant = user.tenant_id
    leads = list((await db.scalars(select(Lead).where(Lead.tenant_id == tenant))).all())
    leads = [lead for lead in leads if not lead.attributes.get("archived", False)]
    runs = list(
        (await db.scalars(select(WorkflowRun).where(WorkflowRun.tenant_id == tenant))).all()
    )
    approvals = list((await db.scalars(select(Approval).where(Approval.tenant_id == tenant))).all())
    reports = list((await db.scalars(select(Report).where(Report.tenant_id == tenant))).all())
    executions = list(
        (await db.scalars(select(AgentExecution).where(AgentExecution.tenant_id == tenant))).all()
    )
    messages = list(
        (
            await db.scalars(
                select(CommunicationMessage).where(CommunicationMessage.tenant_id == tenant)
            )
        ).all()
    )
    message_events = list(
        (await db.scalars(select(MessageEvent).where(MessageEvent.tenant_id == tenant))).all()
    )
    recent = list(
        (
            await db.scalars(
                select(AuditLog)
                .where(AuditLog.tenant_id == tenant)
                .order_by(AuditLog.created_at.desc())
                .limit(8)
            )
        ).all()
    )
    total = len(leads)
    qualified = sum(1 for lead in leads if "qualified" in (lead.qualification_status or ""))
    high = sum(1 for lead in leads if lead.priority == LeadPriority.HIGH)
    active = sum(
        1
        for run in runs
        if run.status in {RunStatus.QUEUED, RunStatus.RUNNING, RunStatus.WAITING_APPROVAL}
    )
    pending = sum(1 for approval in approvals if approval.status == ApprovalStatus.PENDING)
    completed = sum(1 for run in runs if run.status == RunStatus.COMPLETED)
    failed = sum(1 for run in runs if run.status == RunStatus.FAILED)
    success_rate = round(100 * completed / (completed + failed), 1) if completed + failed else 100.0
    today = datetime.now(UTC).date()
    weekly_leads = [
        ChartPoint(
            label=(today - timedelta(days=offset)).strftime("%a"),
            value=sum(
                1 for lead in leads if lead.created_at.date() == today - timedelta(days=offset)
            ),
        )
        for offset in range(6, -1, -1)
    ]
    token_by_agent: dict[str, int] = {}
    for execution in executions:
        token_by_agent[execution.agent_name] = token_by_agent.get(execution.agent_name, 0) + (
            execution.input_tokens + execution.output_tokens
        )
    sent_messages = [item for item in messages if item.sent_at]
    outbound_messages = [
        item for item in messages if item.direction.value == "outbound" and item.sent_at
    ]
    replied_messages = [item for item in outbound_messages if item.replied_at]
    email_sent = [item for item in outbound_messages if item.channel == CommunicationChannel.EMAIL]
    event_statuses = [item.status for item in message_events]
    response_minutes = [
        (item.replied_at - item.sent_at).total_seconds() / 60
        for item in replied_messages
        if item.replied_at and item.sent_at
    ]

    def rate(count: int, denominator: int) -> float:
        return round(100 * count / denominator, 1) if denominator else 0.0

    return DashboardSummary(
        total_leads=total,
        qualified_leads=qualified,
        high_priority_leads=high,
        active_runs=active,
        pending_approvals=pending,
        reports_generated=len(reports),
        failed_workflows=failed,
        success_rate=success_rate,
        total_tokens=sum(token_by_agent.values()),
        monthly_cost_usd=round(sum(item.estimated_cost_usd for item in executions), 4),
        lead_status=[
            ChartPoint(
                label="New", value=sum(1 for lead in leads if not lead.qualification_status)
            ),
            ChartPoint(label="Qualified", value=qualified),
            ChartPoint(
                label="Nurture",
                value=sum(1 for lead in leads if lead.qualification_status == "nurture"),
            ),
        ],
        workflow_outcomes=[
            ChartPoint(label="Completed", value=completed),
            ChartPoint(label="Failed", value=failed),
            ChartPoint(label="Active", value=active),
        ],
        weekly_leads=weekly_leads,
        token_usage=[
            ChartPoint(label=name.title(), value=value) for name, value in token_by_agent.items()
        ],
        recent_activity=recent,
        communication=CommunicationAnalytics(
            messages_sent_today=sum(1 for item in sent_messages if item.sent_at.date() == today),
            emails_sent=len(email_sent),
            messages_delivered=event_statuses.count(MessageStatus.DELIVERED),
            messages_read=event_statuses.count(MessageStatus.READ)
            + event_statuses.count(MessageStatus.OPENED),
            replies_received=event_statuses.count(MessageStatus.REPLIED),
            response_rate=rate(len(replied_messages), len(outbound_messages)),
            average_response_minutes=round(sum(response_minutes) / len(response_minutes), 1)
            if response_minutes
            else 0.0,
            open_rate=rate(event_statuses.count(MessageStatus.OPENED), len(email_sent)),
            click_rate=rate(event_statuses.count(MessageStatus.CLICKED), len(email_sent)),
            reply_rate=rate(len(replied_messages), len(email_sent)),
            bounce_rate=rate(event_statuses.count(MessageStatus.BOUNCED), len(email_sent)),
            funnel=[
                ChartPoint(label="Lead created", value=len(leads)),
                ChartPoint(label="Workflow completed", value=completed),
                ChartPoint(
                    label="Approved",
                    value=sum(1 for item in approvals if item.status == ApprovalStatus.APPROVED),
                ),
                ChartPoint(label="Sent", value=len(outbound_messages)),
                ChartPoint(label="Delivered", value=event_statuses.count(MessageStatus.DELIVERED)),
                ChartPoint(label="Replied", value=len(replied_messages)),
                ChartPoint(
                    label="Converted",
                    value=sum(
                        1
                        for lead in leads
                        if lead.score
                        and lead.score >= 75
                        and lead.attributes.get("response_intent")
                    ),
                ),
            ],
        ),
    )


@router.get("/agents/metrics", response_model=list[AgentMetric], tags=["monitoring"])
async def agent_metrics(
    db: AsyncSession = Depends(get_db), user: User = Depends(current_user)
) -> list[AgentMetric]:
    executions = list(
        (
            await db.scalars(
                select(AgentExecution)
                .where(AgentExecution.tenant_id == user.tenant_id)
                .order_by(AgentExecution.created_at.desc())
            )
        ).all()
    )
    names = ["sales", "research", "email", "approval", "report"]
    result: list[AgentMetric] = []
    for name in names:
        items = [item for item in executions if item.agent_name == name]
        succeeded = sum(1 for item in items if item.status == "completed")
        failed_items = [item for item in items if item.status == "failed"]
        result.append(
            AgentMetric(
                agent_name=name,
                total_runs=len(items),
                successful_runs=succeeded,
                failed_runs=len(failed_items),
                success_rate=round(100 * succeeded / len(items), 1) if items else 100.0,
                average_latency_ms=round(sum(item.latency_ms for item in items) / len(items), 1)
                if items
                else 0,
                input_tokens=sum(item.input_tokens for item in items),
                output_tokens=sum(item.output_tokens for item in items),
                estimated_cost_usd=round(sum(item.estimated_cost_usd for item in items), 4),
                last_failure_reason=failed_items[0].error if failed_items else None,
            )
        )
    return result


@router.get("/users", response_model=list[UserRead], tags=["administration"])
async def list_users(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(Role.ADMIN)),
) -> list[User]:
    query = select(User).where(User.tenant_id == user.tenant_id).order_by(User.created_at.desc())
    return list((await db.scalars(query)).all())


@router.post("/users", response_model=UserRead, status_code=201, tags=["administration"])
async def create_user(
    payload: UserCreate,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(require_roles(Role.ADMIN)),
) -> User:
    existing = await db.scalar(
        select(User).where(User.tenant_id == actor.tenant_id, User.email == payload.email)
    )
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "A user with this email already exists")
    user = User(
        tenant_id=actor.tenant_id,
        email=payload.email,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    await db.flush()
    await audit(
        db,
        tenant_id=actor.tenant_id,
        actor_id=actor.id,
        action="user.invited",
        resource_type="user",
        resource_id=str(user.id),
        details={"role": user.role.value},
    )
    await db.commit()
    await db.refresh(user)
    return user


@router.patch("/users/{user_id}", response_model=UserRead, tags=["administration"])
async def update_user(
    user_id: UUID,
    payload: UserUpdate,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(require_roles(Role.ADMIN)),
) -> User:
    user = await db.scalar(
        select(User).where(User.id == user_id, User.tenant_id == actor.tenant_id)
    )
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    changes = payload.model_dump(exclude_unset=True)
    if user.id == actor.id and changes.get("active") is False:
        raise HTTPException(status.HTTP_409_CONFLICT, "You cannot disable your own account")
    for field, value in changes.items():
        setattr(user, field, value)
    await audit(
        db,
        tenant_id=actor.tenant_id,
        actor_id=actor.id,
        action="user.updated",
        resource_type="user",
        resource_id=str(user.id),
        details={"fields": sorted(changes)},
    )
    await db.commit()
    await db.refresh(user)
    return user


async def tenant_settings_record(db: AsyncSession, tenant_id: UUID) -> MemoryRecord | None:
    return await db.scalar(
        select(MemoryRecord)
        .where(MemoryRecord.tenant_id == tenant_id, MemoryRecord.namespace == "tenant_settings")
        .order_by(MemoryRecord.updated_at.desc())
    )


@router.get("/settings", response_model=TenantSettings, tags=["administration"])
async def get_settings(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(Role.ADMIN)),
) -> TenantSettings:
    tenant = await db.get(Tenant, user.tenant_id)
    record = await tenant_settings_record(db, user.tenant_id)
    values = json.loads(record.content) if record else {}
    return TenantSettings(company_name=tenant.name, **values)


@router.put("/settings", response_model=TenantSettings, tags=["administration"])
async def update_settings(
    payload: TenantSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(Role.ADMIN)),
) -> TenantSettings:
    tenant = await db.get(Tenant, user.tenant_id)
    tenant.name = payload.company_name
    record = await tenant_settings_record(db, user.tenant_id)
    previous = json.loads(record.content) if record else {}
    values = payload.model_dump(exclude={"company_name", "api_key"})
    configured = bool(payload.api_key) or previous.get("api_key_configured", False)
    values["api_key_configured"] = configured
    metadata = dict(record.metadata_json) if record else {}
    if payload.api_key:
        metadata["api_key_fingerprint"] = hashlib.sha256(payload.api_key.encode()).hexdigest()[:12]
    if record is None:
        record = MemoryRecord(
            tenant_id=user.tenant_id,
            namespace="tenant_settings",
            content=json.dumps(values),
            metadata_json=metadata,
        )
        db.add(record)
    else:
        record.content = json.dumps(values)
        record.metadata_json = metadata
    await audit(
        db,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="settings.updated",
        resource_type="tenant",
        resource_id=str(user.tenant_id),
        details={"llm_provider": payload.llm_provider},
    )
    await db.commit()
    return TenantSettings(company_name=tenant.name, **values)
