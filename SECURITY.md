# Security Policy

## Supported versions

| Version | Supported |
|---|---|
| `0.1.x-alpha` | Yes |
| Earlier prototypes | No |

## Reporting a vulnerability

Do not open a public issue for suspected vulnerabilities or credential exposure. Use GitHub's private vulnerability reporting for `Ubaith444/orbitops` after publication, or contact the maintainer privately through [Ubaith444](https://github.com/Ubaith444).

Include:

- Affected component and version/commit.
- Reproduction steps or proof of concept.
- Security impact and required preconditions.
- Suggested remediation, if known.

Please allow a reasonable remediation window before public disclosure.

## Security model

- JWT identity and role checks are enforced by FastAPI.
- Tenant identity is derived from the verified token.
- Outbound communication is disabled by default and approval-gated.
- Webhooks require timestamped HMAC signatures and replay protection.
- Audit and message-event tables are append-only.
- Real provider credentials must be supplied through environment/secret management.

See [docs/rbac-matrix.md](docs/rbac-matrix.md) and [docs/architecture.md](docs/architecture.md).
