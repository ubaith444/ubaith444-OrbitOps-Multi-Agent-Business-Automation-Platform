import json
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Protocol

import httpx

from app.core.config import settings


@dataclass(slots=True)
class CompletionRequest:
    task: str
    prompt: str
    agent_name: str = "generic"
    complexity: str = "standard"
    requires_json: bool = True
    contains_sensitive_data: bool = False


@dataclass(slots=True)
class CompletionResult:
    content: dict[str, Any]
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0
    latency_ms: int = 0
    fallback_history: list[dict[str, Any]] = field(default_factory=list)


class LLMProvider(Protocol):
    name: str

    async def complete(self, request: CompletionRequest, model: str) -> CompletionResult: ...


def parse_content(text: str) -> dict[str, Any]:
    try:
        value = json.loads(text)
        return value if isinstance(value, dict) else {"result": value}
    except json.JSONDecodeError:
        return {"text": text}


def estimated_cost(provider: str, input_tokens: int, output_tokens: int) -> float:
    input_rate = getattr(settings, f"{provider}_input_cost_per_million", 0)
    output_rate = getattr(settings, f"{provider}_output_cost_per_million", 0)
    return round((input_tokens * input_rate + output_tokens * output_rate) / 1_000_000, 8)


class MockProvider:
    name = "mock"

    async def complete(self, request: CompletionRequest, model: str) -> CompletionResult:
        input_tokens = max(1, len(request.prompt) // 4)
        return CompletionResult(
            content={
                "summary": f"Deterministic result for {request.task}",
                "confidence": 0.86,
                "agent": request.agent_name,
            },
            provider=self.name,
            model=model,
            input_tokens=input_tokens,
            output_tokens=24,
        )


class OpenAIProvider:
    name = "openai"

    async def complete(self, request: CompletionRequest, model: str) -> CompletionResult:
        async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
            response = await client.post(
                "https://api.openai.com/v1/responses",
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                json={"model": model, "input": request.prompt},
            )
            response.raise_for_status()
            data = response.json()
        text = data.get("output_text") or ""
        if not text:
            text = "".join(
                part.get("text", "")
                for item in data.get("output", [])
                for part in item.get("content", [])
                if part.get("type") in {"output_text", "text"}
            )
        usage = data.get("usage", {})
        input_tokens = int(usage.get("input_tokens", 0))
        output_tokens = int(usage.get("output_tokens", 0))
        return CompletionResult(
            content=parse_content(text),
            provider=self.name,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=estimated_cost(self.name, input_tokens, output_tokens),
        )


class AnthropicProvider:
    name = "anthropic"

    async def complete(self, request: CompletionRequest, model: str) -> CompletionResult:
        async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": settings.anthropic_api_key or "",
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": model,
                    "max_tokens": 1024,
                    "messages": [{"role": "user", "content": request.prompt}],
                },
            )
            response.raise_for_status()
            data = response.json()
        text = "".join(item.get("text", "") for item in data.get("content", []))
        usage = data.get("usage", {})
        input_tokens = int(usage.get("input_tokens", 0))
        output_tokens = int(usage.get("output_tokens", 0))
        return CompletionResult(
            content=parse_content(text),
            provider=self.name,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=estimated_cost(self.name, input_tokens, output_tokens),
        )


class GoogleProvider:
    name = "google"

    async def complete(self, request: CompletionRequest, model: str) -> CompletionResult:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
            response = await client.post(
                url,
                params={"key": settings.google_api_key},
                json={"contents": [{"parts": [{"text": request.prompt}]}]},
            )
            response.raise_for_status()
            data = response.json()
        text = "".join(
            part.get("text", "")
            for candidate in data.get("candidates", [])
            for part in candidate.get("content", {}).get("parts", [])
        )
        usage = data.get("usageMetadata", {})
        input_tokens = int(usage.get("promptTokenCount", 0))
        output_tokens = int(usage.get("candidatesTokenCount", 0))
        return CompletionResult(
            content=parse_content(text),
            provider=self.name,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=estimated_cost(self.name, input_tokens, output_tokens),
        )


class ModelRouter:
    DEFAULT_ROUTES = {
        "sales": [
            ("openai", settings.openai_model),
            ("anthropic", settings.anthropic_model),
            ("google", settings.google_model),
            ("mock", "local-deterministic"),
        ],
        "research": [
            ("google", settings.google_model),
            ("openai", settings.openai_model),
            ("anthropic", settings.anthropic_model),
            ("mock", "local-deterministic"),
        ],
        "email": [
            ("openai", settings.openai_model),
            ("anthropic", settings.anthropic_model),
            ("google", settings.google_model),
            ("mock", "local-deterministic"),
        ],
        "report": [
            ("anthropic", settings.anthropic_model),
            ("openai", settings.openai_model),
            ("google", settings.google_model),
            ("mock", "local-deterministic"),
        ],
        "generic": [
            ("openai", settings.openai_model),
            ("anthropic", settings.anthropic_model),
            ("google", settings.google_model),
            ("mock", "local-deterministic"),
        ],
    }

    def __init__(self, providers: dict[str, LLMProvider] | None = None) -> None:
        if providers is not None:
            self.providers = providers
            return
        self.providers: dict[str, LLMProvider] = {"mock": MockProvider()}
        if settings.live_llm_enabled:
            if settings.openai_api_key:
                self.providers["openai"] = OpenAIProvider()
            if settings.anthropic_api_key:
                self.providers["anthropic"] = AnthropicProvider()
            if settings.google_api_key:
                self.providers["google"] = GoogleProvider()

    async def complete(
        self,
        request: CompletionRequest,
        route: list[tuple[str, str]] | None = None,
    ) -> CompletionResult:
        candidates = route or self.DEFAULT_ROUTES.get(
            request.agent_name, self.DEFAULT_ROUTES["generic"]
        )
        history: list[dict[str, Any]] = []
        for provider_name, model in candidates:
            provider = self.providers.get(provider_name)
            started = perf_counter()
            if provider is None:
                history.append(
                    {"provider": provider_name, "model": model, "status": "not_configured"}
                )
                continue
            try:
                result = await provider.complete(request, model)
                latency_ms = round((perf_counter() - started) * 1000)
                history.append(
                    {
                        "provider": provider_name,
                        "model": model,
                        "status": "completed",
                        "latency_ms": latency_ms,
                    }
                )
                result.latency_ms = latency_ms
                result.fallback_history = history
                return result
            except Exception as exc:
                history.append(
                    {
                        "provider": provider_name,
                        "model": model,
                        "status": "failed",
                        "error": type(exc).__name__,
                        "latency_ms": round((perf_counter() - started) * 1000),
                    }
                )
        raise RuntimeError("All model providers failed: " + json.dumps(history))
