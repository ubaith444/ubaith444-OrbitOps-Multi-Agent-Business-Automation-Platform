from contextlib import asynccontextmanager
from uuid import uuid4

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

try:
    from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
except ImportError:
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4"

    def generate_latest() -> bytes:
        return b""


from sqlalchemy import select

from app.api.routes import router
from app.core.config import settings
from app.core.database import Base, SessionLocal, engine
from app.core.security import hash_password
from app.core.telemetry import configure_logging, metrics_middleware
from app.models import ModelRoute, PromptVersion, Role, Tenant, User

configure_logging()
log = structlog.get_logger()


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.app_env in {"development", "test"}:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with SessionLocal() as db:
            tenant = await db.scalar(select(Tenant).where(Tenant.slug == "default"))
            if tenant is None:
                tenant = Tenant(name="OrbitOps Demo", slug="default")
                db.add(tenant)
                await db.flush()
            admin = await db.scalar(
                select(User).where(User.email == settings.bootstrap_admin_email)
            )
            if admin is None:
                if not settings.bootstrap_admin_password:
                    raise RuntimeError("BOOTSTRAP_ADMIN_PASSWORD is required for local bootstrap")
                admin = User(
                    tenant_id=tenant.id,
                    email=settings.bootstrap_admin_email,
                    full_name="Platform Administrator",
                    password_hash=hash_password(settings.bootstrap_admin_password),
                    role=Role.ADMIN,
                )
                db.add(admin)
                await db.flush()
            prompt_defaults = {
                "research": "Research the company. Separate verified facts from assumptions.",
                "email": (
                    "Draft concise outreach. Never invent customer facts or send automatically."
                ),
                "report": "Summarize evidence, risks, score, and recommended next action.",
            }
            for agent_name, content in prompt_defaults.items():
                prompt = await db.scalar(
                    select(PromptVersion).where(
                        PromptVersion.tenant_id == tenant.id,
                        PromptVersion.agent_name == agent_name,
                        PromptVersion.active.is_(True),
                    )
                )
                if prompt is None:
                    db.add(
                        PromptVersion(
                            tenant_id=tenant.id,
                            agent_name=agent_name,
                            name=f"{agent_name.title()} default",
                            version=1,
                            content=content,
                            created_by=admin.id,
                            active=True,
                        )
                    )
            route_defaults = {
                "research": ("google", settings.google_model),
                "email": ("openai", settings.openai_model),
                "report": ("anthropic", settings.anthropic_model),
            }
            fallback = [
                {"provider": "openai", "model": settings.openai_model},
                {"provider": "anthropic", "model": settings.anthropic_model},
                {"provider": "google", "model": settings.google_model},
                {"provider": "mock", "model": "local-deterministic"},
            ]
            for agent_name, (provider, model) in route_defaults.items():
                route = await db.scalar(
                    select(ModelRoute).where(
                        ModelRoute.tenant_id == tenant.id,
                        ModelRoute.agent_name == agent_name,
                    )
                )
                if route is None:
                    db.add(
                        ModelRoute(
                            tenant_id=tenant.id,
                            agent_name=agent_name,
                            primary_provider=provider,
                            primary_model=model,
                            fallback_order=[
                                item for item in fallback if item["provider"] != provider
                            ],
                        )
                    )
            await db.commit()
    yield
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0-alpha",
    description="Approval-first multi-agent business automation API",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request.state.request_id = request.headers.get("X-Request-ID", str(uuid4()))
    try:
        return await metrics_middleware(request, call_next)
    except Exception as exc:
        log.exception(
            "unhandled_request_error", request_id=request.state.request_id, error=str(exc)
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "request_id": request.state.request_id},
        )


@app.get("/health/live", tags=["health"])
async def live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready", tags=["health"])
async def ready() -> dict[str, str]:
    async with engine.connect() as connection:
        await connection.execute(select(1))
    return {"status": "ready"}


@app.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


app.include_router(router, prefix="/api/v1")
