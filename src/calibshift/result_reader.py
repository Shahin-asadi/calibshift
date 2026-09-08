"""A sectioned reader for already computed evidence; never fits a model."""

import base64
import io
import json
import zipfile
from html import escape

import matplotlib.pyplot as plt
import pandas as pd

from .presentation import overview_content, select_view
from .reporting import encode_figure, guarded_diagnostics, serialized_render

# Tables and figures remain the original calculated outputs. Sections are a
# reading order, not a ranking, model-selection rule or observation filter.
SECTIONS = {
    "sensefusion": [
        (
            "Model comparison",
            "Compare error and coverage on the recorded cohorts. Lower error is better; fusion can be worse than a single block.",
            ["scores", "paired_baseline_comparison"],
            [],
        ),
        (
            "Prediction and errors",
            "Inspect predictions, group errors and performance across the reference range. These are descriptive diagnostics, not extra validation.",
            ["group_diagnostics", "reference_range_diagnostics"],
            ["diagnostic_prediction_", "diagnostic_group_residuals_", "diagnostic_reference_range_"],
        ),
        (
            "Fusion weights",
            "Inspect training-fold weights, component choices and fallbacks. A large weight is not causal sensor importance.",
            ["fitted_choices"],
            ["diagnostic_fusion_weights"],
        ),
        (
            "Data and validation",
            "Check measurement completeness, exclusions and the actual validation groups before interpreting model performance.",
            ["feature_quality", "input_audit", "splits", "capabilities"],
            ["diagnostic_feature_audit"],
        ),
    ],
    "calibshift": [
        (
            "Transfer comparison",
            "Compare source, corrected and recalibrated predictions at the recorded target-standard budgets and destination conditions.",
            ["scores", "paired_baseline_comparison"],
            [],
        ),
        (
            "Standards and coverage",
            "Inspect which paired standards were used and whether their range covers the target observations. Standards used for correction are excluded from the held-out evaluation.",
            ["standard_range_diagnostics", "standards", "target_availability"],
            ["diagnostic_standard_ranges"],
        ),
        (
            "Prediction and errors",
            "Inspect destination-specific prediction errors, group structure and reference-range effects. Read each diagnostic's cohort and condition labels.",
            ["group_diagnostics", "reference_range_diagnostics"],
            ["diagnostic_prediction_", "diagnostic_group_residuals_", "diagnostic_reference_range_"],
        ),
        (
            "Data and validation",
            "Check paired-input aggregation, measurement completeness and the recorded held-out splits.",
            ["feature_quality", "input_audit", "aggregated_input", "splits", "capabilities"],
            ["diagnostic_feature_audit"],
        ),
    ],
    "matcheddoe": [
        (
            "Model fit and ANOVA",
            "Read the fitted model, ANOVA, coefficients and equation comparisons together. Intervals and tests are conditional on the design and declared independence.",
            ["model_summary", "anova", "coefficients", "equation_comparison", "model_support"],
            ["diagnostic_coefficients"],
        ),
        (
            "Surfaces and candidates",
            "Inspect fitted response surfaces and the selected physical settings. A candidate prediction is not a measured confirmation or a proven global optimum.",
            ["selected_candidates", "factor_coding", "design_check"],
            ["diagnostic_surface_"],
        ),
        (
            "Response tradeoffs",
            "Compare responses evaluated on the same supported grid. Nondominated settings express a tradeoff, not an automatically validated decision.",
            ["candidate_tradeoff"],
            ["diagnostic_tradeoff"],
        ),
        (
            "Run influence",
            "Inspect influential runs and excluded observations without automatically deleting or refitting them.",
            ["influence_diagnostics", "group_diagnostics", "excluded_runs"],
            ["diagnostic_influence"],
        ),
        (
            "Data and support",
            "Check the observed physical settings, input audit and which analysis capabilities the experimental design supports.",
            ["observed_factor_values", "input_audit", "capabilities"],
            [],
        ),
    ],
    "assayreport": [
        (
            "Agreement",
            "Read bias and limits of agreement at the declared unit. Individual repeated readings and specimen means have different estimands; row counts do not establish independence.",
            ["agreement_summary", "agreement_pairs"],
            ["diagnostic_agreement"],
        ),
        (
            "Calibration and accuracy",
            "Review prediction errors and fitted choices, if calibration was performed. Existing measured comparisons remain usable without spectral features.",
            ["scores", "fitted_choices", "feature_correlations"],
            ["diagnostic_prediction_"],
        ),
        (
            "Error patterns",
            "Inspect group errors and reference-range behavior. Descriptive error patterns do not establish interchangeability or a new independent validation.",
            ["group_diagnostics", "reference_range_diagnostics"],
            ["diagnostic_group_residuals_", "diagnostic_reference_range_"],
        ),
        (
            "Data and validation",
            "Check valid pairs, physical specimens, missing measurements and the recorded validation structure.",
            ["feature_quality", "input_audit", "splits", "capabilities"],
            ["diagnostic_feature_audit"],
        ),
    ],
}

SCOPE_NOTE = (
    "The overview uses its recorded primary scoring cohort. Detailed diagnostics show the methods, responses, "
    "conditions and available-pair populations named in their captions and tables; these can differ from the "
    "overview cohort. They describe the same finished run and do not refit models."
)


def sections(result):
    return [
        {"title": title, "intro": intro, "tables": tables, "prefixes": prefixes}
        for title, intro, tables, prefixes in SECTIONS[result.settings["application"]]
    ]


def section_figures(section, figures):
    return [f for f in figures if any(f["stem"].startswith(prefix) for prefix in section["prefixes"])]


def table_description(result, name):
    for item in result.settings.get("diagnostics", []):
        if item.get("table") == name:
            return item.get("question", "") + " " + item.get("interpretation", "")
    return {
        "scores": "Use cohort, method, budget and group-count columns together. Scores from different populations are not a common-cohort comparison.",
        "selected_candidates": "Factor:: fields preserve original physical factor labels. Response identity, direction, support and confirmation status are separate metadata.",
        "agreement_summary": "Valid pairs, physical specimens and agreement units are different counts. Independence is a declaration with recorded support, not inferred from generated row keys.",
        "fitted_choices": "Choices were computed within the training procedure. Displaying this table does not retune a model.",
        "capabilities": "Unavailable capabilities have a reason; small or incomplete inputs can still support other analyses.",
        "splits": "Recorded training/evaluation grouping from the finished run.",
        "input_audit": "Input and exclusion audit. Missing measured references are not filled in.",
    }.get(name, "Calculated table from the finished run; original column labels and units are preserved.")


@serialized_render
def diagnostic_previews(result):
    output = []
    for stem, title, caption, figure in guarded_diagnostics(result):
        try:
            output.append(
                {"stem": stem, "title": title, "caption": caption, "png": encode_figure(figure, ("png",), 140)["png"]}
            )
        finally:
            plt.close(figure)
    return output


def report_tables(result, section):
    return [
        (name, result.tables[name])
        for name in section["tables"]
        if name in result.tables and not result.tables[name].empty
    ]


def table_excerpt(table, rows=30, columns=7):
    """Bound the print view, never the scientific result or downloadable table."""
    preferred = [
        "response",
        "destination",
        "method",
        "model",
        "budget",
        "term",
        "source",
        "group",
        "feature",
        "n",
        "n_groups",
        "group_rmse",
        "rmse",
        "mae",
        "bias",
        "coverage",
        "estimate",
        "coefficient",
        "p_value",
        "predicted_response",
        "direction",
        "n_valid_pairs",
        "n_physical_specimens",
        "n_agreement_units",
        "estimand",
    ]
    chosen = [c for c in preferred if c in table]
    chosen += [c for c in table if c not in chosen]
    chosen = chosen[:columns]
    frame = table.loc[:, chosen].head(rows).copy()
    note = f"Showing {len(frame)} of {len(table)} rows and {len(chosen)} of {len(table.columns)} columns, in original row order."
    if len(frame) < len(table) or len(chosen) < len(table.columns):
        note += " The web table and its CSV contain every row and column. Printed text longer than 180 characters is shortened with an ellipsis."
    return frame, note


def cell(value):
    if isinstance(value, float):
        return "Unavailable" if pd.isna(value) else f"{value:.5g}"
    text = str(value)
    return "Unavailable" if text in {"nan", "None", "<NA>"} else text


def detailed_html(result, selection, figures, preview):
    view = select_view(result, **selection)
    content = overview_content(result, view)
    pages = sections(result)
    parts = [
        "<!doctype html><html lang='en'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>",
        "<title>Analysis report</title><style>body{font:16px/1.65 Georgia,serif;color:#192731;max-width:1100px;margin:30px auto;padding:0 22px}h1{font-size:28px}h2{font-size:23px;border-bottom:2px solid #263c4c;padding-bottom:8px}h3{font-size:18px}nav{display:flex;flex-wrap:wrap;gap:12px;border-bottom:1px solid #bbb;padding:15px 0}a{color:#175180}figure{margin:24px 0;break-inside:avoid}img{max-width:100%;height:auto}figcaption,.note{font-size:14px;color:#44535d}.table-wrap{overflow:auto}table{border-collapse:collapse;width:100%;font-size:14px}th,td{padding:7px;text-align:left;vertical-align:top;overflow-wrap:anywhere;max-width:240px}thead{border-top:1px solid black;border-bottom:1px solid black}tbody{border-bottom:1px solid black}section{margin-top:35px}@media print{body{font-size:10pt;line-height:1.5;margin:0}h2{font-size:12pt}nav{display:none}section{break-before:page}.table-wrap{overflow:visible}thead{display:table-header-group}tr{break-inside:avoid}table{font-size:8pt}}</style>",
        f"<h1>{escape(result.settings['application'])} - analysis report</h1><p>{escape(content['statement'])}</p><p>{escape(content['caveat'])}</p><p class='note'>{escape(SCOPE_NOTE)}</p>",
        "<nav><a href='#overview'>Overview</a>"
        + "".join(f"<a href='#section-{i}'>{escape(s['title'])}</a>" for i, s in enumerate(pages))
        + "</nav><div id='overview'>",
    ]
    for item in json.loads(preview["primary_catalog.json"]):
        data = base64.b64encode(preview[item["stem"] + ".png"]).decode()
        parts.append(
            f"<figure><img alt='{escape(item['title'], quote=True)}' src='data:image/png;base64,{data}'><figcaption>{escape(item['caption'])}</figcaption></figure>"
        )
    parts.append("</div>")
    for i, section in enumerate(pages):
        parts.append(f"<section id='section-{i}'><h2>{escape(section['title'])}</h2><p>{escape(section['intro'])}</p>")
        for figure in section_figures(section, figures):
            data = base64.b64encode(figure["png"]).decode()
            parts.append(
                f"<figure><h3>{escape(figure['title'])}</h3><img alt='{escape(figure['title'], quote=True)}' src='data:image/png;base64,{data}'><figcaption>{escape(figure['caption'])}</figcaption></figure>"
            )
        tables = report_tables(result, section)
        for name, table in tables:
            shown, note = table_excerpt(table, rows=80, columns=12)
            parts.append(
                f"<h3>{escape(name.replace('_', ' ').capitalize())}</h3><p>{escape(table_description(result, name))}</p><p class='note'>{escape(note)}</p><div class='table-wrap'>{shown.to_html(index=False, escape=True, border=0, float_format=lambda x: f'{x:.5g}')}</div>"
            )
        if not tables and not section_figures(section, figures):
            parts.append(
                "<p>This analysis is not available for the supplied input and configuration. See the data/support section and limitations below.</p>"
            )
        parts.append("</section>")
    parts.append(
        "<section><h2>Interpretation and limitations</h2>"
        + "".join(f"<p>{escape(str(note))}</p>" for note in result.notes)
        + "</section></html>"
    )
    return "".join(parts).encode("utf-8")


@serialized_render
def detailed_pdf(result, selection, figures, preview):
    from matplotlib import font_manager
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import (
        Image,
        KeepTogether,
        LongTable,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        TableStyle,
    )

    for alias, weight in [("ReaderSerif", "normal"), ("ReaderSerifBold", "bold")]:
        if alias not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(
                TTFont(alias, font_manager.findfont(font_manager.FontProperties(family="DejaVu Serif", weight=weight)))
            )
    body = ParagraphStyle("body", fontName="ReaderSerif", fontSize=10, leading=15, spaceAfter=8)
    heading = ParagraphStyle(
        "heading", parent=body, fontName="ReaderSerifBold", fontSize=12, leading=17, spaceAfter=10, keepWithNext=True
    )
    small = ParagraphStyle("small", parent=body, fontSize=8, leading=11, spaceAfter=5)
    memory = io.BytesIO()
    doc = SimpleDocTemplate(
        memory,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=34,
        bottomMargin=38,
        title="Detailed analysis report",
    )
    story = []

    def para(text, style=body):
        return Paragraph(escape(str(text)), style)

    def figure_block(title, caption, data):
        figure = Image(io.BytesIO(data))
        scale = min(doc.width / figure.imageWidth, 500 / figure.imageHeight)
        figure.drawWidth = figure.imageWidth * scale
        figure.drawHeight = figure.imageHeight * scale
        story.append(KeepTogether([para(title, heading), figure, Spacer(1, 5), para(caption, small)]))

    view = select_view(result, **selection)
    content = overview_content(result, view)
    story.extend(
        [
            para(result.settings["application"] + " - analysis report", heading),
            para(content["statement"]),
            para(content["caveat"]),
            para(SCOPE_NOTE, small),
        ]
    )
    for item in json.loads(preview["primary_catalog.json"]):
        figure_block(item["title"], item["caption"], preview[item["stem"] + ".png"])
    for section in sections(result):
        story.extend([Spacer(1, 16), para(section["title"], heading), para(section["intro"])])
        selected = section_figures(section, figures)
        for item in selected:
            figure_block(item["title"], item["caption"], item["png"])
        tables = report_tables(result, section)
        for name, table in tables:
            shown, note = table_excerpt(table)
            story.extend(
                [
                    para(name.replace("_", " ").capitalize(), heading),
                    para(table_description(result, name), small),
                    para(note, small),
                ]
            )
            data = [[para(str(c).replace("_", " "), small) for c in shown.columns]]
            data += [
                [para(cell(v)[:180] + (" …" if len(cell(v)) > 180 else ""), small) for v in row]
                for row in shown.itertuples(index=False, name=None)
            ]
            tab = LongTable(
                data,
                colWidths=[doc.width / max(1, len(shown.columns))] * len(shown.columns),
                repeatRows=1,
                hAlign="LEFT",
            )
            tab.setStyle(
                TableStyle(
                    [
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LINEABOVE", (0, 0), (-1, 0), 0.8, colors.black),
                        ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.black),
                        ("LINEBELOW", (0, -1), (-1, -1), 0.8, colors.black),
                        ("LEFTPADDING", (0, 0), (-1, -1), 4),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ]
                )
            )
            story.extend([tab, Spacer(1, 12)])
        if not selected and not tables:
            story.append(
                para("Not available for this input/configuration. Refer to the capability table and limitations.")
            )
    story.extend([Spacer(1, 16), para("Interpretation and limitations", heading)])
    story.extend(para(note) for note in result.notes)

    def footer(canvas, document):
        canvas.setFont("ReaderSerif", 8)
        canvas.drawString(36, 20, result.settings["application"] + " | Finished-run diagnostic report")
        canvas.drawRightString(A4[0] - 36, 20, str(document.page))

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return memory.getvalue()


def key_bundle(result, selection, figures, preview):
    """A small labelled reading package, separate from the complete archive."""
    files = {
        "01_REPORTS/analysis_report.html": detailed_html(result, selection, figures, preview),
        "01_REPORTS/analysis_report.pdf": detailed_pdf(result, selection, figures, preview),
    }
    for section in sections(result):
        for name, table in report_tables(result, section):
            files["02_TABLES/" + name + ".csv"] = table.to_csv(index=False).encode("utf-8-sig")
        for item in section_figures(section, figures):
            files["03_FIGURES/" + item["stem"] + ".png"] = item["png"]
    for name in ["summary_cohort.csv", "summary_view.json"]:
        files["04_RUN_DETAILS/" + name] = preview[name]
    for item in json.loads(preview["primary_catalog.json"]):
        files["03_FIGURES/" + item["stem"] + ".png"] = preview[item["stem"] + ".png"]
    files["START_HERE.txt"] = (
        b"Start with 01_REPORTS/analysis_report.html (offline browser) or analysis_report.pdf (print).\n"
        b"02_TABLES contains full rows/columns for the report tables; print excerpts are labelled.\n"
        b"03_FIGURES contains the primary and section diagnostic figures.\n"
        b"04_RUN_DETAILS identifies the primary view and scoring cohort.\n"
        b"This is a reading package, not the complete reproduction archive. Use the advanced full archive for all predictions and configuration.\n"
    )
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return stream.getvalue()


def archive_index(files):
    links = "".join(
        f"<li><a href='{escape(name, quote=True)}'>{escape(name)}</a></li>"
        for name in sorted(files)
        if name.endswith((".html", ".pdf", ".csv", ".json", ".xlsx"))
    )
    return (
        "<!doctype html><html lang='en'><meta charset='utf-8'><title>Archive guide</title><h1>Complete reproducibility archive</h1><p>Start with analysis_report.html for the sectioned report or report.html for the concise overview. CSV/XLSX are calculated tables; JSON files record configuration, provenance and cohort membership. Diagnostic figures are descriptive. This archive includes all outputs, not just key results.</p><ul>"
        + links
        + "</ul></html>"
    ).encode()
