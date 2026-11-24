"""Report generation for ClauseGuard."""

from __future__ import annotations

from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from schemas import AnalysisResult, RuleCheck


DISCLAIMER = "General guidance only, not legal advice."
PRIVACY_NOTE = "Your agreement was processed in memory and not saved by this app."


def _safe(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def build_report_pdf(
    *,
    analysis: AnalysisResult,
    rule_checks: list[RuleCheck],
    missing_clauses: list[str],
    score: dict,
    language: str,
) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Small", parent=styles["Normal"], fontSize=9, leading=12, textColor=colors.HexColor("#444444")))
    styles.add(ParagraphStyle(name="Section", parent=styles["Heading3"], spaceBefore=8, spaceAfter=4))

    story = []
    title = "ClauseGuard Report" if language == "English" else "ClauseGuard रिपोर्ट"
    story.append(Paragraph(_safe(title), styles["Title"]))
    story.append(Paragraph(_safe(DISCLAIMER), styles["Small"]))
    story.append(Paragraph(_safe(PRIVACY_NOTE), styles["Small"]))
    story.append(Spacer(1, 4 * mm))

    label = score["label_en"] if language == "English" else score["label_hi"]
    story.append(Paragraph(f"<b>Score:</b> {_safe(str(score['score']))}/10 — {_safe(label)}", styles["Heading2"]))
    story.append(Spacer(1, 2 * mm))

    def section(title_text: str, items: list[str], empty_text: str) -> None:
        story.append(Paragraph(_safe(title_text), styles["Section"]))
        if not items:
            story.append(Paragraph(_safe(empty_text), styles["Normal"]))
            return
        for item in items:
            story.append(Paragraph(f"• {_safe(item)}", styles["Normal"]))

    red = [f"{c.clause_text} — {c.explanation}" for c in analysis.clauses if c.color == "red"]
    yellow = [f"{c.clause_text} — {c.explanation}" for c in analysis.clauses if c.color == "yellow"]
    green = [f"{c.clause_text} — {c.explanation}" for c in analysis.clauses if c.color == "green"]

    if language == "Hindi":
        section("उच्च जोखिम", red, "कोई उच्च जोखिम वाला बिंदु नहीं मिला।")
        section("ध्यान देने योग्य", yellow, "ध्यान देने योग्य कोई बिंदु नहीं मिला।")
        section("स्वीकार्य", green, "कोई स्वीकार्य बिंदु नहीं मिला।")
        section("अनुपलब्ध प्रावधान", missing_clauses, "कोई अनुपलब्ध प्रावधान नहीं मिला।")
    else:
        section("High risk", red, "No high-risk items identified.")
        section("Needs attention", yellow, "No items requiring attention.")
        section("Acceptable", green, "No acceptable items identified.")
        section("Missing provisions", missing_clauses, "No missing provisions identified.")

    story.append(Paragraph(_safe("Checklist" if language == "English" else "जांच सूची"), styles["Section"]))
    table_data = [[
        "Item" if language == "English" else "बिंदु",
        "Status" if language == "English" else "स्थिति",
    ]]
    for r in rule_checks:
        label = r.label_en if language == "English" else r.label_hi
        status = "Present" if r.present else "Missing"
        if language == "Hindi":
            status = "मौजूद" if r.present else "गायब"
        table_data.append([label, status])
    table = Table(table_data, colWidths=[110 * mm, 40 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f2f6")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fbfbfb")]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(table)

    changes_title = "Suggested requests" if language == "English" else "सुझाए गए अनुरोध"
    story.append(Paragraph(_safe(changes_title), styles["Section"]))
    if not analysis.suggested_changes:
        story.append(Paragraph(_safe("No changes suggested." if language == "English" else "कोई बदलाव सुझाव नहीं।"), styles["Normal"]))
    else:
        for s in analysis.suggested_changes:
            story.append(Paragraph(f"<b>{_safe(s.issue)}</b>", styles["Normal"]))
            story.append(Paragraph(_safe(s.polite_request_message), styles["Small"]))
            story.append(Spacer(1, 1.5 * mm))

    doc.build(story)
    return buf.getvalue()
