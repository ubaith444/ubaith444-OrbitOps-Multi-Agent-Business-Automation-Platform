# OrbitOps Documentation

This directory is the source of truth for the implemented OrbitOps platform. Diagrams use Mermaid and render directly in GitHub.

## Start here

| Document | Purpose |
|---|---|
| [System architecture](architecture.md) | Components, trust boundaries, data flow, reliability, and observability |
| [Database schema](database-schema.md) | Entity relationship diagram, table catalog, constraints, and tenancy rules |
| [LangGraph workflow](langgraph-workflow.md) | Graph nodes, state transitions, approval/resume, retries, and persistence |
| [API reference](api.md) | Authentication, endpoint catalog, request examples, errors, and webhooks |
| [RBAC matrix](rbac-matrix.md) | Admin, manager, and agent-viewer permissions with tenant-isolation rules |
| [Deployment guide](deployment.md) | Docker Compose, production configuration, AWS topology, rollout, and rollback |
| [Testing report](testing-report.md) | Current automated evidence, coverage map, commands, limitations, and release verdict |

## Supporting documents

- [Portfolio assets](assets/README.md)
- [Frontend and wireframes](frontend-and-wireframes.md)
- [n8n workflows](n8n-workflows.md)
- [Testing strategy](testing-strategy.md)
- [Development roadmap](development-roadmap.md)
- [Portfolio presentation](portfolio.md)

## Documentation rules

1. Update the relevant document in the same pull request as a contract, schema, permission, workflow, or deployment change.
2. Treat code and migrations as authoritative if documentation drifts.
3. Never place credentials, customer data, raw model prompts, or provider webhook payloads in documentation.
4. Update the testing report only from a reproducible test run and record the date and environment.
