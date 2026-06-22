import asyncio

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.main import app
from app.models import Lead, Role, Tenant, User


def auth_headers(
    client: TestClient, email: str = "admin@example.com", password: str = "TestOnly-Password-123!"
):
    response = client.post(
        "/api/v1/auth/login",
        json={"workspace": "default", "email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_complete_vertical_slice_and_idempotent_approval():
    with TestClient(app) as client:
        headers = auth_headers(client)
        lead_response = client.post(
            "/api/v1/leads",
            headers=headers,
            json={
                "name": "Asha Raman",
                "company": "Northstar Labs",
                "industry": "SaaS",
                "website": "https://example.com",
                "email": "asha@example.com",
                "phone": "+15555550123",
                "attributes": {"intent_score": 20},
            },
        )
        assert lead_response.status_code == 201, lead_response.text
        lead_id = lead_response.json()["id"]

        run_response = client.post("/api/v1/workflows", headers=headers, json={"lead_id": lead_id})
        assert run_response.status_code == 202, run_response.text
        assert run_response.json()["status"] == "waiting_approval"

        approvals = client.get("/api/v1/approvals?status=pending", headers=headers)
        assert approvals.status_code == 200
        assert len(approvals.json()) == 1
        approval_id = approvals.json()[0]["id"]

        decision = {"approved": True, "note": "Approved by integration test"}
        first = client.post(
            f"/api/v1/approvals/{approval_id}/decision", headers=headers, json=decision
        )
        second = client.post(
            f"/api/v1/approvals/{approval_id}/decision", headers=headers, json=decision
        )
        assert first.status_code == 200, first.text
        assert second.status_code == 200, second.text
        assert first.json()["status"] == "completed"
        assert second.json()["id"] == first.json()["id"]

        reports = client.get("/api/v1/reports", headers=headers)
        assert reports.status_code == 200
        matching_reports = [item for item in reports.json() if item["lead_id"] == lead_id]
        assert len(matching_reports) == 1
        report_id = matching_reports[0]["id"]
        download = client.get(f"/api/v1/reports/{report_id}/download", headers=headers)
        assert download.status_code == 200
        assert download.content.startswith(b"%PDF")

        audit = client.get("/api/v1/audit-logs", headers=headers)
        assert audit.status_code == 200
        actions = {item["action"] for item in audit.json()}
        assert {
            "auth.login",
            "lead.created",
            "workflow.started",
            "agent.step_completed",
            "approval.approved",
            "report.generated",
        }.issubset(actions)


async def seed_second_tenant_and_viewer() -> tuple[str, str]:
    async with SessionLocal() as db:
        default = await db.scalar(select(Tenant).where(Tenant.slug == "default"))
        viewer = User(
            tenant_id=default.id,
            email="viewer@example.com",
            full_name="Agent Viewer",
            password_hash=hash_password("ViewerPass123!"),
            role=Role.AGENT_VIEWER,
        )
        other = Tenant(name="Other Tenant", slug="other")
        db.add_all([viewer, other])
        await db.flush()
        other_user = User(
            tenant_id=other.id,
            email="other@example.com",
            full_name="Other Admin",
            password_hash=hash_password("OtherPass123!"),
            role=Role.ADMIN,
        )
        db.add(other_user)
        await db.flush()
        foreign_lead = Lead(
            tenant_id=other.id,
            owner_id=other_user.id,
            name="Foreign Lead",
            company="Private Company",
        )
        db.add(foreign_lead)
        await db.commit()
        return str(foreign_lead.id), str(viewer.id)


def test_rbac_and_tenant_isolation():
    with TestClient(app) as client:
        foreign_lead_id, _ = asyncio.run(seed_second_tenant_and_viewer())
        admin_headers = auth_headers(client)
        assert (
            client.get(f"/api/v1/leads/{foreign_lead_id}", headers=admin_headers).status_code == 404
        )

        viewer_headers = auth_headers(client, "viewer@example.com", "ViewerPass123!")
        forbidden = client.post(
            "/api/v1/leads",
            headers=viewer_headers,
            json={"name": "Blocked", "company": "Blocked Company"},
        )
        assert forbidden.status_code == 403
        assert client.get("/api/v1/leads", headers=viewer_headers).status_code == 200
        assert client.get("/api/v1/audit-logs", headers=viewer_headers).status_code == 403
