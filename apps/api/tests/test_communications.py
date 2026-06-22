import asyncio
import hashlib
import hmac
import json
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.core.config import settings
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
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create_lead(client: TestClient, headers: dict[str, str], company: str = "Comms Corp") -> str:
    response = client.post(
        "/api/v1/leads",
        headers=headers,
        json={
            "name": "Ravi Kumar",
            "company": company,
            "industry": "SaaS",
            "email": "ravi@example.com",
            "phone": "+15555550110",
            "attributes": {"intent_score": 20},
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def signed_webhook(
    client: TestClient,
    channel: str,
    payload: dict,
    *,
    secret: str | None = None,
    timestamp: int | None = None,
):
    raw = json.dumps(payload, separators=(",", ":")).encode()
    sent_at = str(timestamp or int(datetime.now(UTC).timestamp()))
    key = secret or (
        settings.email_webhook_secret if channel == "email" else settings.whatsapp_webhook_secret
    )
    signature = hmac.new(key.encode(), sent_at.encode() + b"." + raw, hashlib.sha256).hexdigest()
    return client.post(
        f"/api/v1/webhooks/{channel}",
        content=raw,
        headers={
            "Content-Type": "application/json",
            "X-OrbitOps-Timestamp": sent_at,
            "X-OrbitOps-Signature": f"sha256={signature}",
        },
    )


def prepare_sent_email(client: TestClient, headers: dict[str, str]) -> tuple[str, dict]:
    lead_id = create_lead(client, headers)
    run = client.post("/api/v1/workflows", headers=headers, json={"lead_id": lead_id})
    assert run.status_code == 202
    approval = client.get("/api/v1/approvals?status=pending", headers=headers).json()[0]
    approved = client.post(
        f"/api/v1/approvals/{approval['id']}/decision",
        headers=headers,
        json={"action": "approve", "note": "Approved for delivery"},
    )
    assert approved.status_code == 200
    message = client.get(f"/api/v1/communications?lead_id={lead_id}", headers=headers).json()[0]
    assert message["status"] == "approved"
    sent = client.post(f"/api/v1/communications/{message['id']}/send", headers=headers)
    assert sent.status_code == 200
    assert sent.json()["status"] == "sent"
    return lead_id, sent.json()


def test_email_delivery_webhooks_reply_classification_and_duplicate_handling():
    with TestClient(app) as client:
        headers = auth_headers(client)
        lead_id, message = prepare_sent_email(client, headers)
        base = {
            "message_id": message["provider_message_id"],
            "timestamp": datetime.now(UTC).isoformat(),
            "metadata": {"provider": "mock"},
        }
        delivered_payload = {**base, "event_id": "email-delivered-1", "status": "delivered"}
        delivered = signed_webhook(client, "email", delivered_payload)
        assert delivered.status_code == 200, delivered.text
        assert delivered.json()["status"] == "delivered"

        duplicate = signed_webhook(client, "email", delivered_payload)
        assert duplicate.status_code == 200
        assert duplicate.json()["duplicate"] is True
        conflicting = signed_webhook(
            client, "email", {**delivered_payload, "metadata": {"changed": True}}
        )
        assert conflicting.status_code == 409

        for event_id, event_status in (("email-open-1", "opened"), ("email-click-1", "clicked")):
            response = signed_webhook(
                client,
                "email",
                {**base, "event_id": event_id, "status": event_status},
            )
            assert response.status_code == 200
        reply = signed_webhook(
            client,
            "email",
            {
                **base,
                "event_id": "email-reply-1",
                "status": "replied",
                "reply_text": "I am interested. Please schedule a demo next week.",
            },
        )
        assert reply.status_code == 200, reply.text
        lead = client.get(f"/api/v1/leads/{lead_id}", headers=headers).json()
        assert lead["qualification_status"] == "customer-replied"
        assert lead["attributes"]["response_intent"] == "Meeting Requested"
        assert lead["recommended_action"] == "Schedule Demo"
        assert lead["score"] >= 88

        events = client.get(
            f"/api/v1/communications/{message['id']}/events", headers=headers
        ).json()
        assert [item["status"] for item in events][-4:] == [
            "delivered",
            "opened",
            "clicked",
            "replied",
        ]
        timeline = client.get(f"/api/v1/leads/{lead_id}/timeline", headers=headers)
        assert timeline.status_code == 200
        assert any(item["label"] == "Email Replied" for item in timeline.json())
        dashboard = client.get("/api/v1/dashboard/summary", headers=headers).json()
        assert dashboard["communication"]["emails_sent"] >= 1
        assert dashboard["communication"]["open_rate"] > 0
        assert dashboard["communication"]["reply_rate"] > 0


def test_webhook_signature_replay_window_and_tenant_isolation():
    with TestClient(app) as client:
        headers = auth_headers(client)
        _, message = prepare_sent_email(client, headers)
        payload = {
            "event_id": "security-event-1",
            "message_id": message["provider_message_id"],
            "status": "delivered",
            "timestamp": datetime.now(UTC).isoformat(),
        }
        invalid = signed_webhook(client, "email", payload, secret="wrong-secret")
        assert invalid.status_code == 401
        stale = signed_webhook(client, "email", payload, timestamp=1)
        assert stale.status_code == 401
        other_headers = asyncio.run(seed_other_tenant())
        forbidden = client.get(
            f"/api/v1/communications/{message['id']}/events", headers=other_headers
        )
        assert forbidden.status_code == 404


async def seed_other_tenant() -> dict[str, str]:
    async with SessionLocal() as db:
        tenant = Tenant(name="Communication Other", slug="communication-other")
        db.add(tenant)
        await db.flush()
        user = User(
            tenant_id=tenant.id,
            email="communications-other@example.com",
            full_name="Other Tenant Admin",
            password_hash=hash_password("OtherTenantPass123!"),
            role=Role.ADMIN,
        )
        db.add(user)
        await db.commit()
        token = create_token(user.id, tenant.id, user.role.value, TokenType.ACCESS)
        return {"Authorization": f"Bearer {token}"}


def test_provider_outage_retry_and_dead_letter_queue():
    with TestClient(app) as client:
        headers = auth_headers(client)
        lead_id = create_lead(client, headers, "Outage Corp")
        draft = client.post(
            "/api/v1/communications",
            headers=headers,
            json={
                "lead_id": lead_id,
                "channel": "whatsapp",
                "provider": "outage",
                "body": "Approved test message",
            },
        )
        assert draft.status_code == 201
        message_id = draft.json()["id"]
        approved = client.post(f"/api/v1/communications/{message_id}/approve", headers=headers)
        assert approved.json()["status"] == "approved"
        first = client.post(f"/api/v1/communications/{message_id}/send", headers=headers)
        assert first.json()["status"] == "failed"
        second = client.post(f"/api/v1/communications/{message_id}/retry", headers=headers)
        assert second.json()["status"] == "failed"
        third = client.post(f"/api/v1/communications/{message_id}/retry", headers=headers)
        assert third.json()["status"] == "dead_letter"
        blocked = client.post(f"/api/v1/communications/{message_id}/retry", headers=headers)
        assert blocked.status_code == 409
        events = client.get(f"/api/v1/communications/{message_id}/events", headers=headers).json()
        assert events[-1]["status"] == "dead_letter"
