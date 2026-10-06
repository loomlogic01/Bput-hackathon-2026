"""
PDF report generation for the BRSR ESG Consolidation view.

Accepts a ConsolidationResponse schema object (already assembled by
build_consolidation) and returns raw PDF bytes that can be streamed
directly from the FastAPI endpoint.

Only ReportLab platypus (bundled with reportlab) is used — no new
external dependencies beyond the reportlab package added to
requirements.txt.
"""

import io
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.app.api.v1.schemas import ConsolidationResponse

# ── Colour palette (SEBI / ESG greens) ──────────────────────────────────────
_GREEN = colors.HexColor("#2e7d32")
_LIGHT_GREEN = colors.HexColor("#e8f5e9")
_AMBER = colors.HexColor("#f9a825")
_GREY_HEAD = colors.HexColor("#37474f")
_RULE = colors.HexColor("#b0bec5")


def _build_styles():
    """Return a dict of named ParagraphStyle objects."""
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "rpt_title",
            parent=base["Title"],
            fontSize=20,
            textColor=_GREEN,
            spaceAfter=4,
        ),
        "subtitle": ParagraphStyle(
            "rpt_subtitle",
            parent=base["Normal"],
            fontSize=10,
            textColor=_GREY_HEAD,
            spaceAfter=2,
        ),
        "section": ParagraphStyle(
            "rpt_section",
            parent=base["Heading2"],
            fontSize=12,
            textColor=_GREEN,
            spaceBefore=12,
            spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "rpt_body",
            parent=base["Normal"],
            fontSize=9,
            spaceAfter=2,
        ),
        "kpi_value": ParagraphStyle(
            "rpt_kpi_value",
            parent=base["Normal"],
            fontSize=32,
            textColor=_GREEN,
            spaceAfter=2,
        ),
        "kpi_label": ParagraphStyle(
            "rpt_kpi_label",
            parent=base["Normal"],
            fontSize=10,
            textColor=_GREY_HEAD,
            spaceAfter=4,
        ),
        "footer": ParagraphStyle(
            "rpt_footer",
            parent=base["Normal"],
            fontSize=7,
            textColor=colors.grey,
            alignment=1,  # centre
        ),
        "warn": ParagraphStyle(
            "rpt_warn",
            parent=base["Normal"],
            fontSize=8,
            textColor=_AMBER,
        ),
    }


def _table_style(header_bg=_GREEN, stripe_bg=_LIGHT_GREEN) -> TableStyle:
    return TableStyle(
        [
            # Header row
            ("BACKGROUND", (0, 0), (-1, 0), header_bg),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 8),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
            ("TOPPADDING", (0, 0), (-1, 0), 6),
            # Body rows
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 1), (-1, -1), 8),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, stripe_bg]),
            ("TOPPADDING", (0, 1), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
            # Grid
            ("GRID", (0, 0), (-1, -1), 0.25, _RULE),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]
    )


def generate_consolidation_pdf(data: ConsolidationResponse) -> bytes:
    """Build and return a PDF byte string for *data*.

    The returned bytes can be passed directly to a ``StreamingResponse``
    or written to disk.  No database access is performed here.
    """
    buf = io.BytesIO()
    page_w, page_h = A4
    margin = 18 * mm

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=margin,
        bottomMargin=20 * mm,
        title="BRSR Consolidated ESG Report",
        author="ESG Reporting Portal",
    )

    styles = _build_styles()
    story = []

    # ── Title ──────────────────────────────────────────────────────────────
    story.append(Paragraph("BRSR Consolidated ESG Report", styles["title"]))

    period = data.reporting_period
    fw = data.framework

    desc = getattr(period, "description", None)
    story.append(
        Paragraph(
            f"Reporting Period: <b>{period.fiscal_year}</b>"
            + (f" &mdash; {desc}" if desc else ""),
            styles["subtitle"],
        )
    )
    story.append(
        Paragraph(
            f"Framework: <b>{fw.name}</b>"
            + (f" v{fw.version}" if fw.version else ""),
            styles["subtitle"],
        )
    )
    story.append(
        Paragraph(
            f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
            styles["subtitle"],
        )
    )
    story.append(Spacer(1, 6 * mm))

    # ── Summary line ────────────────────────────────────────────────────────
    totals = data.totals
    story.append(
        Paragraph(
            f"<b>{totals.projects_contributing}</b> projects contributing &bull; "
            f"<b>{totals.metrics_aggregated}</b> metrics aggregated",
            styles["body"],
        )
    )
    story.append(Spacer(1, 4 * mm))

    # ── Derived KPI hero ────────────────────────────────────────────────────
    if data.derived_kpis:
        story.append(Paragraph("Derived KPI", styles["section"]))
        for kpi in data.derived_kpis:
            if kpi.value is not None:
                story.append(
                    Paragraph(
                        f"{kpi.value:.2f}&nbsp;{kpi.unit or ''}",
                        styles["kpi_value"],
                    )
                )
            else:
                story.append(Paragraph("Value not available", styles["warn"]))
            story.append(Paragraph(kpi.label, styles["kpi_label"]))
            story.append(
                Paragraph(
                    f"Method: <b>{kpi.calculation_method}</b> &bull; "
                    f"Contributing projects: <b>{kpi.contributing_project_count}</b> &bull; "
                    f"Sources: <b>{', '.join(kpi.source_question_codes)}</b>",
                    styles["body"],
                )
            )
            story.append(Spacer(1, 4 * mm))

    # ── Consolidated metrics table ──────────────────────────────────────────
    story.append(Paragraph("Consolidated Metrics", styles["section"]))
    if not data.metrics:
        story.append(Paragraph("No metrics available.", styles["body"]))
    else:
        col_w = (page_w - 2 * margin) / 6
        headers = [
            "Question Code",
            "Question",
            "Aggregated Value",
            "Unit",
            "Projects",
            "Aggregation",
        ]
        rows = [headers]
        for m in data.metrics:
            val_str = f"{m.aggregated_value:.2f}"
            if not m.aggregated_value_is_meaningful:
                val_str += " *"
            rows.append(
                [
                    m.question_code,
                    Paragraph(m.question, styles["body"]),
                    val_str,
                    m.unit_of_measurement or "—",
                    str(m.contributing_project_count),
                    m.aggregation,
                ]
            )

        tbl = Table(
            rows,
            colWidths=[col_w * 1.3, col_w * 1.7, col_w * 0.9, col_w * 0.7, col_w * 0.7, col_w * 0.7],
            repeatRows=1,
        )
        tbl.setStyle(_table_style())
        story.append(tbl)

        # Note about non-meaningful values
        if any(not m.aggregated_value_is_meaningful for m in data.metrics):
            story.append(Spacer(1, 2 * mm))
            story.append(
                Paragraph(
                    "* Raw sum — not a meaningful consolidated KPI "
                    "(use the derived KPI above for renewable energy).",
                    styles["warn"],
                )
            )

    story.append(Spacer(1, 5 * mm))

    # ── Contributing projects table ─────────────────────────────────────────
    story.append(Paragraph("Contributing Projects", styles["section"]))
    if not data.projects:
        story.append(Paragraph("No contributing projects.", styles["body"]))
    else:
        col_w = (page_w - 2 * margin) / 3
        proj_headers = ["Project Code", "Project Name", "Submission Status"]
        proj_rows = [proj_headers]
        for p in data.projects:
            code = getattr(p, "project_code", None) or "—"
            name = getattr(p, "project_name", None) or getattr(p, "name", None) or "—"
            status = getattr(p, "submission_status", None) or "—"
            if status != "—":
                status = status.replace("_", " ")
            proj_rows.append([code, name, status])

        proj_tbl = Table(proj_rows, colWidths=[col_w, col_w, col_w], repeatRows=1)
        proj_tbl.setStyle(_table_style())
        story.append(proj_tbl)

    story.append(Spacer(1, 8 * mm))

    # ── Footer ──────────────────────────────────────────────────────────────
    story.append(
        Paragraph(
            "Generated by ESG Reporting Portal &bull; BRSR / SEBI",
            styles["footer"],
        )
    )

    doc.build(story)
    return buf.getvalue()

