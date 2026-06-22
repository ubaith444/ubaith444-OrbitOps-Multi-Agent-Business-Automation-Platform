import json
from typing import Any

from app.core.config import settings


async def cache_workflow_state(
    tenant_id: str, run_id: str, state: dict[str, Any], ttl_seconds: int = 3600
) -> None:
    """Cache active graph state; PostgreSQL remains the durable source of truth."""
    try:
        from redis.asyncio import from_url

        client = from_url(settings.redis_url, decode_responses=True)
        await client.set(
            f"orbitops:{tenant_id}:workflow:{run_id}",
            json.dumps(state, default=str),
            ex=ttl_seconds,
        )
        await client.aclose()
    except Exception:
        # Redis loss must not corrupt or block the PostgreSQL-backed workflow.
        return
