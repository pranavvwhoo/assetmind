"""In-memory PDF generation for the analysis result."""

from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle, KeepTogether,
)


def _safe(value: object) -> str:
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def generate_pdf(analysis: dict[str, Any], evaluation: dict[str, Any] | None = None) -> bytes:
    output = BytesIO()
    doc = SimpleDocTemplate(
        output, pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm,
        topMargin=17 * mm, bottomMargin=17 * mm, title="IT Asset Report",
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="ReportTitle", parent=styles["Title"], alignment=TA_CENTER, spaceAfter=12))
    styles.add(ParagraphStyle(name="SmallCell", parent=styles["BodyText"], fontSize=8, leading=10))
    story = [
        Paragraph("IT Asset Management Report", styles["ReportTitle"]),
        Paragraph(f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}", styles["Normal"]),
        Spacer(1, 8),
    ]
    report = analysis.get("report") or {}
    metrics = analysis.get("analytics", {})
    story.extend([Paragraph("Executive summary", styles["Heading1"]),
                  Paragraph(_safe(report.get("executive_summary", "AI report was not generated.")), styles["BodyText"]),
                  Spacer(1, 8)])
    story.append(Paragraph("Dataset overview", styles["Heading1"]))
    overview_rows = [
        ["Metric", "Verified value"],
        ["Source", _safe(analysis.get("source_name", "Unknown"))],
        ["Total assets", str(metrics.get("total_assets", 0))],
        ["Allocated / unallocated / unknown", f"{metrics.get('allocated_assets', 0)} / {metrics.get('unallocated_assets', 0)} / {metrics.get('allocation_unknown_assets', 0)}"],
        ["Retired / active / unknown", f"{metrics.get('retired_assets', 0)} / {metrics.get('active_assets', 0)} / {metrics.get('retirement_unknown_assets', 0)}"],
        ["Rows with missing information", str(metrics.get("assets_with_missing_information", 0))],
        ["Data-quality score", f"{metrics.get('data_quality_score', 0)}%"],
        ["Duplicate ID values", str(metrics.get("duplicate_identifier_values", 0))],
    ]
    story.append(_table(overview_rows))
    for title, key in (("Asset categories", "by_category"), ("Departments", "by_department"), ("Statuses", "by_status")):
        values = metrics.get(key) or {}
        if values:
            story.extend([Paragraph(title, styles["Heading2"]), _table([["Group", "Assets"]] + [
                [_safe(name), str(count)] for name, count in sorted(values.items())
            ])])
    radar = metrics.get("attention_radar", {})
    story.append(Paragraph("Asset Attention Radar", styles["Heading1"]))
    story.append(Paragraph(
        f"{radar.get('assets_requiring_review', 0)} record(s) crossed the review threshold of "
        f"{radar.get('review_threshold', 20)} points as of {_safe(radar.get('as_of_date', 'unknown'))}. "
        "This is a transparent review-priority score, not a prediction of financial, security, or failure risk.",
        styles["BodyText"],
    ))
    if radar.get("signal_counts"):
        story.extend([
            Spacer(1, 5),
            _table([["Attention signal", "Records"]] + [
                [_safe(name.replace("_", " ").title()), str(count)]
                for name, count in radar["signal_counts"].items()
            ]),
        ])
    if radar.get("review_queue"):
        story.extend([
            Paragraph("Highest-priority records", styles["Heading2"]),
            _table(
                [["Source row", "Asset ID", "Score", "Priority", "Evidence", "Suggested next step"]]
                + [
                    [
                        str(item["source_row"]), _safe(item["asset_id"]), str(item["score"]),
                        _safe(item["priority"]), _safe("; ".join(item["evidence"])),
                        _safe(item["next_action"]),
                    ]
                    for item in radar["review_queue"]
                ],
                widths=[15 * mm, 22 * mm, 12 * mm, 18 * mm, 45 * mm, 58 * mm],
            ),
        ])
    story.append(Paragraph("Scoring method", styles["Heading2"]))
    story.append(Paragraph(_safe(radar.get("method", "No attention score available.")), styles["BodyText"]))
    story.append(Paragraph(
        "Warranty dates are evaluated relative to the report date; unknown or unparsable dates are not assumed expired. "
        "Records below the review threshold are not included in the review queue.",
        styles["BodyText"],
    ))
    story.append(Paragraph("Data-quality findings", styles["Heading1"]))
    validation_issues = metrics.get("validation_issues", []) + metrics.get("column_issues", [])
    if validation_issues:
        for issue in validation_issues:
            story.append(Paragraph(f"• {_safe(issue)}", styles["BodyText"]))
    else:
        story.append(Paragraph("No required-field or column-mapping issues were detected.", styles["BodyText"]))
    missing_values = {
        name: count for name, count in metrics.get("missing_values_by_column", {}).items() if count
    }
    if missing_values:
        story.extend([
            Paragraph("Missing values by column", styles["Heading2"]),
            _table([["Column", "Missing values"]] + [
                [_safe(name), str(count)] for name, count in sorted(missing_values.items())
            ]),
        ])
    quality = analysis.get("quality_analysis") or {}
    findings = quality.get("findings", [])
    if findings:
        for finding in findings:
            story.append(Paragraph(
                f"<b>{_safe(finding.get('severity', 'info').upper())}: {_safe(finding.get('title', 'Finding'))}</b><br/>"
                f"{_safe(finding.get('detail', ''))}", styles["BodyText"]))
            story.append(Spacer(1, 4))
    else:
        story.append(Paragraph("No agent findings are available.", styles["BodyText"]))

    story.append(Paragraph("Important observations", styles["Heading1"]))
    interpretation = analysis.get("analytics_interpretation") or {}
    observations = interpretation.get("observations", [])
    if observations:
        for observation in observations:
            story.append(Paragraph(
                f"<b>{_safe(observation.get('title', 'Observation'))}</b>: "
                f"{_safe(observation.get('detail', ''))}", styles["BodyText"]))
            story.append(Spacer(1, 4))
    for hypothesis in interpretation.get("hypotheses_to_investigate", []):
        story.append(Paragraph(f"Hypothesis to investigate: {_safe(hypothesis)}", styles["BodyText"]))

    story.append(Paragraph("Prioritized recommendations", styles["Heading1"]))
    recommendations = report.get("recommendations", [])
    if recommendations:
        story.append(_table([["Priority", "Action", "Rationale"]] + [
            [_safe(item.get("priority", "")), _safe(item.get("action", "")), _safe(item.get("rationale", ""))]
            for item in recommendations
        ], widths=[25 * mm, 70 * mm, 75 * mm]))
    else:
        story.append(Paragraph("No AI recommendations are available.", styles["BodyText"]))

    review = analysis.get("quality_review") or {}
    story.extend([Paragraph("Quality review", styles["Heading1"]),
                  Paragraph(f"Reviewer status: {'PASSED' if review.get('passed') else 'FAILED / UNAVAILABLE'}",
                            styles["BodyText"])])
    for issue in review.get("issues", []) + review.get("unsupported_claims", []):
        story.append(Paragraph(f"• {_safe(issue)}", styles["BodyText"]))
    if evaluation:
        story.extend([Paragraph("Evaluation", styles["Heading1"]),
                      Paragraph(_safe(evaluation.get("summary", "Evaluation results")), styles["BodyText"])])
    story.extend([Paragraph("Methodology and limitations", styles["Heading1"]),
                  Paragraph(_safe(metrics.get("allocation_definition", "")), styles["BodyText"]),
                  Paragraph(_safe(metrics.get("retirement_definition", "")), styles["BodyText"])])
    for item in metrics.get("limitations", []):
        story.append(Paragraph(f"• {_safe(item)}", styles["BodyText"]))
    story.extend([Spacer(1, 8), Paragraph(
        "AI interpretations are advisory. Numeric totals and group counts in this report are calculated "
        "deterministically from the uploaded dataset. Unknown states are not inferred.", styles["Italic"])])
    doc.build(story)
    return output.getvalue()


def _table(rows: list[list[str]], widths: list[float] | None = None) -> Table:
    wrapped = [[Paragraph(str(cell), getSampleStyleSheet()["BodyText"]) for cell in row] for row in rows]
    table = Table(wrapped, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#19324d")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f6fa")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return table
