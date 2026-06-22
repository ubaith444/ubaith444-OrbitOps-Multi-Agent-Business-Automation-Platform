from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AgentEvaluation, AgentExecution


async def evaluate_execution(
    db: AsyncSession, execution: AgentExecution, output_text: str
) -> AgentEvaluation:
    completed = execution.status == "completed"
    accuracy = 0.9 if completed else 0.2
    completeness = min(1.0, 0.55 + len(output_text.strip()) / 240) if completed else 0.1
    relevance = 0.92 if completed and output_text.strip() else 0.15
    hallucination_risk = (
        0.08 if "source" in output_text.casefold() or execution.agent_name != "research" else 0.28
    )
    overall = round((accuracy + completeness + relevance + (1 - hallucination_risk)) / 4, 4)
    evaluation = AgentEvaluation(
        tenant_id=execution.tenant_id,
        execution_id=execution.id,
        accuracy=round(accuracy, 4),
        completeness=round(completeness, 4),
        relevance=round(relevance, 4),
        hallucination_risk=round(hallucination_risk, 4),
        overall_score=overall,
        rationale=(
            "Deterministic rubric: execution status, output completeness, task relevance, "
            "and source-verification language."
        ),
    )
    db.add(evaluation)
    await db.flush()
    return evaluation
