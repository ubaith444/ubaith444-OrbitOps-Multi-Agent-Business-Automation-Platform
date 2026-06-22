from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.llm_router import CompletionRequest, ModelRouter
from app.api.dependencies import current_user, require_roles
from app.core.database import get_db
from app.models import (
    AgentEvaluation,
    AgentExecution,
    AgentExecutionTrace,
    AgentFeedback,
    CommunicationMessage,
    MessageEvent,
    MessageStatus,
    ModelRoute,
    PlaygroundRun,
    PromptVersion,
    Role,
    User,
)
from app.schemas import (
    AgentExecutionHistory,
    AgentMetric,
    AIOperationsSummary,
    ChartPoint,
    CostBreakdown,
    CostSummary,
    EvaluationRead,
    FeedbackCreate,
    FeedbackRead,
    ModelRouteRead,
    ModelRouteUpdate,
    PlaygroundRequest,
    PlaygroundRunRead,
    PromptVersionCreate,
    PromptVersionRead,
)
from app.services.audit import audit

router = APIRouter(prefix="/ai-ops")


async def tenant_executions(db: AsyncSession, tenant_id: UUID) -> list[AgentExecution]:
    return list(
        (
            await db.scalars(
                select(AgentExecution)
                .where(AgentExecution.tenant_id == tenant_id)
                .order_by(AgentExecution.created_at.desc())
            )
        ).all()
    )


async def execution_history_item(
    db: AsyncSession, execution: AgentExecution
) -> AgentExecutionHistory:
    trace = await db.scalar(
        select(AgentExecutionTrace).where(AgentExecutionTrace.execution_id == execution.id)
    )
    evaluation = await db.scalar(
        select(AgentEvaluation)
        .where(AgentEvaluation.execution_id == execution.id)
        .order_by(AgentEvaluation.created_at.desc())
    )
    feedback = list(
        (
            await db.scalars(
                select(AgentFeedback).where(AgentFeedback.execution_id == execution.id)
            )
        ).all()
    )
    prompt = (
        await db.get(PromptVersion, trace.prompt_version_id)
        if trace and trace.prompt_version_id
        else None
    )
    return AgentExecutionHistory(
        id=execution.id,
        run_id=execution.run_id,
        user_id=trace.user_id if trace else None,
        agent_name=execution.agent_name,
        task=trace.task if trace else f"{execution.agent_name}_step",
        provider=execution.provider,
        model=execution.model,
        status=execution.status,
        input_tokens=execution.input_tokens,
        output_tokens=execution.output_tokens,
        estimated_cost_usd=execution.estimated_cost_usd,
        latency_ms=execution.latency_ms,
        retry_count=trace.retry_count if trace else max(0, execution.attempt - 1),
        error_category=trace.error_category if trace else None,
        error=execution.error,
        fallback_history=trace.fallback_history if trace else [],
        prompt_version=prompt.version if prompt else None,
        evaluation_score=evaluation.overall_score if evaluation else None,
        positive_feedback=sum(1 for item in feedback if item.rating == 1),
        negative_feedback=sum(1 for item in feedback if item.rating == -1),
        created_at=execution.created_at,
    )


@router.get("/executions", response_model=list[AgentExecutionHistory], tags=["ai-operations"])
async def list_executions(
    agent_name: str | None = Query(default=None, max_length=80),
    execution_status: str | None = Query(default=None, alias="status", max_length=40),
    provider: str | None = Query(default=None, max_length=40),
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
) -> list[AgentExecutionHistory]:
    query = select(AgentExecution).where(AgentExecution.tenant_id == user.tenant_id)
    if agent_name:
        query = query.where(AgentExecution.agent_name == agent_name)
    if execution_status:
        query = query.where(AgentExecution.status == execution_status)
    if provider:
        query = query.where(AgentExecution.provider == provider)
    executions = list(
        (await db.scalars(query.order_by(AgentExecution.created_at.desc()).limit(limit))).all()
    )
    return [await execution_history_item(db, item) for item in executions]


def grouped_cost(
    executions: list[AgentExecution], labels: dict[UUID, str] | None, field: str
) -> list[CostBreakdown]:
    grouped: dict[str, list[AgentExecution]] = {}
    for execution in executions:
        if field == "user":
            label = labels.get(execution.id, "System") if labels else "System"
        else:
            label = str(getattr(execution, field))
        grouped.setdefault(label, []).append(execution)
    return [
        CostBreakdown(
            label=label,
            input_tokens=sum(item.input_tokens for item in items),
            output_tokens=sum(item.output_tokens for item in items),
            cost_usd=round(sum(item.estimated_cost_usd for item in items), 6),
        )
        for label, items in sorted(grouped.items())
    ]


async def cost_summary(
    db: AsyncSession, tenant_id: UUID, executions: list[AgentExecution]
) -> CostSummary:
    traces = list(
        (
            await db.scalars(
                select(AgentExecutionTrace).where(AgentExecutionTrace.tenant_id == tenant_id)
            )
        ).all()
    )
    users = list((await db.scalars(select(User).where(User.tenant_id == tenant_id))).all())
    user_names = {item.id: item.full_name for item in users}
    execution_users = {item.execution_id: user_names.get(item.user_id, "System") for item in traces}
    today = datetime.now(UTC).date()
    month_start = today.replace(day=1)
    daily = [
        ChartPoint(
            label=(today - timedelta(days=offset)).strftime("%b %d"),
            value=round(
                sum(
                    item.estimated_cost_usd
                    for item in executions
                    if item.created_at.date() == today - timedelta(days=offset)
                ),
                6,
            ),
        )
        for offset in range(6, -1, -1)
    ]
    return CostSummary(
        total_input_tokens=sum(item.input_tokens for item in executions),
        total_output_tokens=sum(item.output_tokens for item in executions),
        daily_spend_usd=round(
            sum(item.estimated_cost_usd for item in executions if item.created_at.date() == today),
            6,
        ),
        monthly_spend_usd=round(
            sum(
                item.estimated_cost_usd
                for item in executions
                if item.created_at.date() >= month_start
            ),
            6,
        ),
        by_agent=grouped_cost(executions, None, "agent_name"),
        by_provider=grouped_cost(executions, None, "provider"),
        by_user=grouped_cost(executions, execution_users, "user"),
        daily=daily,
    )


@router.get("/summary", response_model=AIOperationsSummary, tags=["ai-operations"])
async def ai_operations_summary(
    db: AsyncSession = Depends(get_db), user: User = Depends(current_user)
) -> AIOperationsSummary:
    executions = await tenant_executions(db, user.tenant_id)
    evaluations = list(
        (
            await db.scalars(
                select(AgentEvaluation).where(AgentEvaluation.tenant_id == user.tenant_id)
            )
        ).all()
    )
    feedback = list(
        (
            await db.scalars(select(AgentFeedback).where(AgentFeedback.tenant_id == user.tenant_id))
        ).all()
    )
    traces = list(
        (
            await db.scalars(
                select(AgentExecutionTrace).where(AgentExecutionTrace.tenant_id == user.tenant_id)
            )
        ).all()
    )
    completed = sum(1 for item in executions if item.status == "completed")
    failed = sum(1 for item in executions if item.status == "failed")
    error_counts: dict[str, int] = {}
    for trace in traces:
        if trace.error_category:
            error_counts[trace.error_category] = error_counts.get(trace.error_category, 0) + 1
    agents: list[AgentMetric] = []
    for name in sorted(
        {item.agent_name for item in executions} | {"sales", "research", "email", "report"}
    ):
        items = [item for item in executions if item.agent_name == name]
        successes = sum(1 for item in items if item.status == "completed")
        failures = [item for item in items if item.status == "failed"]
        agents.append(
            AgentMetric(
                agent_name=name,
                total_runs=len(items),
                successful_runs=successes,
                failed_runs=len(failures),
                success_rate=round(100 * successes / len(items), 1) if items else 100,
                average_latency_ms=round(sum(item.latency_ms for item in items) / len(items), 1)
                if items
                else 0,
                input_tokens=sum(item.input_tokens for item in items),
                output_tokens=sum(item.output_tokens for item in items),
                estimated_cost_usd=round(sum(item.estimated_cost_usd for item in items), 6),
                last_failure_reason=failures[0].error if failures else None,
            )
        )
    total = len(executions)
    rated = [item for item in feedback if item.rating in {-1, 1}]
    return AIOperationsSummary(
        total_executions=total,
        success_rate=round(100 * completed / total, 1) if total else 100,
        failure_rate=round(100 * failed / total, 1) if total else 0,
        average_latency_ms=round(sum(item.latency_ms for item in executions) / total, 1)
        if total
        else 0,
        retries=sum(item.retry_count for item in traces),
        average_evaluation_score=round(
            sum(item.overall_score for item in evaluations) / len(evaluations), 4
        )
        if evaluations
        else 0,
        positive_feedback_rate=round(
            100 * sum(1 for item in rated if item.rating == 1) / len(rated), 1
        )
        if rated
        else 0,
        error_categories=[
            ChartPoint(label=key, value=value) for key, value in error_counts.items()
        ],
        agents=agents,
        costs=await cost_summary(db, user.tenant_id, executions),
    )


@router.get(
    "/executions/{execution_id}/evaluations",
    response_model=list[EvaluationRead],
    tags=["ai-operations"],
)
async def list_evaluations(
    execution_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
) -> list[AgentEvaluation]:
    execution = await db.scalar(
        select(AgentExecution).where(
            AgentExecution.id == execution_id, AgentExecution.tenant_id == user.tenant_id
        )
    )
    if execution is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Execution not found")
    return list(
        (
            await db.scalars(
                select(AgentEvaluation)
                .where(AgentEvaluation.execution_id == execution_id)
                .order_by(AgentEvaluation.created_at.desc())
            )
        ).all()
    )


@router.post(
    "/executions/{execution_id}/feedback",
    response_model=FeedbackRead,
    tags=["ai-operations"],
)
async def save_feedback(
    execution_id: UUID,
    payload: FeedbackCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
) -> AgentFeedback:
    execution = await db.scalar(
        select(AgentExecution).where(
            AgentExecution.id == execution_id, AgentExecution.tenant_id == user.tenant_id
        )
    )
    if execution is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Execution not found")
    feedback = await db.scalar(
        select(AgentFeedback).where(
            AgentFeedback.execution_id == execution_id, AgentFeedback.user_id == user.id
        )
    )
    if feedback is None:
        feedback = AgentFeedback(
            tenant_id=user.tenant_id,
            execution_id=execution_id,
            user_id=user.id,
            rating=payload.rating,
            comment=payload.comment,
        )
        db.add(feedback)
    else:
        feedback.rating = payload.rating
        feedback.comment = payload.comment
    await audit(
        db,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="agent.feedback_recorded",
        resource_type="agent_execution",
        resource_id=str(execution_id),
        details={"rating": payload.rating},
    )
    await db.commit()
    await db.refresh(feedback)
    return feedback


@router.get("/prompts", response_model=list[PromptVersionRead], tags=["prompt-management"])
async def list_prompts(
    agent_name: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(Role.ADMIN)),
) -> list[PromptVersion]:
    query = select(PromptVersion).where(PromptVersion.tenant_id == user.tenant_id)
    if agent_name:
        query = query.where(PromptVersion.agent_name == agent_name)
    prompts = list((await db.scalars(query.order_by(PromptVersion.created_at.desc()))).all())
    for prompt in prompts:
        traces = list(
            (
                await db.scalars(
                    select(AgentExecutionTrace).where(
                        AgentExecutionTrace.prompt_version_id == prompt.id
                    )
                )
            ).all()
        )
        execution_ids = [item.execution_id for item in traces]
        evaluations = (
            list(
                (
                    await db.scalars(
                        select(AgentEvaluation).where(
                            AgentEvaluation.execution_id.in_(execution_ids)
                        )
                    )
                ).all()
            )
            if execution_ids
            else []
        )
        feedback = (
            list(
                (
                    await db.scalars(
                        select(AgentFeedback).where(AgentFeedback.execution_id.in_(execution_ids))
                    )
                ).all()
            )
            if execution_ids
            else []
        )
        prompt.performance_metrics = {
            "executions": len(execution_ids),
            "average_evaluation": round(
                sum(item.overall_score for item in evaluations) / len(evaluations), 4
            )
            if evaluations
            else 0,
            "positive_feedback_rate": round(
                100 * sum(1 for item in feedback if item.rating == 1) / len(feedback), 1
            )
            if feedback
            else 0,
        }
        if prompt.agent_name == "email" and execution_ids:
            run_ids = list(
                (
                    await db.scalars(
                        select(AgentExecution.run_id).where(AgentExecution.id.in_(execution_ids))
                    )
                ).all()
            )
            messages = list(
                (
                    await db.scalars(
                        select(CommunicationMessage).where(CommunicationMessage.run_id.in_(run_ids))
                    )
                ).all()
            )
            message_ids = [item.id for item in messages]
            opens = (
                await db.scalar(
                    select(func.count(MessageEvent.id)).where(
                        MessageEvent.message_id.in_(message_ids),
                        MessageEvent.status == MessageStatus.OPENED,
                    )
                )
                if message_ids
                else 0
            ) or 0
            prompt.performance_metrics["open_rate"] = (
                round(100 * opens / len(messages), 1) if messages else 0
            )
    return prompts


@router.post(
    "/prompts", response_model=PromptVersionRead, status_code=201, tags=["prompt-management"]
)
async def create_prompt(
    payload: PromptVersionCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(Role.ADMIN)),
) -> PromptVersion:
    latest = await db.scalar(
        select(func.max(PromptVersion.version)).where(
            PromptVersion.tenant_id == user.tenant_id,
            PromptVersion.agent_name == payload.agent_name,
        )
    )
    if payload.activate:
        active = list(
            (
                await db.scalars(
                    select(PromptVersion).where(
                        PromptVersion.tenant_id == user.tenant_id,
                        PromptVersion.agent_name == payload.agent_name,
                        PromptVersion.active.is_(True),
                    )
                )
            ).all()
        )
        for item in active:
            item.active = False
    prompt = PromptVersion(
        tenant_id=user.tenant_id,
        agent_name=payload.agent_name,
        name=payload.name,
        version=(latest or 0) + 1,
        content=payload.content,
        created_by=user.id,
        active=payload.activate,
    )
    db.add(prompt)
    await db.flush()
    await audit(
        db,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="prompt.version_created",
        resource_type="prompt_version",
        resource_id=str(prompt.id),
        details={"agent": prompt.agent_name, "version": prompt.version},
    )
    await db.commit()
    await db.refresh(prompt)
    return prompt


@router.post(
    "/prompts/{prompt_id}/activate",
    response_model=PromptVersionRead,
    tags=["prompt-management"],
)
async def activate_prompt(
    prompt_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(Role.ADMIN)),
) -> PromptVersion:
    prompt = await db.scalar(
        select(PromptVersion).where(
            PromptVersion.id == prompt_id, PromptVersion.tenant_id == user.tenant_id
        )
    )
    if prompt is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Prompt not found")
    active = list(
        (
            await db.scalars(
                select(PromptVersion).where(
                    PromptVersion.tenant_id == user.tenant_id,
                    PromptVersion.agent_name == prompt.agent_name,
                    PromptVersion.active.is_(True),
                )
            )
        ).all()
    )
    for item in active:
        item.active = False
    prompt.active = True
    await db.commit()
    await db.refresh(prompt)
    return prompt


@router.get("/routes", response_model=list[ModelRouteRead], tags=["model-routing"])
async def list_model_routes(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(Role.ADMIN)),
) -> list[ModelRoute]:
    return list(
        (
            await db.scalars(
                select(ModelRoute)
                .where(ModelRoute.tenant_id == user.tenant_id)
                .order_by(ModelRoute.agent_name)
            )
        ).all()
    )


@router.put("/routes/{agent_name}", response_model=ModelRouteRead, tags=["model-routing"])
async def update_model_route(
    agent_name: str,
    payload: ModelRouteUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(Role.ADMIN)),
) -> ModelRoute:
    route = await db.scalar(
        select(ModelRoute).where(
            ModelRoute.tenant_id == user.tenant_id, ModelRoute.agent_name == agent_name
        )
    )
    if route is None:
        route = ModelRoute(tenant_id=user.tenant_id, agent_name=agent_name)
        db.add(route)
    route.primary_provider = payload.primary.provider
    route.primary_model = payload.primary.model
    route.fallback_order = [item.model_dump() for item in payload.fallbacks]
    await audit(
        db,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="model_route.updated",
        resource_type="model_route",
        resource_id=agent_name,
        details={"primary_provider": route.primary_provider},
    )
    await db.commit()
    await db.refresh(route)
    return route


@router.post("/playground", response_model=list[PlaygroundRunRead], tags=["agent-playground"])
async def run_playground(
    payload: PlaygroundRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(Role.ADMIN)),
) -> list[PlaygroundRun]:
    router = ModelRouter()
    candidates = payload.candidates
    if not candidates:
        configured = await db.scalar(
            select(ModelRoute).where(
                ModelRoute.tenant_id == user.tenant_id,
                ModelRoute.agent_name == payload.agent_name,
            )
        )
        candidates = (
            [
                type(
                    "Candidate",
                    (),
                    {"provider": configured.primary_provider, "model": configured.primary_model},
                )
            ]
            if configured
            else [type("Candidate", (), {"provider": "mock", "model": "local-deterministic"})]
        )
    comparison_group = str(uuid4())
    runs: list[PlaygroundRun] = []
    for candidate in candidates:
        try:
            result = await router.complete(
                CompletionRequest(
                    task="playground",
                    prompt=payload.prompt,
                    agent_name=payload.agent_name,
                ),
                route=[(candidate.provider, candidate.model)],
            )
            output = result.content
            provider, model = result.provider, result.model
            input_tokens, output_tokens = result.input_tokens, result.output_tokens
            cost, latency = result.estimated_cost_usd, result.latency_ms
        except Exception as exc:
            output = {"error": str(exc), "provider_configured": False}
            provider, model = candidate.provider, candidate.model
            input_tokens = output_tokens = 0
            cost = 0
            latency = 0
        run = PlaygroundRun(
            tenant_id=user.tenant_id,
            user_id=user.id,
            agent_name=payload.agent_name,
            prompt=payload.prompt,
            provider=provider,
            model=model,
            output_json=output,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=cost,
            latency_ms=latency,
            comparison_group=comparison_group,
        )
        db.add(run)
        runs.append(run)
    await audit(
        db,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="agent.playground_run",
        resource_type="playground_run",
        resource_id=comparison_group,
        details={"agent": payload.agent_name, "candidates": len(runs)},
    )
    await db.commit()
    for run in runs:
        await db.refresh(run)
    return runs
