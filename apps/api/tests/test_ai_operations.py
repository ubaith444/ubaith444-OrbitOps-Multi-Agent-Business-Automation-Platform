import asyncio

import pytest
from fastapi.testclient import TestClient

from app.agents.llm_router import CompletionRequest, CompletionResult, ModelRouter
from app.core.database import SessionLocal
from app.core.security import TokenType, create_token, hash_password
from app.main import app
from app.models import Role, Tenant, User


def auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={
            "workspace": "default",
            "email": "admin@example.com",
            "password": "TestOnly-Password-123!",
        },
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


class FailingProvider:
    name = "openai"

    async def complete(self, request, model):
        raise TimeoutError("provider timed out")


class SuccessfulProvider:
    name = "anthropic"

    async def complete(self, request, model):
        return CompletionResult(
            content={"answer": "fallback worked"},
            provider=self.name,
            model=model,
            input_tokens=12,
            output_tokens=8,
            estimated_cost_usd=0.002,
        )


@pytest.mark.asyncio
async def test_multi_llm_fallback_records_attempt_history():
    router = ModelRouter(providers={"openai": FailingProvider(), "anthropic": SuccessfulProvider()})
    result = await router.complete(
        CompletionRequest(task="test", prompt="route me", agent_name="email"),
        route=[("openai", "gpt-test"), ("anthropic", "claude-test")],
    )
    assert result.provider == "anthropic"
    assert result.input_tokens == 12
    assert [item["status"] for item in result.fallback_history] == ["failed", "completed"]
    assert result.fallback_history[0]["error"] == "TimeoutError"


def create_completed_workflow(client: TestClient, headers: dict[str, str]) -> str:
    lead = client.post(
        "/api/v1/leads",
        headers=headers,
        json={
            "name": "P2 Agent Lead",
            "company": "Reliability Labs",
            "industry": "AI",
            "email": "p2@example.com",
            "attributes": {"intent_score": 20},
        },
    )
    lead_id = lead.json()["id"]
    started = client.post("/api/v1/workflows", headers=headers, json={"lead_id": lead_id})
    assert started.status_code == 202
    approval = client.get("/api/v1/approvals?status=pending", headers=headers).json()[0]
    completed = client.post(
        f"/api/v1/approvals/{approval['id']}/decision",
        headers=headers,
        json={"action": "approve", "note": "P2 test"},
    )
    assert completed.json()["status"] == "completed"
    return completed.json()["id"]


def test_observability_cost_evaluation_feedback_prompts_routes_and_playground():
    with TestClient(app) as client:
        headers = auth_headers(client)
        run_id = create_completed_workflow(client, headers)
        history = client.get("/api/v1/ai-ops/executions", headers=headers)
        assert history.status_code == 200, history.text
        executions = [item for item in history.json() if item["run_id"] == run_id]
        assert {item["agent_name"] for item in executions} == {
            "sales",
            "research",
            "email",
            "report",
        }
        llm_executions = [item for item in executions if item["agent_name"] != "sales"]
        assert all(item["input_tokens"] > 0 for item in llm_executions)
        assert all(item["latency_ms"] >= 0 for item in executions)
        assert all(item["evaluation_score"] is not None for item in executions)
        assert any(item["fallback_history"] for item in llm_executions)

        summary = client.get("/api/v1/ai-ops/summary", headers=headers)
        assert summary.status_code == 200
        data = summary.json()
        assert data["total_executions"] >= 4
        assert data["success_rate"] == 100
        assert data["costs"]["total_input_tokens"] > 0
        assert data["costs"]["by_agent"]
        assert data["costs"]["by_provider"]
        assert data["costs"]["by_user"]

        execution_id = executions[0]["id"]
        feedback = client.post(
            f"/api/v1/ai-ops/executions/{execution_id}/feedback",
            headers=headers,
            json={"rating": 1, "comment": "Useful output"},
        )
        assert feedback.status_code == 200
        updated = client.post(
            f"/api/v1/ai-ops/executions/{execution_id}/feedback",
            headers=headers,
            json={"rating": -1, "comment": "Needs citations"},
        )
        assert updated.status_code == 200
        assert updated.json()["rating"] == -1
        evaluations = client.get(
            f"/api/v1/ai-ops/executions/{execution_id}/evaluations", headers=headers
        )
        assert evaluations.status_code == 200
        assert 0 <= evaluations.json()[0]["hallucination_risk"] <= 1

        prompt = client.post(
            "/api/v1/ai-ops/prompts",
            headers=headers,
            json={
                "agent_name": "email",
                "name": "Evidence-first outreach",
                "content": (
                    "Draft concise outreach using only supplied evidence and request approval."
                ),
                "activate": True,
            },
        )
        assert prompt.status_code == 201, prompt.text
        assert prompt.json()["version"] >= 2
        prompts = client.get("/api/v1/ai-ops/prompts?agent_name=email", headers=headers)
        assert sum(1 for item in prompts.json() if item["active"]) == 1
        assert "average_evaluation" in prompts.json()[0]["performance_metrics"]

        route = client.put(
            "/api/v1/ai-ops/routes/email",
            headers=headers,
            json={
                "primary": {"provider": "openai", "model": "gpt-test"},
                "fallbacks": [
                    {"provider": "anthropic", "model": "claude-test"},
                    {"provider": "google", "model": "gemini-test"},
                    {"provider": "mock", "model": "local-deterministic"},
                ],
            },
        )
        assert route.status_code == 200
        assert route.json()["fallback_order"][0]["provider"] == "anthropic"

        playground = client.post(
            "/api/v1/ai-ops/playground",
            headers=headers,
            json={
                "agent_name": "email",
                "prompt": "Create a short test email",
                "candidates": [{"provider": "mock", "model": "local-deterministic"}],
            },
        )
        assert playground.status_code == 200, playground.text
        assert playground.json()[0]["output_json"]["agent"] == "email"


async def seed_viewer() -> dict[str, str]:
    async with SessionLocal() as db:
        tenant = Tenant(name="P2 Isolated Tenant", slug="p2-isolated")
        db.add(tenant)
        await db.flush()
        user = User(
            tenant_id=tenant.id,
            email="p2-viewer@example.com",
            full_name="P2 Viewer",
            password_hash=hash_password("P2ViewerPass123!"),
            role=Role.AGENT_VIEWER,
        )
        db.add(user)
        await db.commit()
        token = create_token(user.id, tenant.id, user.role.value, TokenType.ACCESS)
        return {"Authorization": f"Bearer {token}"}


def test_ai_ops_rbac_and_tenant_scoping():
    with TestClient(app) as client:
        admin_headers = auth_headers(client)
        create_completed_workflow(client, admin_headers)
        viewer_headers = asyncio.run(seed_viewer())
        summary = client.get("/api/v1/ai-ops/summary", headers=viewer_headers)
        assert summary.status_code == 200
        assert summary.json()["total_executions"] == 0
        executions = client.get("/api/v1/ai-ops/executions", headers=viewer_headers)
        assert executions.status_code == 200
        assert executions.json() == []
        assert client.get("/api/v1/ai-ops/prompts", headers=viewer_headers).status_code == 403
        assert (
            client.post(
                "/api/v1/ai-ops/playground",
                headers=viewer_headers,
                json={"agent_name": "email", "prompt": "blocked", "candidates": []},
            ).status_code
            == 403
        )
