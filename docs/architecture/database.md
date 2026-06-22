# Database Schema

```mermaid
erDiagram
    TENANT ||--o{ USER : contains
    TENANT ||--o{ LEAD : owns
    USER o|--o{ LEAD : assigned
    LEAD ||--o{ WORKFLOW_RUN : starts
    WORKFLOW_RUN ||--o{ APPROVAL : pauses
    WORKFLOW_RUN ||--o| REPORT : produces
    WORKFLOW_RUN ||--o{ AGENT_EXECUTION : measures
    AGENT_EXECUTION ||--|| EXECUTION_TRACE : traces
    AGENT_EXECUTION ||--o{ EVALUATION : evaluates
    AGENT_EXECUTION ||--o{ FEEDBACK : receives
    PROMPT_VERSION o|--o{ EXECUTION_TRACE : configures
    LEAD ||--o{ COMMUNICATION_MESSAGE : receives
    COMMUNICATION_MESSAGE ||--o{ MESSAGE_EVENT : records
    LEAD ||--o{ MEMORY_RECORD : remembers
    TENANT ||--o{ AUDIT_LOG : audits
```

All business entities carry `tenant_id`. Important uniqueness boundaries include `(run_id, approval_kind)`, one report per run, one feedback item per execution/user, and globally unique provider event IDs. Audit and message events are append-only.

Full catalog: [../database-schema.md](../database-schema.md).
