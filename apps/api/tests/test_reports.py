import pytest

from app.services.reports import render_executive_pdf


def test_report_requires_approval():
    with pytest.raises(ValueError):
        render_executive_pdf({"title": "Draft", "status": "draft"})


def test_approved_report_is_pdf():
    content = render_executive_pdf(
        {
            "title": "Lead intelligence",
            "status": "approved",
            "executive_summary": "A concise, approved summary.",
            "score": 88,
            "priority": "high",
            "recommended_action": "Book a discovery call",
        }
    )
    assert content.startswith(b"%PDF")
    assert len(content) > 500
