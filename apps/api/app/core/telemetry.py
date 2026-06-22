import logging
import time
from collections.abc import Awaitable, Callable

import structlog
from fastapi import Request, Response

try:
    from prometheus_client import Counter, Histogram
except ImportError:  # local minimal environments; production installs prometheus-client

    class _Metric:
        def labels(self, *_: object):
            return self

        def inc(self) -> None:
            return None

        def observe(self, _: float) -> None:
            return None

    def Counter(*_: object, **__: object):  # noqa: N802
        return _Metric()

    def Histogram(*_: object, **__: object):  # noqa: N802
        return _Metric()


REQUEST_COUNT = Counter(
    "orbitops_http_requests_total", "HTTP requests", ["method", "path", "status"]
)
REQUEST_LATENCY = Histogram(
    "orbitops_http_request_seconds", "HTTP request latency", ["method", "path"]
)
AGENT_RUNS = Counter("orbitops_agent_runs_total", "Agent executions", ["agent", "status"])
LLM_TOKENS = Counter("orbitops_llm_tokens_total", "LLM token usage", ["provider", "direction"])
LLM_COST = Counter("orbitops_llm_cost_usd_total", "Estimated LLM cost", ["provider", "model"])


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ]
    )


async def metrics_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    started = time.perf_counter()
    response = await call_next(request)
    path = request.scope.get("route").path if request.scope.get("route") else request.url.path
    REQUEST_COUNT.labels(request.method, path, response.status_code).inc()
    REQUEST_LATENCY.labels(request.method, path).observe(time.perf_counter() - started)
    response.headers["X-Request-ID"] = getattr(request.state, "request_id", "")
    return response
