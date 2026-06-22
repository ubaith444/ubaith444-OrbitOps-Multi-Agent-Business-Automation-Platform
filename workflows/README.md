# Workflows

OrbitOps has two workflow boundaries:

- LangGraph business orchestration: `apps/api/app/agents/graph.py`
- External connector choreography: `n8n/*.workflow.json`

Business authorization, tenant scope, approval, and canonical state remain in FastAPI/PostgreSQL. n8n may coordinate connectors but cannot override policy.
