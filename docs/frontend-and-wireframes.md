# Frontend plan and wireframes

The console uses Next.js App Router, strict TypeScript, Tailwind CSS, and small shadcn-style Radix primitives. Server components render initial data; client components own filters, optimistic decisions, and live workflow events. Authentication should use an encrypted, HTTP-only, SameSite cookie via a backend-for-frontend route rather than browser local storage.

```text
App shell
├── Sidebar (workspace, role-aware navigation, health)
├── Header (search, notifications, identity)
└── Route content
    ├── Dashboard → KPI cards, live activity, pipeline, approval callout
    ├── Leads → filters, lead table, detail drawer, run action
    ├── Agent monitoring → run table, event timeline, cost/latency traces
    ├── Approvals → immutable payload preview, rationale, approve/reject
    ├── Reports → report list, generation form, preview/publish
    ├── Users → invitations, role editor, session revocation
    └── Settings → model, integration, memory, delivery policies
```

Desktop wireframe:

```text
┌───────────────┬────────────────────────────────────────────────────┐
│ OrbitOps      │ OPERATIONS CENTER                    Search  User  │
│ Overview      │ Good morning, Asha                                 │
│ Leads         ├──────────┬──────────┬──────────┬──────────┤         │
│ Agent runs    │ Leads    │ Success  │ Reviews  │ Pipeline │         │
│ Approvals (4) ├───────────────────────────────┬────────────┤         │
│ Reports       │ Live agent activity           │ Pulse      │         │
│ Users         │ company · agent · state       │ chart      │         │
│ Settings      ├───────────────────────────────┴────────────┤         │
│               │ Approval callout · system health           │         │
└───────────────┴────────────────────────────────────────────────────┘
```

Accessibility: visible keyboard focus, semantic tables and headings, labelled controls, non-color status labels, live-region updates for decisions, reduced-motion support, and WCAG AA contrast. Test at 360, 768, 1280, and 1536 px.

