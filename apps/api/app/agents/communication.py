from typing import Any


def classify_reply(text: str, current_score: int | None) -> dict[str, Any]:
    """Deterministic safety-first classifier; replaceable by a validated LLM adapter."""
    normalized = text.casefold()
    if any(term in normalized for term in ("meeting", "demo", "schedule", "calendar")):
        intent, confidence, action, delta = "Meeting Requested", 0.96, "Schedule Demo", 18
    elif any(term in normalized for term in ("interested", "sounds good", "yes")):
        intent, confidence, action, delta = "Interested", 0.93, "Send scheduling link", 12
    elif any(term in normalized for term in ("more information", "more info", "question")):
        intent, confidence, action, delta = "Need More Information", 0.89, "Prepare answers", 6
    elif any(term in normalized for term in ("out of office", "on leave", "away until")):
        intent, confidence, action, delta = "Out of Office", 0.97, "Pause until return date", 0
    elif any(
        term in normalized for term in ("not interested", "unsubscribe", "remove me", "no thanks")
    ):
        intent, confidence, action, delta = "Not Interested", 0.97, "Stop outreach", -25
    elif "spam" in normalized:
        intent, confidence, action, delta = "Spam", 0.99, "Suppress contact", -35
    else:
        intent, confidence, action, delta = "Need More Information", 0.65, "Human review", 3
    return {
        "intent": intent,
        "confidence": confidence,
        "next_action": action,
        "lead_score": max(0, min(100, (current_score or 50) + delta)),
    }
