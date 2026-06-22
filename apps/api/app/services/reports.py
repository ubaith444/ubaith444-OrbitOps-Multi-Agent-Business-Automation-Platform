from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def render_executive_pdf(report: dict[str, Any]) -> bytes:
    """Render an approved report; callers persist bytes in encrypted object storage."""
    if report.get("status") != "approved":
        raise ValueError("Only approved reports can be rendered for publication")
    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=str(report.get("title", "OrbitOps report")),
    )
    styles = getSampleStyleSheet()
    story = [
        Paragraph(str(report.get("title", "Executive report")), styles["Title"]),
        Spacer(1, 8 * mm),
        Paragraph(str(report.get("executive_summary", "")), styles["BodyText"]),
        Spacer(1, 6 * mm),
        Table(
            [
                ["Lead score", str(report.get("score", "—"))],
                ["Priority", str(report.get("priority", "—")).title()],
                ["Recommended action", str(report.get("recommended_action", "—"))],
            ],
            colWidths=[42 * mm, 112 * mm],
            style=TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#E6FFFB")),
                    ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#115E59")),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("PADDING", (0, 0), (-1, -1), 8),
                ]
            ),
        ),
    ]
    document.build(story)
    return output.getvalue()
