# Agents

Production agent implementation lives in `apps/api/app/agents` so it ships with the FastAPI package.

| Module | Responsibility |
|---|---|
| `graph.py` | LangGraph topology, guarded nodes, routing, retry entry |
| `nodes.py` | Sales, research, email, approval, and report nodes |
| `state.py` | Typed durable workflow state |
| `llm_router.py` | Provider adapters, fallback, tokens, latency, and cost |
| `communication.py` | Deterministic reply classification |

See [docs/architecture/langgraph.md](../docs/architecture/langgraph.md).
