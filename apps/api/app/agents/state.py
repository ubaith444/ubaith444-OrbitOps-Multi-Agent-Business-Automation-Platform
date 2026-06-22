from typing import Any, TypedDict


class AutomationState(TypedDict, total=False):
    tenant_id: str
    run_id: str
    lead: dict[str, Any]
    lead_score: int
    qualification_status: str
    priority: str
    recommended_action: str
    company_summary: str
    industry_insights: list[str]
    competitors: list[str]
    risks: list[str]
    email_subject: str
    email_body: str
    follow_up_sequence: list[dict[str, Any]]
    whatsapp_message: str
    report: dict[str, Any]
    pending_approval: dict[str, Any] | None
    approved_actions: list[str]
    events: list[dict[str, Any]]
    errors: list[str]
    phase: str
    resume_node: str | None
    llm_calls: list[dict[str, Any]]
    node_timings: list[dict[str, Any]]
    model_routes: dict[str, list[dict[str, str]]]
    prompt_templates: dict[str, str]
