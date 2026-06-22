# Environment Configuration

Copy `.env.example` to `.env`. Never commit `.env` or provider credential files.

## Required for local Docker Compose

| Variable | Secret | Description |
|---|:---:|---|
| `APP_SECRET_KEY` | Yes | JWT signing secret, minimum 32 random characters |
| `POSTGRES_DB` | No | Local database name |
| `POSTGRES_USER` | No | Local database user |
| `POSTGRES_PASSWORD` | Yes | Local database password |
| `DATABASE_URL` | Yes | Async SQLAlchemy URL containing DB credentials |
| `BOOTSTRAP_ADMIN_EMAIL` | No | Development/test bootstrap identity |
| `BOOTSTRAP_ADMIN_PASSWORD` | Yes | Development/test bootstrap password, minimum 12 characters |

## Security and session policy

| Variable | Default/example behavior |
|---|---|
| `APP_ENV` | `development`; use `staging` or `production` explicitly |
| `CORS_ORIGINS` | Comma-separated exact origins; wildcard rejected outside local/test |
| `ACCESS_TOKEN_MINUTES` | 30 |
| `REFRESH_TOKEN_DAYS` | 14 |

## AI providers

Real models require `LIVE_LLM_ENABLED=true` plus the corresponding key. Mock remains deterministic and free.

- `OPENAI_API_KEY`, `OPENAI_MODEL`
- `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`
- `GOOGLE_API_KEY`, `GOOGLE_MODEL`
- `*_INPUT_COST_PER_MILLION`, `*_OUTPUT_COST_PER_MILLION`
- `LLM_TIMEOUT_SECONDS`

## Communications

`DELIVERY_ENABLED=false` is the master kill switch. Credentials alone do not authorize sending.

- `EMAIL_WEBHOOK_SECRET`
- `WHATSAPP_WEBHOOK_SECRET`
- `WEBHOOK_TOLERANCE_SECONDS`
- `MESSAGE_MAX_ATTEMPTS`
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM`
- `SMTP_URL`, `SENDGRID_API_KEY`, `AWS_REGION`

## Production storage

Use AWS Secrets Manager or an equivalent vault. Grant secrets only to the ECS task role that needs them, rotate them, and never expose them through `NEXT_PUBLIC_*` variables, logs, audit details, screenshots, or graph state.
