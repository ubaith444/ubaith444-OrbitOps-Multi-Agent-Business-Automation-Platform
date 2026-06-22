from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.graph import automation_graph
from app.models import (
    AgentExecution,
    AgentExecutionTrace,
    Approval,
    ApprovalKind,
    CommunicationChannel,
    CommunicationMessage,
    MessageStatus,
    PromptVersion,
    Report,
    ReportStatus,
    RunStatus,
    WorkflowRun,
)
from app.services.audit import audit
from app.services.communications import record_message_event
from app.services.evaluations import evaluate_execution
from app.services.reports import render_executive_pdf
from app.services.state_store import cache_workflow_state


async def execute_run(db: AsyncSession, run: WorkflowRun, state: dict) -> WorkflowRun:
    run.status = RunStatus.RUNNING
    run.error = None
    run.started_at = run.started_at or datetime.now(UTC)
    run.current_agent = state.get("phase", "sales")
    await db.commit()
    previous_event_count = len(state.get("events", []))
    try:
        result = await automation_graph.ainvoke(state)
        run.state_snapshot = result
        await cache_workflow_state(str(run.tenant_id), str(run.id), result)
        if result.get("phase") == "failed":
            run.status = RunStatus.FAILED
            run.current_agent = result.get("resume_node")
            run.error = result.get("errors", ["Agent execution failed"])[-1]
            run.finished_at = datetime.now(UTC)
            await persist_execution(
                db,
                run,
                run.current_agent or "unknown",
                "failed",
                result,
                error=run.error,
                output_text=run.error or "",
            )
            await audit(
                db,
                tenant_id=run.tenant_id,
                actor_id=None,
                action="workflow.error",
                resource_type="workflow_run",
                resource_id=str(run.id),
                details={"error": run.error, "agent": run.current_agent},
            )
            await db.commit()
            await db.refresh(run)
            return run
        new_events = result.get("events", [])[previous_event_count:]
        for item in new_events:
            agent_name = item.get("agent", "unknown")
            await persist_execution(
                db,
                run,
                agent_name,
                "completed",
                result,
                output_text=item.get("message", ""),
            )
            await audit(
                db,
                tenant_id=run.tenant_id,
                actor_id=None,
                action="agent.step_completed",
                resource_type="workflow_run",
                resource_id=str(run.id),
                details={"agent": agent_name, "message": item.get("message", "")},
            )
        pending = result.get("pending_approval")
        if pending:
            run.status = RunStatus.WAITING_APPROVAL
            run.current_agent = pending["agent"]
            existing = await db.scalar(
                select(Approval).where(
                    Approval.run_id == run.id,
                    Approval.kind == ApprovalKind.OUTBOUND_EMAIL,
                )
            )
            if existing is None:
                existing = Approval(
                    tenant_id=run.tenant_id,
                    run_id=run.id,
                    kind=ApprovalKind.OUTBOUND_EMAIL,
                    payload=pending["payload"],
                    requested_by_agent=pending["agent"],
                )
                db.add(existing)
                await db.flush()
            communication = await db.scalar(
                select(CommunicationMessage).where(CommunicationMessage.approval_id == existing.id)
            )
            if communication is None and existing.kind == ApprovalKind.OUTBOUND_EMAIL:
                communication = CommunicationMessage(
                    tenant_id=run.tenant_id,
                    lead_id=run.lead_id,
                    run_id=run.id,
                    approval_id=existing.id,
                    channel=CommunicationChannel.EMAIL,
                    provider="mock",
                    subject=str(pending["payload"].get("subject", "")),
                    body=str(pending["payload"].get("body", "")),
                )
                db.add(communication)
                await db.flush()
                await record_message_event(db, communication, MessageStatus.DRAFT)
        else:
            await generate_report(db, run, result)
            run.status = RunStatus.COMPLETED
            run.current_agent = None
            run.finished_at = datetime.now(UTC)
    except Exception as exc:
        run.status = RunStatus.FAILED
        run.error = str(exc)
        run.finished_at = datetime.now(UTC)
        await audit(
            db,
            tenant_id=run.tenant_id,
            actor_id=None,
            action="workflow.error",
            resource_type="workflow_run",
            resource_id=str(run.id),
            details={"error": str(exc)},
        )
    await db.commit()
    await db.refresh(run)
    return run


async def persist_execution(
    db: AsyncSession,
    run: WorkflowRun,
    agent_name: str,
    execution_status: str,
    state: dict,
    *,
    error: str | None = None,
    output_text: str = "",
) -> AgentExecution:
    usage = next(
        (item for item in reversed(state.get("llm_calls", [])) if item["agent"] == agent_name),
        {},
    )
    timing = next(
        (item for item in reversed(state.get("node_timings", [])) if item["agent"] == agent_name),
        {},
    )
    execution = AgentExecution(
        tenant_id=run.tenant_id,
        run_id=run.id,
        agent_name=agent_name,
        provider=usage.get("provider", "deterministic"),
        model=usage.get("model", "rules-v1"),
        status=execution_status,
        input_tokens=usage.get("input_tokens", 0),
        output_tokens=usage.get("output_tokens", 0),
        estimated_cost_usd=usage.get("estimated_cost_usd", 0),
        latency_ms=timing.get("latency_ms", usage.get("latency_ms", 0)),
        attempt=timing.get("attempt", 1),
        error=error,
    )
    db.add(execution)
    await db.flush()
    prompt = await db.scalar(
        select(PromptVersion).where(
            PromptVersion.tenant_id == run.tenant_id,
            PromptVersion.agent_name == agent_name,
            PromptVersion.active.is_(True),
        )
    )
    started_at = timing.get("started_at")
    finished_at = timing.get("finished_at")
    db.add(
        AgentExecutionTrace(
            tenant_id=run.tenant_id,
            execution_id=execution.id,
            user_id=run.initiated_by,
            prompt_version_id=prompt.id if prompt else None,
            task=usage.get("task", f"{agent_name}_step"),
            started_at=datetime.fromisoformat(started_at) if started_at else datetime.now(UTC),
            finished_at=datetime.fromisoformat(finished_at) if finished_at else datetime.now(UTC),
            error_category=timing.get("error_category") if error else None,
            retry_count=max(0, timing.get("attempt", 1) - 1),
            fallback_history=usage.get("fallback_history", []),
        )
    )
    await evaluate_execution(db, execution, output_text)
    return execution


async def generate_report(db: AsyncSession, run: WorkflowRun, state: dict) -> Report:
    existing = await db.scalar(select(Report).where(Report.run_id == run.id))
    if existing is not None:
        return existing
    report_data = dict(state["report"])
    try:
        content = render_executive_pdf(report_data)
        report = Report(
            tenant_id=run.tenant_id,
            run_id=run.id,
            lead_id=run.lead_id,
            title=report_data["title"],
            status=ReportStatus.GENERATED,
            file_name=f"orbitops-{run.id}.pdf",
            content=content,
            size_bytes=len(content),
            metadata_json={
                "score": report_data.get("score"),
                "priority": report_data.get("priority"),
            },
        )
        db.add(report)
        await db.flush()
        await audit(
            db,
            tenant_id=run.tenant_id,
            actor_id=None,
            action="report.generated",
            resource_type="report",
            resource_id=str(report.id),
        )
        return report
    except Exception as exc:
        await audit(
            db,
            tenant_id=run.tenant_id,
            actor_id=None,
            action="report.error",
            resource_type="workflow_run",
            resource_id=str(run.id),
            details={"error": str(exc)},
        )
        raise


def initial_state(run: WorkflowRun, lead: object) -> dict:
    return {
        "tenant_id": str(run.tenant_id),
        "run_id": str(run.id),
        "lead": {
            "id": str(lead.id),
            "name": lead.name,
            "company": lead.company,
            "industry": lead.industry,
            "website": lead.website,
            "email": lead.email,
            "phone": lead.phone,
            "attributes": lead.attributes,
        },
        "approved_actions": [],
        "events": [],
        "errors": [],
        "phase": "new",
    }
