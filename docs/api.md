# OrbitOps API Reference

## 1. Service contract

- API version: `0.1.0`
- Base path: `/api/v1`
- OpenAPI UI: `/docs`
- OpenAPI document: `/openapi.json`
- Media type: `application/json`, except PDF downloads and Prometheus metrics
- Authentication: `Authorization: Bearer <access_token>`
- Tenant source: verified JWT claim; never a request-body field

The generated OpenAPI document is the field-level contract. This document explains authorization, lifecycle behavior, and operational use.

## 2. Authentication

### Login

```http
POST /api/v1/auth/login
Content-Type: application/json
```

```json
{
  "workspace": "default",
  "email": "admin@example.com",
  "password": "a-secret-password"
}
```

```json
{
  "access_token": "<jwt>",
  "refresh_token": "<jwt>",
  "token_type": "bearer"
}
```

Access tokens default to 30 minutes and refresh tokens to 14 days. The Next.js application exchanges these through same-origin auth routes and stores them in secure HTTP-only cookies. Direct API clients may use the token pair themselves.

### Protected request

```http
GET /api/v1/auth/me
Authorization: Bearer <access_token>
```

The API reloads the active user using both the token subject and tenant claim. Expired tokens, inactive users, unknown tenants, and token-type mismatches return `401`.

## 3. Endpoint catalog

Role notation: **Any** means any authenticated `admin`, `manager`, or `agent_viewer`. Full permission details are in the [RBAC matrix](rbac-matrix.md).

### Health and authentication

| Method | Path | Access | Purpose |
|---|---|---|---|
| GET | `/health/live` | Public/internal | Process liveness |
| GET | `/health/ready` | Public/internal | Database readiness |
| GET | `/metrics` | Internal | Prometheus exposition; omitted from OpenAPI |
| POST | `/api/v1/auth/login` | Public | Exchange workspace credentials for token pair |
| POST | `/api/v1/auth/refresh` | Refresh token | Issue a new token pair |
| GET | `/api/v1/auth/me` | Any | Current active tenant user |

### Leads and workflows

| Method | Path | Access | Purpose |
|---|---|---|---|
| POST | `/api/v1/leads` | Admin, Manager | Create and audit a lead |
| GET | `/api/v1/leads` | Any | Filtered/paginated tenant lead list |
| GET | `/api/v1/leads/{lead_id}` | Any | Tenant-scoped lead detail |
| PATCH | `/api/v1/leads/{lead_id}` | Admin, Manager | Update allowed lead fields |
| DELETE | `/api/v1/leads/{lead_id}` | Admin, Manager | Soft archive via lead attributes |
| POST | `/api/v1/workflows` | Admin, Manager | Run Sales → Research → Email → Approval; returns `202` |
| GET | `/api/v1/workflows` | Any | Up to 100 recent runs, optionally by lead |
| POST | `/api/v1/workflows/{run_id}/retry` | Admin, Manager | Resume a failed run from `resume_node` |
| GET | `/api/v1/leads/{lead_id}/timeline` | Any | Unified business, workflow, communication, and audit timeline |

Lead query parameters: `priority`, `search`, `qualification_status`, `include_archived`, `limit` (1–200), and `offset`.

### Approvals and reports

| Method | Path | Access | Purpose |
|---|---|---|---|
| GET | `/api/v1/approvals` | Any | Approval inbox, optionally filtered by status |
| POST | `/api/v1/approvals/{approval_id}/decision` | Admin, Manager | Approve, reject, or request changes |
| GET | `/api/v1/reports` | Any | Reports filtered by lead or search text |
| GET | `/api/v1/reports/{report_id}/preview` | Any | Structured report preview |
| POST | `/api/v1/reports/{report_id}/regenerate` | Admin, Manager | Re-render report from saved workflow state |
| GET | `/api/v1/reports/{report_id}/download` | Any | Download `application/pdf` |

Approval bodies accept the preferred `action` field:

```json
{ "action": "approve", "note": "Reviewed against source data" }
```

Allowed actions are `approve`, `reject`, and `request_changes`. Repeating the same final decision returns the existing run; a conflicting decision returns `409`.

### Communications and webhooks

| Method | Path | Access | Purpose |
|---|---|---|---|
| GET | `/api/v1/communications` | Any | Filter by lead, channel, or status |
| POST | `/api/v1/communications` | Admin, Manager | Create an email/WhatsApp draft |
| POST | `/api/v1/communications/{message_id}/approve` | Admin, Manager | Approve a draft |
| POST | `/api/v1/communications/{message_id}/send` | Admin, Manager | Queue/send through configured adapter |
| POST | `/api/v1/communications/{message_id}/retry` | Admin, Manager | Requeue a failed message |
| GET | `/api/v1/communications/{message_id}/events` | Any | Immutable lifecycle events |
| POST | `/api/v1/webhooks/{channel}` | Signed provider | Process email or WhatsApp event |

Supported channels are `email` and `whatsapp`. Provider webhook requests require:

```http
X-OrbitOps-Timestamp: <unix-seconds>
X-OrbitOps-Signature: sha256=<hex-hmac>
```

The signature input is `<timestamp>.<raw-request-body>` using the channel secret. Requests outside `WEBHOOK_TOLERANCE_SECONDS`, invalid signatures, unknown messages, or invalid transitions are rejected. Duplicate `event_id` values are acknowledged without applying the transition twice.

Example webhook:

```json
{
  "event_id": "evt_01J...",
  "message_id": "provider-message-123",
  "status": "replied",
  "timestamp": "2026-06-22T10:41:00Z",
  "metadata": {"provider_region": "in"},
  "reply_text": "Interested — please schedule a demo."
}
```

### Dashboard, monitoring, and audit

| Method | Path | Access | Purpose |
|---|---|---|---|
| GET | `/api/v1/dashboard/summary` | Any | Tenant KPIs, funnels, communication analytics, recent activity |
| GET | `/api/v1/agents/metrics` | Any | Per-agent success, failure, latency, tokens, and cost |
| GET | `/api/v1/audit-logs` | Admin, Manager | Filtered immutable tenant audit events |

Audit filters: `action`, `resource_type`, `actor_id`, `date_from`, and `date_to`.

### AI Operations

All paths below are under `/api/v1/ai-ops`.

| Method | Path | Access | Purpose |
|---|---|---|---|
| GET | `/executions` | Any | Filtered execution history; limit 1–500 |
| GET | `/summary` | Any | Reliability, evaluation, feedback, token, and cost summary |
| GET | `/executions/{id}/evaluations` | Any | Quality evaluations for a tenant execution |
| POST | `/executions/{id}/feedback` | Any | Create/update the current user's rating |
| GET | `/prompts` | Admin | Prompt versions and derived performance |
| POST | `/prompts` | Admin | Create a new prompt version |
| POST | `/prompts/{id}/activate` | Admin | Activate one version for its agent |
| GET | `/routes` | Admin | Model route policies |
| PUT | `/routes/{agent_name}` | Admin | Set primary and up to four fallback models |
| POST | `/playground` | Admin | Compare up to three model candidates without production mutation |

### Administration

| Method | Path | Access | Purpose |
|---|---|---|---|
| GET | `/api/v1/users` | Admin | Tenant users |
| POST | `/api/v1/users` | Admin | Create/invite tenant user |
| PATCH | `/api/v1/users/{user_id}` | Admin | Change name, role, or active status |
| GET | `/api/v1/settings` | Admin | Tenant branding and integration state |
| PUT | `/api/v1/settings` | Admin | Update settings and secret configuration |

Stored secret material is never returned by the settings API; responses expose only configuration state.

## 4. Core request examples

### Create lead

```json
{
  "name": "Asha Raman",
  "company": "Northstar Labs",
  "industry": "B2B SaaS",
  "website": "https://example.com",
  "email": "asha@example.com",
  "phone": "+15555550123",
  "source": "website",
  "attributes": {"intent_score": 18, "employee_band": "51-200"}
}
```

### Start workflow

```json
{
  "lead_id": "4c0e831f-8100-4b94-a949-96354ff965d4",
  "auto_approve_low_risk": false
}
```

### Update model route

```json
{
  "primary": {"provider": "google", "model": "gemini-2.5-flash"},
  "fallbacks": [
    {"provider": "openai", "model": "gpt-4.1-mini"},
    {"provider": "anthropic", "model": "claude-sonnet-4-20250514"},
    {"provider": "mock", "model": "local-deterministic"}
  ]
}
```

## 5. Status and error semantics

| Code | Meaning |
|---:|---|
| 200/201 | Successful read or creation |
| 202 | Workflow accepted/executed to its current boundary |
| 204 | Lead archived successfully |
| 400 | Invalid domain transition or request state |
| 401 | Missing, invalid, expired, or inactive identity |
| 403 | Authenticated but role is insufficient |
| 404 | Resource absent from the authenticated tenant |
| 409 | Conflicting idempotent decision or duplicate domain state |
| 422 | Pydantic validation failure |
| 500 | Sanitized internal error with request ID |

Unhandled errors use:

```json
{"detail": "Internal server error", "request_id": "<correlation-id>"}
```

Provider stack traces and secrets must never be returned.

## 6. Compatibility expectations

- Additive response fields are backward compatible; clients should ignore unknown fields.
- Removing or changing field meaning requires a versioned endpoint.
- Enum additions may require client updates; document them in release notes.
- Write endpoints should gain a standard `Idempotency-Key` contract before public third-party use. Approval and webhook writes already have domain-specific idempotency.
