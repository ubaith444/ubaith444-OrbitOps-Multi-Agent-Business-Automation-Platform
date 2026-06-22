from datetime import UTC, datetime
from time import perf_counter

from langgraph.graph import END, START, StateGraph

from app.agents.nodes import email_agent, email_gate, report_agent, research_agent, sales_agent
from app.agents.state import AutomationState


def guarded(name, node):
    async def execute(state: AutomationState):
        started_at = datetime.now(UTC)
        started = perf_counter()
        attempt = sum(1 for item in state.get("node_timings", []) if item["agent"] == name) + 1
        try:
            result = await node(state)
            result["node_timings"] = [
                *state.get("node_timings", []),
                {
                    "agent": name,
                    "status": "completed",
                    "attempt": attempt,
                    "started_at": started_at.isoformat(),
                    "finished_at": datetime.now(UTC).isoformat(),
                    "latency_ms": round((perf_counter() - started) * 1000),
                },
            ]
            return result
        except Exception as exc:
            return {
                "phase": "failed",
                "resume_node": name,
                "errors": [*state.get("errors", []), f"{name}: {exc}"],
                "node_timings": [
                    *state.get("node_timings", []),
                    {
                        "agent": name,
                        "status": "failed",
                        "attempt": attempt,
                        "started_at": started_at.isoformat(),
                        "finished_at": datetime.now(UTC).isoformat(),
                        "latency_ms": round((perf_counter() - started) * 1000),
                        "error_category": type(exc).__name__,
                    },
                ],
            }

    return execute


def route_entry(state: AutomationState) -> str:
    phase = state.get("phase", "new")
    if phase == "failed" and state.get("resume_node"):
        return state["resume_node"]
    if phase == "awaiting_approval" and "outbound_email" in state.get("approved_actions", []):
        return "report"
    return {
        "sales_complete": "research",
        "research_complete": "email",
        "email_complete": "approval_gate",
        "approved": "report",
        "completed": END,
    }.get(phase, "sales")


def build_graph(checkpointer=None):
    graph = StateGraph(AutomationState)
    graph.add_node("sales", guarded("sales", sales_agent))
    graph.add_node("research", guarded("research", research_agent))
    graph.add_node("email", guarded("email", email_agent))
    graph.add_node("approval_gate", guarded("approval_gate", email_gate))
    graph.add_node("report", guarded("report", report_agent))
    graph.add_conditional_edges(
        START,
        route_entry,
        {
            "sales": "sales",
            "research": "research",
            "email": "email",
            "approval_gate": "approval_gate",
            "report": "report",
            END: END,
        },
    )
    graph.add_conditional_edges(
        "sales",
        lambda state: END if state.get("phase") == "failed" else "research",
        {END: END, "research": "research"},
    )
    graph.add_conditional_edges(
        "research",
        lambda state: END if state.get("phase") == "failed" else "email",
        {END: END, "email": "email"},
    )
    graph.add_conditional_edges(
        "email",
        lambda state: END if state.get("phase") == "failed" else "approval_gate",
        {END: END, "approval_gate": "approval_gate"},
    )
    graph.add_edge("approval_gate", END)
    graph.add_edge("report", END)
    return graph.compile(checkpointer=checkpointer)


automation_graph = build_graph()
