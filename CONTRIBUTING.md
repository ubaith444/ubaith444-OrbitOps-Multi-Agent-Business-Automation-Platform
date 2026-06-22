# Contributing to OrbitOps

Thank you for helping improve reliable, human-controlled agent systems.

## Development workflow

1. Fork the repository and create a branch from `main`.
2. Use a focused branch name such as `feat/provider-health` or `fix/approval-race`.
3. Keep changes tenant-safe, auditable, and deny-by-default.
4. Add or update tests for behavior, authorization, and failure paths.
5. Update documentation when changing APIs, schemas, roles, workflows, or deployment.
6. Run the quality gates before opening a pull request.

```bash
cd apps/api
ruff check app tests
pytest -q

cd ../web
pnpm typecheck
pnpm build
pnpm test:e2e
```

## Commit convention

OrbitOps uses Conventional Commits:

```text
feat(auth): implement JWT authentication and RBAC
feat(workflow): add LangGraph workflow orchestration
feat(approval): implement human approval gates
feat(communication): add webhook security and retry queues
fix(tenant): prevent cross-tenant execution lookup
test(e2e): add Playwright workflow coverage
docs(architecture): document durable state boundaries
chore(release): prepare v0.1.0-alpha
```

## Pull request expectations

- Explain what changed and why.
- Identify security, tenant, migration, cost, and delivery impact.
- Include screenshots for UI changes.
- Include test evidence and known limitations.
- Never include credentials, real customer data, or production webhook payloads.
- Keep live delivery disabled in automated tests.

## Architecture invariants

- PostgreSQL remains the durable source of truth.
- Tenant scope comes from the verified identity, never request data.
- LLM output cannot authorize business actions.
- Outbound actions require deterministic policy and configured approval.
- Audit and provider-event histories remain append-only.

By participating, you agree to the [Code of Conduct](CODE_OF_CONDUCT.md).
