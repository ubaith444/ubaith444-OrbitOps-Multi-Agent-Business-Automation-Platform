from fastapi.testclient import TestClient

from app.main import app


def login(client: TestClient) -> tuple[dict[str, str], dict]:
    response = client.post(
        "/api/v1/auth/login",
        json={
            "workspace": "default",
            "email": "admin@example.com",
            "password": "TestOnly-Password-123!",
        },
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}, response.json()


def create_lead(client: TestClient, headers: dict[str, str], company: str) -> dict:
    response = client.post(
        "/api/v1/leads",
        headers=headers,
        json={
            "name": "P1 Test Lead",
            "company": company,
            "industry": "Automation",
            "website": "https://example.com",
            "email": "p1@example.com",
            "attributes": {"intent_score": 20},
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_refresh_lead_crud_filters_and_archive():
    with TestClient(app) as client:
        headers, tokens = login(client)
        refreshed = client.post(
            "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        )
        assert refreshed.status_code == 200

        lead = create_lead(client, headers, "P1 Searchable Company")
        changed = client.patch(
            f"/api/v1/leads/{lead['id']}",
            headers=headers,
            json={"priority": "high", "industry": "AI Operations"},
        )
        assert changed.status_code == 200
        assert changed.json()["industry"] == "AI Operations"
        found = client.get("/api/v1/leads?search=searchable&priority=high", headers=headers)
        assert any(item["id"] == lead["id"] for item in found.json())
        archived = client.delete(f"/api/v1/leads/{lead['id']}", headers=headers)
        assert archived.status_code == 204
        visible = client.get("/api/v1/leads?search=searchable", headers=headers)
        assert all(item["id"] != lead["id"] for item in visible.json())


def test_p1_dashboard_monitor_preview_regeneration_and_request_changes():
    with TestClient(app) as client:
        headers, _ = login(client)
        lead = create_lead(client, headers, "P1 Monitoring Company")
        run = client.post("/api/v1/workflows", headers=headers, json={"lead_id": lead["id"]})
        assert run.status_code == 202

        metrics = client.get("/api/v1/agents/metrics", headers=headers)
        assert metrics.status_code == 200
        assert {item["agent_name"] for item in metrics.json()} >= {"sales", "research", "email"}
        dashboard = client.get("/api/v1/dashboard/summary", headers=headers)
        assert dashboard.status_code == 200
        assert len(dashboard.json()["weekly_leads"]) == 7
        assert "recent_activity" in dashboard.json()

        approval = client.get("/api/v1/approvals?status=pending", headers=headers).json()[0]
        changed = client.post(
            f"/api/v1/approvals/{approval['id']}/decision",
            headers=headers,
            json={"action": "request_changes", "note": "Clarify the value proposition"},
        )
        assert changed.status_code == 200
        history = client.get("/api/v1/approvals", headers=headers).json()
        assert any(item["status"] == "changes_requested" for item in history)

        second = create_lead(client, headers, "P1 Report Company")
        client.post("/api/v1/workflows", headers=headers, json={"lead_id": second["id"]})
        approval = client.get("/api/v1/approvals?status=pending", headers=headers).json()[0]
        client.post(
            f"/api/v1/approvals/{approval['id']}/decision",
            headers=headers,
            json={"action": "approve", "note": "Approved"},
        )
        report = client.get("/api/v1/reports", headers=headers).json()[0]
        preview = client.get(f"/api/v1/reports/{report['id']}/preview", headers=headers)
        assert preview.status_code == 200
        assert preview.json()["report"]["title"].startswith("Lead intelligence")
        regenerated = client.post(f"/api/v1/reports/{report['id']}/regenerate", headers=headers)
        assert regenerated.status_code == 200


def test_admin_users_settings_and_audit_filters():
    with TestClient(app) as client:
        headers, _ = login(client)
        created = client.post(
            "/api/v1/users",
            headers=headers,
            json={
                "email": "p1-manager@example.com",
                "full_name": "P1 Manager",
                "password": "ManagerPass123!",
                "role": "manager",
            },
        )
        assert created.status_code == 201, created.text
        updated = client.patch(
            f"/api/v1/users/{created.json()['id']}",
            headers=headers,
            json={"role": "agent_viewer", "active": False},
        )
        assert updated.status_code == 200
        assert updated.json()["active"] is False

        settings = client.put(
            "/api/v1/settings",
            headers=headers,
            json={
                "company_name": "P1 OrbitOps Tenant",
                "llm_provider": "mock",
                "whatsapp_enabled": False,
                "email_enabled": False,
                "n8n_webhook_url": "https://example.com/webhook",
                "report_brand_name": "P1 Reports",
                "api_key": "secret-that-must-not-be-returned",
            },
        )
        assert settings.status_code == 200
        assert settings.json()["api_key_configured"] is True
        assert "secret-that-must-not-be-returned" not in settings.text
        audit = client.get("/api/v1/audit-logs?action=settings.updated", headers=headers)
        assert audit.status_code == 200
        assert audit.json() and all(item["action"] == "settings.updated" for item in audit.json())
