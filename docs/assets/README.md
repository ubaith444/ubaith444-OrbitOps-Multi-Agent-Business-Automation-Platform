# OrbitOps Portfolio Assets

All repository visuals are generated from the implemented application or maintained as editable SVG.

## Screenshots

| File | Screen |
|---|---|
| `screenshots/dashboard.png` | Executive operations dashboard |
| `screenshots/leads.png` | Lead management table |
| `screenshots/workflows.png` | LangGraph workflow tracker |
| `screenshots/approvals.png` | Human approval queue |
| `screenshots/reports.png` | Generated report gallery |
| `screenshots/ai-operations.png` | AI reliability and cost control plane |
| `screenshots/communications.png` | Email and WhatsApp communication center |
| `screenshots/agent-monitor.png` | Per-agent health and execution monitoring |
| `screenshots/mobile-dashboard.png` | 390 × 844 dashboard |
| `screenshots/mobile-leads.png` | Responsive lead cards |
| `screenshots/mobile-navigation.png` | Touch navigation drawer |

## GIF demos

- `demos/product-tour.gif`
- `demos/approval-flow.gif`
- `demos/mobile-experience.gif`

GIFs are intentionally kept below typical GitHub repository size concerns.

## Architecture

- `architecture/system-architecture.svg`
- `architecture/agent-workflow.svg`

SVG source is committed directly so labels and colors remain easy to update without proprietary design software.

## Regeneration

```bash
cd apps/web
pnpm build
PLAYWRIGHT_CHANNEL=chrome pnpm exec playwright test --config portfolio.playwright.config.ts
cd ../..
python scripts/build_portfolio_gifs.py
```

The capture suite uses an in-memory test API, synthetic data, mock model routes, and disabled live delivery.
