# Changelog

All notable changes follow [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and Semantic Versioning pre-release conventions.

## [0.1.0-alpha] - 2026-06-22

### Added

- JWT authentication with HTTP-only frontend sessions.
- Multi-tenant RBAC for Admin, Manager, and Agent Viewer roles.
- Lead management and tenant-scoped dashboard analytics.
- LangGraph Sales → Research → Email → Approval → Report workflow.
- Durable workflow snapshots, failure classification, retry, and resume.
- Idempotent human approval decisions and immutable audit history.
- PDF report generation, preview, regeneration, and download.
- Email and WhatsApp lifecycle tracking with immutable message events.
- HMAC webhook verification, replay protection, duplicate handling, retry, and dead letter.
- Reply classification and lead-score updates.
- Multi-LLM routing, prompt versioning, execution telemetry, cost tracking, evaluation, feedback, and playground.
- Responsive enterprise SaaS console and mobile navigation.
- Pytest, Playwright, CI, documentation, architecture visuals, and portfolio assets.

### Security

- Removed runtime secret/password defaults.
- Added production configuration validation and comprehensive secret exclusions.
- Kept live LLM and delivery integrations disabled by default.

[0.1.0-alpha]: https://github.com/Ubaith444/orbitops/releases/tag/v0.1.0-alpha
