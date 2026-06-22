import pytest

from app.agents.graph import build_graph


def lead(**overrides):
    value = {
        "id": "lead-1",
        "name": "Asha Raman",
        "company": "Northstar Labs",
        "industry": "SaaS",
        "website": "https://example.com",
        "email": "asha@example.com",
        "phone": "+15555550123",
        "attributes": {"intent_score": 20},
    }
    value.update(overrides)
    return value


@pytest.mark.asyncio
async def test_lead_flow_stops_for_email_approval():
    graph = build_graph()
    result = await graph.ainvoke(
        {"lead": lead(), "approved_actions": [], "events": [], "errors": []},
        config={"configurable": {"thread_id": "high-value"}},
    )
    assert result["lead_score"] == 100
    assert result["priority"] == "high"
    assert result["pending_approval"]["kind"] == "outbound_email"
    assert "email_body" in result


@pytest.mark.asyncio
async def test_preapproved_flow_generates_report():
    graph = build_graph()
    pending = await graph.ainvoke(
        {
            "lead": lead(),
            "approved_actions": [],
            "events": [],
            "errors": [],
        },
        config={"configurable": {"thread_id": "approved"}},
    )
    pending["approved_actions"] = ["outbound_email"]
    pending["pending_approval"] = None
    result = await graph.ainvoke(pending)
    assert result["pending_approval"] is None
    assert result["report"]["status"] == "approved"
    assert len(result["events"]) == 4


@pytest.mark.asyncio
async def test_low_information_lead_is_nurtured():
    graph = build_graph()
    result = await graph.ainvoke(
        {
            "lead": lead(email=None, phone=None, website=None, industry=None, attributes={}),
            "approved_actions": [],
            "events": [],
            "errors": [],
        },
        config={"configurable": {"thread_id": "low"}},
    )
    assert result["lead_score"] == 25
    assert result["priority"] == "low"
    assert result["pending_approval"]["kind"] == "outbound_email"


@pytest.mark.asyncio
async def test_failed_agent_state_can_resume(monkeypatch):
    from app.agents import nodes

    original = nodes.router.complete

    async def fail(_request):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(nodes.router, "complete", fail)
    graph = build_graph()
    failed = await graph.ainvoke(
        {"lead": lead(), "approved_actions": [], "events": [], "errors": []}
    )
    assert failed["phase"] == "failed"
    assert failed["resume_node"] == "research"

    monkeypatch.setattr(nodes.router, "complete", original)
    resumed = await graph.ainvoke(failed)
    assert resumed["phase"] == "awaiting_approval"
    assert resumed["pending_approval"]["kind"] == "outbound_email"
