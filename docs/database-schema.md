# OrbitOps Database Schema

## 1. Design rules

- UUID primary keys are generated application-side.
- All business tables carry `tenant_id`; the authenticated tenant is never accepted from a request body.
- PostgreSQL is the production database. SQLite is used only for deterministic automated tests and local fallback.
- JSON columns hold bounded flexible metadata; high-value searchable fields remain typed columns.
- Foreign-key delete behavior is explicit: tenant and lead ownership generally cascades, while actor references commonly become null.
- `audit_logs` and `message_events` are append-only.

## 2. Entity relationship diagram

```mermaid
erDiagram
    TENANTS ||--o{ USERS : contains
    TENANTS ||--o{ LEADS : owns
    USERS o|--o{ LEADS : assigned_to
    LEADS ||--o{ WORKFLOW_RUNS : starts
    USERS ||--o{ WORKFLOW_RUNS : initiates
    WORKFLOW_RUNS ||--o{ APPROVALS : pauses_for
    USERS o|--o{ APPROVALS : decides
    WORKFLOW_RUNS ||--o| REPORTS : produces
    LEADS ||--o{ REPORTS : summarized_by
    WORKFLOW_RUNS ||--o{ AGENT_EXECUTIONS : records
    AGENT_EXECUTIONS ||--|| AGENT_EXECUTION_TRACES : traced_by
    AGENT_EXECUTIONS ||--o{ AGENT_EVALUATIONS : evaluated_by
    AGENT_EXECUTIONS ||--o{ AGENT_FEEDBACK : rated_by
    USERS ||--o{ AGENT_FEEDBACK : submits
    USERS ||--o{ PROMPT_VERSIONS : creates
    PROMPT_VERSIONS o|--o{ AGENT_EXECUTION_TRACES : used_by
    TENANTS ||--o{ MODEL_ROUTES : configures
    USERS ||--o{ PLAYGROUND_RUNS : executes
    LEADS ||--o{ COMMUNICATION_MESSAGES : receives
    WORKFLOW_RUNS o|--o{ COMMUNICATION_MESSAGES : drafts
    APPROVALS o|--o| COMMUNICATION_MESSAGES : authorizes
    COMMUNICATION_MESSAGES ||--o{ MESSAGE_EVENTS : has
    LEADS ||--o{ MEMORY_RECORDS : remembers
    USERS o|--o{ AUDIT_LOGS : acts

    TENANTS {
        uuid id PK
        string name
        string slug UK
        boolean active
        datetime created_at
        datetime updated_at
    }
    USERS {
        uuid id PK
        uuid tenant_id FK
        string email
        string password_hash
        enum role
        boolean active
    }
    LEADS {
        uuid id PK
        uuid tenant_id FK
        uuid owner_id FK
        string company
        int score
        enum priority
        json attributes
    }
    WORKFLOW_RUNS {
        uuid id PK
        uuid tenant_id FK
        uuid lead_id FK
        enum status
        string graph_thread_id UK
        json state_snapshot
        string current_agent
    }
    APPROVALS {
        uuid id PK
        uuid run_id FK
        enum kind
        enum status
        json payload
        datetime decided_at
    }
    REPORTS {
        uuid id PK
        uuid run_id FK
        uuid lead_id FK
        enum status
        binary content
        json metadata_json
    }
    AGENT_EXECUTIONS {
        uuid id PK
        uuid run_id FK
        string agent_name
        string provider
        string model
        int input_tokens
        int output_tokens
        float estimated_cost_usd
    }
    AGENT_EXECUTION_TRACES {
        uuid id PK
        uuid execution_id FK
        uuid prompt_version_id FK
        string task
        int retry_count
        json fallback_history
    }
    AGENT_EVALUATIONS {
        uuid id PK
        uuid execution_id FK
        float accuracy
        float completeness
        float relevance
        float hallucination_risk
        float overall_score
    }
    AGENT_FEEDBACK {
        uuid id PK
        uuid execution_id FK
        uuid user_id FK
        int rating
        string comment
    }
    PROMPT_VERSIONS {
        uuid id PK
        string agent_name
        int version
        text content
        boolean active
        json performance_metrics
    }
    MODEL_ROUTES {
        uuid id PK
        string agent_name
        string primary_provider
        string primary_model
        json fallback_order
    }
    PLAYGROUND_RUNS {
        uuid id PK
        uuid user_id FK
        string agent_name
        string provider
        json output_json
        string comparison_group
    }
    COMMUNICATION_MESSAGES {
        uuid id PK
        uuid lead_id FK
        uuid approval_id FK
        enum channel
        enum direction
        enum status
        string provider_message_id
        int attempt_count
        json classification
    }
    MESSAGE_EVENTS {
        uuid id PK
        uuid message_id FK
        string provider_event_id UK
        enum status
        datetime occurred_at
        string payload_digest
        json metadata_json
    }
    MEMORY_RECORDS {
        uuid id PK
        uuid lead_id FK
        string namespace
        text content
        string embedding_ref
        datetime expires_at
    }
    AUDIT_LOGS {
        uuid id PK
        uuid actor_id FK
        string action
        string resource_type
        string resource_id
        json details
        datetime created_at
    }
```

Every table in the diagram except `tenants` also carries `tenant_id`; repeated attributes are omitted where that makes the diagram readable.

## 3. Table catalog

| Table | Purpose | Important constraints/indexes |
|---|---|---|
| `tenants` | Workspace identity and activation | Unique indexed `slug` |
| `users` | Tenant users and roles | Unique `(tenant_id, email)` |
| `leads` | Prospect profile, score, qualification, owner | Indexed tenant; lead archive is represented in `attributes` |
| `workflow_runs` | Durable graph lifecycle and state snapshot | Unique `graph_thread_id`; indexed lead and tenant |
| `approvals` | Human approval request and decision | Unique `(run_id, kind)` prevents duplicate gates |
| `reports` | Generated PDF and report metadata | Unique `run_id` enforces one report per workflow |
| `agent_executions` | Per-node runtime and token/cost data | Indexed run and tenant |
| `agent_execution_traces` | Task timing, retry, prompt, fallback history | One trace per execution |
| `agent_evaluations` | Quality and hallucination-risk scores | Indexed execution and overall score |
| `agent_feedback` | User thumbs-up/down and comment | Unique `(execution_id, user_id)` |
| `prompt_versions` | Versioned per-agent prompt templates | Unique `(tenant_id, agent_name, version)` |
| `model_routes` | Primary and fallback model policy | Unique `(tenant_id, agent_name)` |
| `playground_runs` | Isolated model-comparison results | Indexed comparison group and agent |
| `communication_messages` | Current message lifecycle and retry state | Unique `(tenant_id, provider, provider_message_id)`; approval unique |
| `message_events` | Immutable provider lifecycle history | Globally unique indexed `provider_event_id`; DB trigger blocks mutation |
| `memory_records` | Tenant/lead-scoped memory and embedding reference | Indexed tenant, lead, namespace |
| `audit_logs` | Immutable security/business event history | Indexed tenant, action, created time; DB trigger blocks mutation |

## 4. Lifecycle enumerations

| Domain | Values |
|---|---|
| User role | `admin`, `manager`, `agent_viewer` |
| Workflow | `queued`, `running`, `waiting_approval`, `completed`, `failed`, `cancelled` |
| Approval | `pending`, `approved`, `rejected`, `changes_requested`, `expired` |
| Approval kind | `high_value_lead`, `outbound_email`, `whatsapp_campaign`, `report_publish` |
| Communication | `draft`, `approved`, `queued`, `sent`, `delivered`, `read`, `opened`, `clicked`, `replied`, `bounced`, `failed`, `dead_letter` |
| Report | `generated`, `failed` |

## 5. Migration policy

Alembic migrations are in `apps/api/migrations/versions`:

1. `0001_initial` creates the core model metadata.
2. `0002_immutable_audit` adds PostgreSQL audit immutability.
3. `0003_p1_approval_status` evolves approval status handling.
4. `0004_communication_delivery` adds messages/events and immutable event triggers.
5. `0005_ai_operations` adds prompt, routing, tracing, evaluation, feedback, and playground entities.

Production changes should use expand/migrate/contract: add nullable or backward-compatible structure, deploy compatible code, backfill, then enforce/drop in a later release. Back up and rehearse restore before destructive migrations.

## 6. Scale and retention guidance

- Move large PDF content to versioned, encrypted object storage and keep metadata plus checksum in `reports`.
- Partition `audit_logs`, `message_events`, and `agent_executions` by month once retention volume justifies it.
- Apply tenant-aware PostgreSQL row-level security as defense in depth.
- Define retention by data class: audit/security, communications, AI telemetry, customer memory, and report artifacts.
- Never delete immutable events through application endpoints; use controlled retention/archive jobs with legal approval.
