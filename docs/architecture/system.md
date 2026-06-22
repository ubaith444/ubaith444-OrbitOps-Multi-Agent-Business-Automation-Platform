# System Architecture

```mermaid
flowchart LR
    USER["Sales, Operations, AI Admin"] --> EDGE["Nginx / TLS / Rate Limit"]
    EDGE --> WEB["Next.js Console"]
    WEB --> API["FastAPI Control Plane"]
    API --> AUTH["JWT · RBAC · Tenant Scope"]
    API --> GRAPH["LangGraph Runtime"]
    GRAPH --> ROUTER["Multi-LLM Router"]
    ROUTER --> OPENAI["OpenAI"]
    ROUTER --> CLAUDE["Anthropic Claude"]
    ROUTER --> GEMINI["Google Gemini"]
    ROUTER --> MOCK["Deterministic Mock"]
    API --> PG[("PostgreSQL\nSystem of Record")]
    API --> REDIS[("Redis\nTTL Cache / Retry")]
    API --> REPORT["PDF Report Service"]
    API --> DELIVERY["Email / WhatsApp Adapters"]
    DELIVERY --> PROVIDERS["SendGrid · SES · Twilio"]
    PROVIDERS -->|"Signed webhook"| API
    API --> N8N["n8n Connector Gateway"]
    API --> OBS["Logs · Prometheus · LangSmith"]
```

## Boundaries

- FastAPI owns identity, tenancy, authorization, validation, approval policy, and audit.
- LangGraph owns resumable execution, not permission.
- PostgreSQL is authoritative; Redis failure cannot erase business state.
- Provider payloads are untrusted until signature, replay, and transition validation succeeds.

Full discussion: [../architecture.md](../architecture.md).
