# Testing and quality strategy

| Layer | What to verify | Tooling / gate |
|---|---|---|
| Unit | scoring, routing, policy, schemas, prompts | pytest; deterministic adapters; ≥80% changed-code coverage |
| Graph | paths, approval stops/resume, retries, checkpoint restoration | pytest + in-memory checkpointer |
| API | auth, RBAC matrix, tenant isolation, idempotency, validation | FastAPI HTTP client + ephemeral PostgreSQL/Redis |
| Contract | LLM structured output, n8n callbacks, Twilio/CRM payloads | JSON Schema/Pydantic fixtures |
| Frontend | components, keyboard flows, loading/error states | Vitest/RTL + axe |
| End-to-end | capture → approval → delivery sandbox → report | Playwright in Compose environment |
| Resilience | provider timeout, Redis loss, worker crash, duplicate events | fault injection and replay tests |
| Security | dependency/image scan, SAST, secret scan, DAST, authorization fuzzing | Dependabot, Trivy, CodeQL, Gitleaks, ZAP |
| Evaluation | research groundedness, email quality, unsafe action rate | curated versioned dataset + human rubric |

Release gates require migrations tested both directions, no critical vulnerabilities, evaluation scores at or above the pinned baseline, backup restoration evidence, and canary health. Production smoke tests use synthetic tenants and provider sandboxes; never real recipients.

