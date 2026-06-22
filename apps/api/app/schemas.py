from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, StringConstraints

from app.models import (
    ApprovalKind,
    ApprovalStatus,
    CommunicationChannel,
    LeadPriority,
    MessageDirection,
    MessageStatus,
    ReportStatus,
    Role,
    RunStatus,
)


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


EmailValue = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        max_length=320,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
    ),
]


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    workspace: str = Field(default="default", min_length=1, max_length=80)
    email: EmailValue
    password: str = Field(min_length=8, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=20)


class UserRead(ORMModel):
    id: UUID
    tenant_id: UUID
    email: EmailValue
    full_name: str
    role: Role
    active: bool
    created_at: datetime


class UserCreate(BaseModel):
    email: EmailValue
    full_name: str = Field(min_length=2, max_length=160)
    password: str = Field(min_length=12, max_length=128)
    role: Role = Role.AGENT_VIEWER


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=160)
    role: Role | None = None
    active: bool | None = None


class LeadCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    company: str = Field(min_length=1, max_length=200)
    industry: str | None = Field(default=None, max_length=120)
    website: HttpUrl | None = None
    email: EmailValue | None = None
    phone: str | None = Field(default=None, max_length=40)
    source: str = Field(default="manual", max_length=100)
    attributes: dict[str, Any] = Field(default_factory=dict)


class LeadUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    company: str | None = Field(default=None, min_length=1, max_length=200)
    industry: str | None = Field(default=None, max_length=120)
    website: HttpUrl | None = None
    email: EmailValue | None = None
    phone: str | None = Field(default=None, max_length=40)
    priority: LeadPriority | None = None
    attributes: dict[str, Any] | None = None


class LeadRead(ORMModel):
    id: UUID
    name: str
    company: str
    industry: str | None
    website: str | None
    email: str | None
    phone: str | None
    source: str
    score: int | None
    priority: LeadPriority
    qualification_status: str | None
    recommended_action: str | None
    attributes: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class WorkflowStart(BaseModel):
    lead_id: UUID
    auto_approve_low_risk: bool = False


class WorkflowRead(ORMModel):
    id: UUID
    lead_id: UUID
    status: RunStatus
    current_agent: str | None
    state_snapshot: dict[str, Any]
    error: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class ApprovalRead(ORMModel):
    id: UUID
    run_id: UUID
    kind: ApprovalKind
    status: ApprovalStatus
    payload: dict[str, Any]
    requested_by_agent: str
    decision_note: str | None
    decided_at: datetime | None
    created_at: datetime


class ApprovalDecision(BaseModel):
    approved: bool | None = None
    action: str | None = Field(default=None, pattern="^(approve|reject|request_changes)$")
    note: str | None = Field(default=None, max_length=1000)


class ReportPreview(BaseModel):
    id: UUID
    title: str
    lead_id: UUID
    report: dict[str, Any]
    metadata: dict[str, Any]


class ReportRead(ORMModel):
    id: UUID
    run_id: UUID
    lead_id: UUID
    title: str
    status: ReportStatus
    file_name: str
    size_bytes: int
    error: str | None
    metadata_json: dict[str, Any]
    created_at: datetime


class AuditLogRead(ORMModel):
    id: UUID
    actor_id: UUID | None
    action: str
    resource_type: str
    resource_id: str | None
    ip_address: str | None
    details: dict[str, Any]
    created_at: datetime


class ChartPoint(BaseModel):
    label: str
    value: float


class AgentMetric(BaseModel):
    agent_name: str
    total_runs: int
    successful_runs: int
    failed_runs: int
    success_rate: float
    average_latency_ms: float
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float
    last_failure_reason: str | None = None


class AgentExecutionHistory(BaseModel):
    id: UUID
    run_id: UUID
    user_id: UUID | None
    agent_name: str
    task: str
    provider: str
    model: str
    status: str
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float
    latency_ms: int
    retry_count: int
    error_category: str | None
    error: str | None
    fallback_history: list[dict[str, Any]]
    prompt_version: int | None
    evaluation_score: float | None
    positive_feedback: int
    negative_feedback: int
    created_at: datetime


class CostBreakdown(BaseModel):
    label: str
    input_tokens: int
    output_tokens: int
    cost_usd: float


class CostSummary(BaseModel):
    total_input_tokens: int
    total_output_tokens: int
    daily_spend_usd: float
    monthly_spend_usd: float
    by_agent: list[CostBreakdown]
    by_provider: list[CostBreakdown]
    by_user: list[CostBreakdown]
    daily: list[ChartPoint]


class PromptVersionCreate(BaseModel):
    agent_name: str = Field(min_length=2, max_length=80)
    name: str = Field(min_length=2, max_length=160)
    content: str = Field(min_length=10, max_length=20000)
    activate: bool = False


class PromptVersionRead(ORMModel):
    id: UUID
    agent_name: str
    name: str
    version: int
    content: str
    created_by: UUID
    active: bool
    performance_metrics: dict[str, Any]
    created_at: datetime


class ModelCandidate(BaseModel):
    provider: str = Field(pattern="^(mock|openai|anthropic|google)$")
    model: str = Field(min_length=1, max_length=120)


class ModelRouteUpdate(BaseModel):
    primary: ModelCandidate
    fallbacks: list[ModelCandidate] = Field(default_factory=list, max_length=4)


class ModelRouteRead(ORMModel):
    id: UUID
    agent_name: str
    primary_provider: str
    primary_model: str
    fallback_order: list[dict[str, str]]
    active: bool
    updated_at: datetime


class EvaluationRead(ORMModel):
    id: UUID
    execution_id: UUID
    accuracy: float
    completeness: float
    relevance: float
    hallucination_risk: float
    overall_score: float
    evaluator: str
    rationale: str | None
    created_at: datetime


class FeedbackCreate(BaseModel):
    rating: int = Field(ge=-1, le=1)
    comment: str | None = Field(default=None, max_length=1000)


class FeedbackRead(ORMModel):
    id: UUID
    execution_id: UUID
    user_id: UUID
    rating: int
    comment: str | None
    created_at: datetime


class PlaygroundRequest(BaseModel):
    agent_name: str = Field(min_length=2, max_length=80)
    prompt: str = Field(min_length=3, max_length=20000)
    candidates: list[ModelCandidate] = Field(default_factory=list, max_length=3)


class PlaygroundRunRead(ORMModel):
    id: UUID
    agent_name: str
    prompt: str
    provider: str
    model: str
    output_json: dict[str, Any]
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float
    latency_ms: int
    comparison_group: str | None
    created_at: datetime


class AIOperationsSummary(BaseModel):
    total_executions: int
    success_rate: float
    failure_rate: float
    average_latency_ms: float
    retries: int
    average_evaluation_score: float
    positive_feedback_rate: float
    error_categories: list[ChartPoint]
    agents: list[AgentMetric]
    costs: CostSummary


class CommunicationCreate(BaseModel):
    lead_id: UUID
    channel: CommunicationChannel
    subject: str | None = Field(default=None, max_length=320)
    body: str = Field(min_length=1, max_length=10000)
    provider: str = Field(default="mock", pattern="^(mock|outage|sendgrid|ses|twilio)$")


class CommunicationRead(ORMModel):
    id: UUID
    lead_id: UUID
    run_id: UUID | None
    approval_id: UUID | None
    channel: CommunicationChannel
    direction: MessageDirection
    provider: str
    provider_message_id: str | None
    subject: str | None
    body: str
    status: MessageStatus
    attempt_count: int
    next_retry_at: datetime | None
    last_error: str | None
    classification: dict[str, Any]
    sent_at: datetime | None
    delivered_at: datetime | None
    read_at: datetime | None
    replied_at: datetime | None
    created_at: datetime
    updated_at: datetime


class MessageEventRead(ORMModel):
    id: UUID
    message_id: UUID
    channel: CommunicationChannel
    provider: str
    provider_event_id: str
    status: MessageStatus
    occurred_at: datetime
    metadata_json: dict[str, Any]


class WebhookEvent(BaseModel):
    event_id: str = Field(min_length=1, max_length=200)
    message_id: str = Field(min_length=1, max_length=200)
    status: MessageStatus
    timestamp: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)
    reply_text: str | None = Field(default=None, max_length=10000)


class WebhookResult(BaseModel):
    accepted: bool = True
    duplicate: bool = False
    message_id: UUID
    status: MessageStatus


class TimelineItem(BaseModel):
    id: str
    kind: str
    label: str
    status: str
    timestamp: datetime
    details: dict[str, Any] = Field(default_factory=dict)


class CommunicationAnalytics(BaseModel):
    messages_sent_today: int
    emails_sent: int
    messages_delivered: int
    messages_read: int
    replies_received: int
    response_rate: float
    average_response_minutes: float
    open_rate: float
    click_rate: float
    reply_rate: float
    bounce_rate: float
    funnel: list[ChartPoint]


class DashboardSummary(BaseModel):
    total_leads: int
    qualified_leads: int
    high_priority_leads: int
    active_runs: int
    pending_approvals: int
    reports_generated: int
    failed_workflows: int
    success_rate: float
    total_tokens: int
    monthly_cost_usd: float
    lead_status: list[ChartPoint]
    workflow_outcomes: list[ChartPoint]
    weekly_leads: list[ChartPoint]
    token_usage: list[ChartPoint]
    recent_activity: list[AuditLogRead]
    communication: CommunicationAnalytics


class TenantSettings(BaseModel):
    company_name: str = Field(default="OrbitOps Demo", min_length=2, max_length=160)
    llm_provider: str = Field(default="mock", pattern="^(mock|openai|gemini|claude)$")
    whatsapp_enabled: bool = False
    email_enabled: bool = False
    n8n_webhook_url: str | None = Field(default=None, max_length=500)
    report_brand_name: str = Field(default="OrbitOps", max_length=120)
    api_key_configured: bool = False


class TenantSettingsUpdate(BaseModel):
    company_name: str = Field(min_length=2, max_length=160)
    llm_provider: str = Field(pattern="^(mock|openai|gemini|claude)$")
    whatsapp_enabled: bool = False
    email_enabled: bool = False
    n8n_webhook_url: str | None = Field(default=None, max_length=500)
    report_brand_name: str = Field(default="OrbitOps", max_length=120)
    api_key: str | None = Field(default=None, max_length=500)
