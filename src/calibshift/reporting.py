"""Portable reports and table archives generated from one computed result."""

import io
import threading
import zipfile
from datetime import UTC, datetime
from functools import wraps
from html import escape
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .common import InputError, environment, json_text


def method_label(key):
    mapping = {
        "early_pls": "Early fusion (PLS)",
        "late_equal": "Late fusion (equal weights)",
        "late_weighted": "Late fusion (trained weights)",
        "late_inverse_rmse": "Late fusion (inverse RMSE)",
        "training_mean": "Training mean",
        "source_pls": "Source calibration",
        "source_mean": "Source mean",
        "bias_correction": "Bias correction",
        "slope_intercept": "Slope/intercept correction",
        "target_recalibration": "Target spectral recalibration",
    }
    return mapping.get(str(key), str(key).replace("single_", "Single block: "))


def response_label(result, column=None):
    column = column or result.settings.get("target", "response")
    meta = result.settings.get("columns", {}).get(column, {})
    return f"{meta.get('label', column)} ({meta.get('unit', 'unit not supplied')})"


def result_summary(result):
    """Readable numerical statements derived directly from the exported result tables."""
    settings = result.settings
    output = [
        f"Input: {settings.get('input_name', 'in-memory table')}; {settings.get('n_input_rows', settings.get('n_rows', 'unknown'))} rows. Computation completed; evidence availability: {result.status.replace('_', ' ')}."
    ]
    scores = result.tables.get("scores", pd.DataFrame())
    if result.title.startswith("MatchedDoE"):
        summary = result.tables.get("model_summary", pd.DataFrame())
        for _, row in summary.iterrows():
            r2 = f"{row.r2_fitted:.4g}" if pd.notna(row.r2_fitted) else "unavailable (constant response)"
            output.append(
                f"{response_label(result, row.response)}: {int(row.n)} matched runs; fitted R² = {r2}; residual sum of squares = {row.residual_ss:.6g}. These are in-sample fits, not independent confirmation experiments."
            )
        equation = result.tables.get("equation_comparison", pd.DataFrame())
        if not equation.empty:
            output.append(
                f"Reported-equation check: {int(equation.status.eq('discrepancy').sum())} of {len(equation)} comparisons exceed the declared numeric and coefficient-rounding tolerances. The comparisons describe arithmetic, not measured confirmation."
            )
    elif result.title.startswith("AssayReport") and not scores.empty:
        row = scores.iloc[0]
        value = f"{row.rmse:.6g}" if pd.notna(row.rmse) else "unavailable"
        output.append(
            f"Target: {response_label(result)}. {int(row.n)} paired rows in {int(row.n_groups)} physical groups; row-level RMSE = {value}. Prediction origin: {settings.get('prediction_origin', 'unknown')}."
        )
        agreement = result.tables.get("agreement_summary", pd.DataFrame())
        if not agreement.empty:
            output.append(
                result.settings.get("agreement_unit", "specimen_mean").replace("_", " ")
                + " agreement: "
                + str(agreement.iloc[0]["status"])
                + ". Limits are not a declaration of method interchangeability."
            )
    elif not scores.empty:
        pool = scores[scores.cohort.eq("common_scored_rows") & scores.group_rmse.notna()]
        output.append(
            f"Target: {response_label(result)}. Errors use held-out physical groups; comparisons use the stated common cohort."
        )
        if pool.empty:
            output.append(
                "The all-method common comparison is unavailable. Available predictions and their coverage remain in the complete tables; no common-cohort ranking is supported."
            )
        else:
            parts = pool.groupby("destination", sort=True) if "destination" in pool else [("all methods", pool)]
            for label, part in parts:
                best = part.loc[part.group_rmse.idxmin()]
                model = best.get("model", best.get("method"))
                budget = f"; {int(best.budget)} target standards" if "budget" in best else ""
                output.append(
                    f"{label}: lowest displayed group RMSE = {best.group_rmse:.6g} for {method_label(model)}{budget}, on {int(best.n)} rows / {int(best.n_groups)} groups. This ranking is descriptive and may change on new data."
                )
    if result.status != "complete" and result.notes:
        output.append(
            next(
                (
                    n
                    for n in reversed(result.notes)
                    if any(w in n.lower() for w in ["unavailable", "fewer", "at least", "no reference", "independence"])
                ),
                result.notes[-1],
            )
        )
    return output


def make_figure(result, selected_response=None):
    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["Times New Roman", "DejaVu Serif"],
            "font.size": 10,
            "axes.titlesize": 12,
            "axes.titleweight": "bold",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "savefig.bbox": "tight",
        }
    )
    prediction = result.tables.get("predictions")
    if prediction is None or prediction.empty:
        return None, "No figure: the available input supports a quality audit only."
    if result.title.startswith("AssayReport"):
        fig, axes = plt.subplots(2, 3, figsize=(11.7, 7.8), layout="constrained")
        axes = axes.ravel()
        response = result.tables.get("response_reference", pd.DataFrame())
        if not response.empty:
            axes[0].scatter(response.feature_value, response.reference, c="black", s=12, alpha=0.55)
            axes[0].set(xlabel=str(response.feature.iloc[0]), ylabel="Reference")
        else:
            axes[0].text(0.5, 0.5, "Measurement features not supplied", ha="center", transform=axes[0].transAxes)
        correlations = result.tables.get("feature_correlations", pd.DataFrame())
        if not correlations.empty:
            selected = correlations.head(12)
            axes[1].barh(range(len(selected)), selected.pearson_r_descriptive, color="0.4")
            axes[1].set_yticks(range(len(selected)), selected.feature, fontsize=7)
            axes[1].set(xlabel="Descriptive Pearson r", xlim=(-1, 1))
        else:
            axes[1].text(0.5, 0.5, "Feature correlations unavailable", ha="center", transform=axes[1].transAxes)
        pair = prediction.dropna(subset=["reference", "prediction"])
        axes[2].scatter(pair.reference, pair.prediction, color="black", s=12, alpha=0.5)
        if len(pair):
            bounds = [
                min(pair.reference.min(), pair.prediction.min()),
                max(pair.reference.max(), pair.prediction.max()),
            ]
            axes[2].plot(bounds, bounds, "--", color="0.5")
        axes[2].set(xlabel="Reference", ylabel="Prediction")
        score = result.tables["scores"].iloc[0]
        values = [score.get("rmse"), score.get("mae"), score.get("bias")]
        axes[3].bar(["RMSE", "MAE", "Bias"], [v if v is not None else np.nan for v in values], color="0.4")
        axes[3].set_ylabel(response_label(result))
        axes[4].scatter(pair.prediction, pair.residual, color="black", s=12, alpha=0.5)
        axes[4].axhline(0, color="0.5", linestyle="--")
        axes[4].set(xlabel="Prediction", ylabel="Prediction − reference")
        ba = result.tables.get("agreement_pairs", pd.DataFrame())
        limits = result.tables.get("agreement_summary", pd.DataFrame())
        if not ba.empty:
            axes[5].scatter(ba.mean_of_pair, ba.difference, color="black", s=18)
        if len(limits) and "bias" in limits:
            for c in [c for c in ["bias", "loa95_low", "loa95_high"] if c in limits and pd.notna(limits.iloc[0][c])]:
                axes[5].axhline(limits.iloc[0][c], color="0.4", linestyle="-" if c == "bias" else "--")
        axes[5].set(xlabel="Mean of paired values", ylabel="Comparison minus reference")
        if len(limits) and "loa95_low" not in limits:
            axes[5].text(
                0.5,
                0.85,
                "Agreement limits unavailable: fewer than\nthree agreement units",
                ha="center",
                va="top",
                transform=axes[5].transAxes,
                fontsize=9,
            )
        if pair.empty:
            for position in [2, 3, 4]:
                axes[position].text(
                    0.5,
                    0.5,
                    "No finite reference/prediction pairs",
                    ha="center",
                    transform=axes[position].transAxes,
                    fontsize=8,
                )
        for ax, title in zip(
            axes,
            [
                "A  Response and reference",
                "B  Feature associations",
                "C  Prediction and reference",
                "D  Error measures",
                "E  Signed residuals",
                "F  Agreement of paired values",
            ],
        ):
            ax.set_title(title, loc="left")
        caption = (
            f"Figure 1. Assay diagnostics. Prediction origin: {result.settings.get('prediction_origin')}. "
            "A uses the first selected feature; B displays the first 12 selected features in input order without ranking. "
            f"C–E use available reference/comparison pairs. F uses the declared {result.settings.get('agreement_unit', 'specimen_mean')} units; "
            "dashed limits are bias ± 1.96 SD of those differences. Missing panels are identified explicitly."
        )
    elif result.title.startswith("MatchedDoE"):
        response = selected_response or prediction.response.iloc[0]
        pair = prediction[prediction.response.eq(response)]
        fig, axes = plt.subplots(1, 2, figsize=(9, 4), layout="constrained")
        axes[0].scatter(pair.reference, pair.prediction, c="black")
        bounds = [min(pair.reference.min(), pair.prediction.min()), max(pair.reference.max(), pair.prediction.max())]
        axes[0].plot(bounds, bounds, "--", c="0.5")
        axes[0].set(
            xlabel="Measured " + response_label(result, response),
            ylabel="Fitted " + response_label(result, response),
            title="A  Observed versus fitted",
        )
        axes[1].scatter(pair.prediction, pair.residual, c="black")
        axes[1].axhline(0, c="0.5", ls="--")
        axes[1].set(
            xlabel="Fitted " + response_label(result, response),
            ylabel="Fitted − measured (response units)",
            title="B  Residuals",
        )
        caption = f"Figure 1. In-sample fit and residuals for {response}; these panels do not show independent prediction validation. All responses are retained in the result tables."
    else:
        scores = result.tables.get("scores", pd.DataFrame()).copy()
        if scores.empty:
            return None, "No scores available for plotting."
        if result.title.startswith("SenseFusion"):
            scores = scores[scores.cohort.eq("common_scored_rows")]
            labels = scores.model.map(method_label)
            caption = "Figure 1. Group-weighted RMSE on the same scored observations for every eligible method. Excluded methods remain identified in tables. Weights and component choices are learned inside the training folds; lower error is better. Prediction coverage is reported separately."
        else:
            if "cohort" in scores:
                scores = scores[scores.cohort.eq("common_scored_rows")]
            labels = (
                scores.destination.astype(str)
                + " / "
                + scores.method.map(method_label)
                + " / standards="
                + scores.budget.astype(str)
            )
            caption = "Figure 1. Leave-formulation-out transfer error on common scored formulations within each target domain, by correction and target-standard budget k. Each held-out formulation is excluded from source training and all adaptation standards. Separate available-row scores retain coverage information."
        usable = scores.group_rmse.notna() & scores.n.gt(0)
        if not usable.any():
            return (
                None,
                "Common-cohort figure unavailable: no measured/predicted observations support every requested method. See available-row scores and exclusions.",
            )
        scores = scores.loc[usable]
        labels = labels.loc[usable]
        fig, ax = plt.subplots(figsize=(10.5, max(3.5, 0.28 * len(scores))), layout="constrained")
        ax.barh(range(len(scores)), scores.group_rmse, color="0.35")
        ax.set_yticks(range(len(scores)), labels)
        ax.invert_yaxis()
        ax.set(xlabel="Group-weighted RMSE — " + response_label(result), title="Held-out evaluation")
    return fig, caption


def html_report(result, caption, has_figure, catalog=None):
    tables = []
    primary = ["scores", "model_summary", "anova", "equation_comparison", "selected_candidates", "agreement_summary"]
    ordered = [k for k in primary if k in result.tables] + [k for k in result.tables if k not in primary]
    appendix_started = False
    for number, name in enumerate(ordered, 1):
        table = result.tables[name]
        if name not in primary and not appendix_started:
            tables.append(
                "<h2>Audit appendix</h2><p>Complete tables are supplied as CSV; previews below retain the stated row and column limits.</p>"
            )
            appendix_started = True
        preview_size = 12 if name in {"aggregated_input", "candidates", "splits", "input_audit"} else 24
        display = table.head(preview_size).copy()
        for key in ["model", "method"]:
            if key in display:
                display[key] = display[key].map(method_label)
        notice = (
            f" Showing {preview_size} of {len(table)} rows; the complete table is in {name}.csv."
            if len(table) > preview_size
            else ""
        )
        if len(table.columns) > 12 and name in {"aggregated_input", "candidates", "splits", "input_audit"}:
            display = display.iloc[:, :8]
            notice += " The report previews the first eight columns; the CSV preserves every column."
        columns = list(display.columns)
        chunks = (
            [columns] if len(columns) <= 6 else [[columns[0]] + columns[i : i + 5] for i in range(1, len(columns), 5)]
        )
        sections = []
        for part, chunk in enumerate(chunks, 1):
            label = f" Part {part}/{len(chunks)}." if len(chunks) > 1 else ""
            sections.append(
                f"<p>{label}</p>"
                + display[chunk].to_html(index=False, border=0, float_format=lambda x: f"{x:.6g}", escape=True)
            )
        tables.append(
            f"<section><h2>Table {number}. {escape(name.replace('_', ' '))}</h2><p>{escape(notice)}</p>{''.join(sections)}</section>"
        )
    if catalog is None:
        catalog = [{"stem": "figure", "title": "Analysis overview", "caption": caption}] if has_figure else []
    figure = (
        "".join(
            f'<section class="diagnostic" id="{escape(item["stem"])}"><h2>Figure {index}. {escape(item["title"])}</h2>'
            f'<img src="{escape(item["stem"])}.png" alt="{escape(item["title"])}"><p>{escape(item["caption"])}</p></section>'
            for index, item in enumerate(catalog, 1)
        )
        or f"<p>{escape(caption)}</p>"
    )
    navigation = (
        '<nav><a href="#summary">Summary</a> · '
        + " · ".join(f'<a href="#{escape(item["stem"])}">{escape(item["title"])}</a>' for item in catalog)
        + '<br><a href="#tables">Complete evidence tables</a></nav>'
    )
    summary = "".join("<p>" + escape(line) + "</p>" for line in result_summary(result))
    return f"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(result.title)}</title><style>
body{{font-family:"Times New Roman",serif;font-size:10pt;line-height:1.5;max-width:1100px;margin:30px auto;padding:0 24px;color:#111}}
h1,h2{{font-size:12pt;font-weight:bold}} table{{border-collapse:collapse;margin:16px auto;width:100%;table-layout:fixed;font-size:10pt}}
th,td{{padding:4px 7px;text-align:center;border:0;overflow-wrap:anywhere}}thead{{border-top:1px solid black;border-bottom:1px solid black}}tbody{{border-bottom:1px solid black}}
nav{{padding:12px 0;border-bottom:1px solid #bbb;line-height:1.8}}a{{color:#17466b}}.diagnostic{{break-inside:avoid}}img{{max-width:100%;max-height:230mm;object-fit:contain}}pre{{white-space:pre-wrap;overflow-wrap:anywhere}}section{{margin-top:28px}}@page{{size:A4;margin:16mm 15mm}}@media print{{nav{{display:none}}body{{margin:0}}img{{max-height:230mm}}thead{{display:table-header-group}}tr{{break-inside:avoid}}}}
</style><h1>{escape(result.title)}</h1>{navigation}<h2 id="summary">Result summary</h2>{summary}
{figure}<h2>Interpretation and limits</h2><ul>{"".join("<li>" + escape(n) + "</li>" for n in result.notes)}</ul>
<div id="tables">{"".join(tables)}</div><h2>Analysis settings</h2><pre>{escape(json_text(result.settings))}</pre></html>"""


RENDER_LOCK = threading.RLock()


def serialized_render(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        with RENDER_LOCK:
            return function(*args, **kwargs)

    return wrapped


def encode_figure(figure, formats=("png", "pdf", "svg"), png_dpi=300):
    """Solve the layout once, then reuse it for the three export backends."""
    figure.canvas.draw()
    figure.set_layout_engine("none")
    encoded = {}
    with plt.rc_context({"savefig.bbox": None, "svg.fonttype": "none"}):
        for extension in formats:
            buffer = io.BytesIO()
            figure.savefig(buffer, format=extension, dpi=png_dpi if extension == "png" else 300)
            encoded[extension] = buffer.getvalue()
    return encoded


@serialized_render
def _extended_files(result, formats=("png", "pdf", "svg"), png_dpi=300):
    output = {}
    from .visuals import overview

    try:
        fig, caption = make_figure(result)
    except Exception as exc:  # noqa: BLE001 - legacy overview is an optional post-fit illustration
        fig, caption = None, "Legacy overview unavailable; numerical tables and concise report remain available."
        result.settings.setdefault("diagnostic_errors", []).append(
            {"id": "legacy_overview", "type": type(exc).__name__, "message": str(exc)}
        )
    if result.title.startswith(("SenseFusion", "CalibShift")) and "scores" in result.tables:
        try:
            redesigned = overview(result)
        except Exception as exc:  # noqa: BLE001 - optional overview, not core calculation
            redesigned = None
            result.settings.setdefault("diagnostic_errors", []).append(
                {"id": "extended_overview", "type": type(exc).__name__, "message": str(exc)}
            )
        if redesigned is not None:
            if fig is not None:
                plt.close(fig)
            fig = redesigned
    catalog = []
    if fig is not None:
        catalog.append({"stem": "figure", "title": "Analysis overview", "caption": caption})
    if fig is not None:
        output.update({"figure." + ext: content for ext, content in encode_figure(fig, formats, png_dpi).items()})
        plt.close(fig)
    if result.title.startswith("MatchedDoE") and "predictions" in result.tables:
        responses = result.tables["predictions"].response.unique().tolist()
        for index, response in enumerate(responses[1:], 2):
            extra, extra_caption = make_figure(result, response)
            if extra is not None:
                output.update(
                    {
                        f"figure_response_{index}." + ext: content
                        for ext, content in encode_figure(extra, formats, png_dpi).items()
                    }
                )
                plt.close(extra)
                catalog.append(
                    {
                        "stem": f"figure_response_{index}",
                        "title": "Fitted response: " + str(response),
                        "caption": extra_caption,
                    }
                )
                output[f"figure_response_{index}_caption.txt"] = extra_caption.replace(
                    "Figure 1.", f"Figure {index}."
                ).encode("utf-8")
    if result.settings.get("application"):
        for stem, title, description, diagnostic in guarded_diagnostics(result):
            output.update(
                {stem + "." + ext: content for ext, content in encode_figure(diagnostic, formats, png_dpi).items()}
            )
            plt.close(diagnostic)
            output[stem + "_caption.txt"] = description.encode("utf-8")
            catalog.append({"stem": stem, "title": title, "caption": description})
    output["figure_catalog.json"] = json_text(catalog).encode("utf-8")
    from .workbook import workbook_bytes

    output["results.xlsx"] = workbook_bytes(result)
    for name, table in result.tables.items():
        output[f"{name}.csv"] = table.to_csv(index=False, lineterminator="\n").encode("utf-8-sig")
    metadata = {
        "title": result.title,
        "status": result.status,
        "settings": result.settings,
        "notes": result.notes,
        "environment": environment(),
        "created_utc": datetime.now(UTC).isoformat(),
        "export_profile": {"figure_formats": list(formats), "png_dpi": png_dpi},
        "tables": {name: len(table) for name, table in result.tables.items()},
    }
    metadata.update(
        application=result.settings.get("application"),
        software_version=result.settings.get("software_version"),
        configuration_schema_version=result.settings.get("configuration_schema_version"),
        computation_status="completed",
        export_status="partial" if result.settings.get("diagnostic_errors") else "completed",
        evidence_status=result.settings.get("evidence_summary", result.status),
    )
    output["run.json"] = json_text(metadata).encode("utf-8")
    output["config.json"] = json_text(
        result.settings.get("export_config", result.settings.get("call_parameters", {}))
    ).encode("utf-8")
    output["provenance.json"] = json_text(result.settings.get("provenance", {"kind": "user_provided"})).encode("utf-8")
    output["summary.txt"] = "\n\n".join(result_summary(result)).encode("utf-8")
    output["README.txt"] = (
        b"Open report.html after extracting the complete archive. CSV files retain complete tables. "
        b"Retain your original input table: raw uploaded inputs are not copied into this report archive. "
        b"config.json contains resolved analysis arguments; run.json records versions, parsed-table hash, evidence and settings. "
        b"Creation time is excluded from deterministic numerical comparisons. Code and data licensing are separate; see provenance.json."
    )
    output["caption.txt"] = caption.encode("utf-8")
    output["report.html"] = html_report(result, caption, fig is not None, catalog).encode("utf-8")
    return output


def guarded_diagnostics(result):
    """Optional post-fit diagnostics cannot invalidate already computed core tables."""
    from .visuals import figures

    try:
        yield from figures(result)
    except Exception as exc:  # noqa: BLE001 - optional post-fit diagnostics are isolated; core errors propagate
        result.settings.setdefault("diagnostic_errors", []).append(
            {"id": "diagnostic_figures", "type": type(exc).__name__, "message": str(exc)}
        )


@serialized_render
def summary_files(result, *, response=None, domain=None, method=None, budget=None, include_pdf=False, png_dpi=160):
    from .presentation import overview_content, primary_figures, select_view, summary_html, summary_pdf

    view = select_view(result, response, domain, method, budget)
    content = overview_content(result, view)
    output = {}
    items = []
    for stem, title, caption, fig in primary_figures(result, view):
        try:
            encoded = encode_figure(fig, formats=("png",), png_dpi=png_dpi)
            output[stem + ".png"] = encoded["png"]
            items.append({"stem": stem, "title": title, "caption": caption, "png": encoded["png"]})
        finally:
            plt.close(fig)
    output["report.html"] = summary_html(result, view, content, items).encode("utf-8")
    output["summary.txt"] = (content["statement"] + "\n\n" + content["caveat"]).encode("utf-8")
    output["summary_cohort.csv"] = view["cohort"].to_csv(index=False).encode("utf-8-sig")
    output["summary_view.json"] = json_text(
        {
            key: view[key]
            for key in [
                "method",
                "domain",
                "response",
                "budget",
                "scope",
                "reason",
                "n_available_pairs",
                "n_primary_pairs",
            ]
        }
    ).encode("utf-8")
    output["primary_catalog.json"] = json_text(
        [{k: v for k, v in item.items() if k != "png"} for item in items]
    ).encode("utf-8")
    if include_pdf:
        output["summary.pdf"] = summary_pdf(result, view, content, items)
    return output


@serialized_render
def diagnostic_files(result, stem, formats=("png",), png_dpi=160):
    """Render a requested diagnostic only after the user opens advanced diagnostics."""
    for name, title, caption, figure in guarded_diagnostics(result):
        try:
            if name == stem:
                return {name + "." + ext: data for ext, data in encode_figure(figure, formats, png_dpi).items()} | {
                    "caption.txt": caption.encode("utf-8")
                }
        finally:
            plt.close(figure)
    return {}


@serialized_render
def files_for_result(result, formats=("png", "pdf", "svg"), png_dpi=300, **selection):
    output = _extended_files(result, formats, png_dpi)
    output["extended_report.html"] = output.pop("report.html")
    output.update(summary_files(result, include_pdf=True, png_dpi=png_dpi, **selection))
    output["README.txt"] += (
        b" Open report.html or summary.pdf for the concise scientific view. extended_report.html contains the complete diagnostic appendix."
    )
    return output


def archive_result(result):
    memory = io.BytesIO()
    with zipfile.ZipFile(memory, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files_for_result(result).items():
            archive.writestr(name, content)
    return memory.getvalue()


def save_result(result, directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    if any(directory.iterdir()):
        raise InputError("Choose a new or empty output directory so an earlier analysis is preserved.")
    for name, content in files_for_result(result).items():
        (directory / name).write_bytes(content)
    return directory
