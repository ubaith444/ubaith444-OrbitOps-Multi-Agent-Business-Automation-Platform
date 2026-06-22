# Resume-ready project description

**Multi-Agent Business Automation Platform — FastAPI, LangGraph, Next.js, PostgreSQL, Redis, Docker, AWS**

Designed and implemented an approval-first, multi-tenant SaaS platform orchestrating sales qualification, company research, personalized outreach, WhatsApp follow-up, and executive reporting agents. Built resumable LangGraph workflows with human checkpoints, provider-neutral model routing and fallbacks, tenant-scoped RBAC, durable memory, audit trails, cost/latency telemetry, n8n connector boundaries, and containerized CI/CD architecture. Added deterministic agent tests and safe mock delivery adapters so complete workflows can be evaluated without paid models or real customer contact.

Interview talking points:

- Why PostgreSQL remains authoritative while Redis is disposable.
- How approval state, idempotency, and immutable payloads prevent duplicate or altered sends.
- How model routing balances capability, cost, privacy, and provider health.
- How tenant isolation, prompt-injection defenses, consent rules, and auditability sit outside the LLM.
- How to evolve from Compose/EC2 to autoscaled ECS, RDS, ElastiCache, S3, and a queue.

