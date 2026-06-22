from datetime import UTC, datetime
from typing import Any

from app.agents.llm_router import CompletionRequest, CompletionResult, ModelRouter
from app.agents.state import AutomationState

router = ModelRouter()


def event(agent: str, message: str) -> dict[str, str]:
    return {"agent": agent, "message": message, "at": datetime.now(UTC).isoformat()}


def llm_call(agent: str, task: str, prompt: str, result: CompletionResult) -> dict[str, Any]:
    return {
        "agent": agent,
        "task": task,
        "prompt": prompt,
        "provider": result.provider,
        "model": result.model,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "estimated_cost_usd": result.estimated_cost_usd,
        "latency_ms": result.latency_ms,
        "fallback_history": result.fallback_history,
    }


def route_for(state: AutomationState, agent: str) -> list[tuple[str, str]] | None:
    configured = state.get("model_routes", {}).get(agent)
    if not configured:
        return None
    return [(item["provider"], item["model"]) for item in configured]


def apply_prompt(state: AutomationState, agent: str, task_prompt: str) -> str:
    template = state.get("prompt_templates", {}).get(agent)
    return f"{template}\n\nTask:\n{task_prompt}" if template else task_prompt


async def sales_agent(state: AutomationState) -> dict[str, Any]:
    lead = state["lead"]
    score = 25
    score += 20 if lead.get("email") else 0
    score += 10 if lead.get("phone") else 0
    score += 15 if lead.get("website") else 0
    score += 10 if lead.get("industry") else 0
    score += min(20, int(lead.get("attributes", {}).get("intent_score", 0)))
    priority = "high" if score >= 75 else "medium" if score >= 50 else "low"
    qualification = (
        "sales-qualified" if score >= 75 else "marketing-qualified" if score >= 50 else "nurture"
    )
    action = (
        "Book a discovery call"
        if score >= 75
        else "Send a tailored value brief"
        if score >= 50
        else "Enroll in nurture"
    )
    return {
        "lead_score": score,
        "priority": priority,
        "qualification_status": qualification,
        "recommended_action": action,
        "phase": "sales_complete",
        "events": [*state.get("events", []), event("sales", f"Scored lead {score}/100")],
    }


async def research_agent(state: AutomationState) -> dict[str, Any]:
    lead = state["lead"]
    prompt = apply_prompt(
        state,
        "research",
        f"Research {lead['company']} in {lead.get('industry') or 'its industry'}",
    )
    result = await router.complete(
        CompletionRequest(
            task="company_research",
            prompt=prompt,
            agent_name="research",
            complexity="standard",
        ),
        route=route_for(state, "research"),
    )
    company = lead["company"]
    industry = lead.get("industry") or "the target market"
    return {
        "company_summary": (
            f"{company} is a prospect operating in {industry}. "
            "External facts require source verification before use."
        ),
        "industry_insights": [
            f"Demand and competitive pressure in {industry} should be validated "
            "with current sources."
        ],
        "competitors": [],
        "risks": ["Research is preliminary", "No verified external citations in mock mode"],
        "phase": "research_complete",
        "events": [
            *state.get("events", []),
            event("research", f"Research completed via {result.provider}"),
        ],
        "llm_calls": [
            *state.get("llm_calls", []),
            llm_call("research", "company_research", prompt, result),
        ],
    }


async def email_agent(state: AutomationState) -> dict[str, Any]:
    lead = state["lead"]
    first_name = lead["name"].split()[0]
    prompt = apply_prompt(
        state, "email", f"Draft an approval-required sales email for {lead['company']}"
    )
    result = await router.complete(
        CompletionRequest(task="email_draft", prompt=prompt, agent_name="email"),
        route=route_for(state, "email"),
    )
    return {
        "email_subject": f"A practical idea for {lead['company']}",
        "email_body": (
            f"Hi {first_name},\n\nI noticed {lead['company']} is active in "
            f"{lead.get('industry') or 'your market'}. We help teams automate "
            "qualified lead follow-up without losing human review. Would a 20-minute "
            "working session be useful?\n\nBest,\nOrbitOps"
        ),
        "follow_up_sequence": [
            {"day": 3, "purpose": "share one relevant outcome"},
            {"day": 7, "purpose": "close the loop politely"},
        ],
        "phase": "email_complete",
        "events": [
            *state.get("events", []),
            event("email", f"Prepared personalized sequence via {result.provider}"),
        ],
        "llm_calls": [
            *state.get("llm_calls", []),
            llm_call("email", "email_draft", prompt, result),
        ],
    }


async def email_gate(state: AutomationState) -> dict[str, Any]:
    if "outbound_email" not in state.get("approved_actions", []):
        return {
            "pending_approval": {
                "kind": "outbound_email",
                "agent": "email",
                "payload": {"subject": state["email_subject"], "body": state["email_body"]},
            },
            "phase": "awaiting_approval",
        }
    return {"pending_approval": None, "phase": "approved"}


async def report_agent(state: AutomationState) -> dict[str, Any]:
    prompt = apply_prompt(
        state,
        "report",
        f"Summarize approved lead intelligence for {state['lead']['company']}",
    )
    result = await router.complete(
        CompletionRequest(task="report_summary", prompt=prompt, agent_name="report"),
        route=route_for(state, "report"),
    )
    return {
        "report": {
            "title": f"Lead intelligence: {state['lead']['company']}",
            "executive_summary": state["company_summary"],
            "score": state["lead_score"],
            "priority": state["priority"],
            "recommended_action": state["recommended_action"],
            "risks": state.get("risks", []),
            "status": "approved",
        },
        "phase": "completed",
        "events": [
            *state.get("events", []),
            event("report", f"Generated executive report draft via {result.provider}"),
        ],
        "llm_calls": [
            *state.get("llm_calls", []),
            llm_call("report", "report_summary", prompt, result),
        ],
    }
