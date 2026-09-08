"""Concise scientific views from a finished result; no fitting or model selection."""

import base64
import io
from html import escape

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .visuals import COLORS, MARKERS, STYLE, label, target_label, wrapped

QUESTIONS = {
    "sensefusion": "Does combining measurement blocks improve prediction?",
    "calibshift": "How much do target standards improve this calibration transfer?",
    "matcheddoe": "What response pattern is supported by these experimental runs?",
    "assayreport": "How closely do the paired values match their reference?",
}


def select_view(result, response=None, domain=None, method=None, budget=None):
    """Resolve a finished result by eligibility, never by observed error.

    Prefer equal fusion, bias correction, source PLS, then single blocks in
    recorded order, then means. A stale selection falls back to this order.
    Primary predictions are exactly the stored metric cohort. With no common
    cohort, an eligible available-row result is explicitly standalone.
    """
    slug = result.settings.get("application", "")
    pred = result.tables.get("predictions", pd.DataFrame()).copy()
    scores = result.tables.get("model_summary" if slug == "matcheddoe" else "scores", pd.DataFrame()).copy()
    options = {}
    for column, key, requested in [("destination", "domain", domain), ("response", "response", response)]:
        values = list(pred[column].drop_duplicates()) if column in pred else []
        options[key] = values
        chosen = requested if requested in values else (values[0] if values else None)
        if key == "domain":
            domain = chosen
        else:
            response = chosen
        if values:
            pred = pred[pred[column].eq(chosen)]
            if column in scores:
                scores = scores[scores[column].eq(chosen)]
    method_col = "model" if "model" in pred else "method" if "method" in pred else None
    scope = "fitted_observations" if slug == "matcheddoe" else "paired_readings"
    reason = ""
    comparison = scores.copy()
    if "cohort" in scores:
        allowed = result.settings.get("common_comparison", {}).get("methods")
        if allowed is not None and method_col in scores:
            scores = scores[scores[method_col].isin(allowed)]
        common = scores[scores.cohort.eq("common_scored_rows") & scores.n.gt(0)]
        if len(common):
            scores = common
            comparison = common.copy()
            scope = "common_comparison_cohort"
        else:
            scores = scores[scores.cohort.eq("all_available_rows") & scores.n.gt(0)]
            comparison = scores.iloc[:0].copy()
            scope = "standalone_available_pairs" if len(scores) else "no_usable_evidence"
            reason = "No shared scored cohort is available; this is a standalone result, not a family comparison."
        if slug == "sensefusion" and not any(str(m).startswith(("late_", "early_")) for m in scores.get("model", [])):
            reason = (
                "Fusion is unavailable; the view shows an eligible single-block model or training-mean baseline. "
                + reason
            )
    methods, budgets = [], []
    if method_col:
        methods = list(scores[method_col].drop_duplicates()) if method_col in scores else []
        preferred = ["late_equal", "late_equal_fixed1", "bias_correction", "source_pls"]
        preferred += [m for m in methods if str(m).startswith("single_")]
        preferred += ["training_mean", "source_mean"]
        method = (
            method
            if method in methods
            else next((m for m in preferred if m in methods), methods[0] if methods else None)
        )
        pred = pred[pred[method_col].eq(method)]
        if method_col in scores:
            scores = scores[scores[method_col].eq(method)]
        if "budget" in scores:
            budgets = sorted(scores.budget.drop_duplicates())
            budget = budget if budget in budgets else (budgets[0] if budgets else None)
            pred = pred[pred.budget.eq(budget)]
            scores = scores[scores.budget.eq(budget)]
    if method_col is None:
        method = None
    if "budget" not in scores:
        budget = None
    options.update(method=methods, budget=budgets)
    all_predictions = pred.copy()
    valid = (
        (np.isfinite(pred.reference) & np.isfinite(pred.prediction))
        if {"reference", "prediction"} <= set(pred)
        else pd.Series(False, index=pred.index)
    )
    used = valid.copy()
    if scope == "common_comparison_cohort":
        # The core records membership at the same point at which it scores it.
        used &= pred["in_common_cohort"].astype(bool)
    pred = pred.loc[used].copy()
    identity = [
        c
        for c in ["sample_id", "group", "fold", "evaluation", "destination", "response", method_col, "budget"]
        if c is not None and c in all_predictions
    ]
    cohort = all_predictions[identity].copy()
    cohort["included_in_primary_score_and_figure"] = used.to_numpy()
    cohort["has_finite_pair"] = valid.to_numpy()
    return {
        "slug": slug,
        "response": response,
        "domain": domain,
        "method": method,
        "budget": budget,
        "predictions": pred,
        "all_predictions": all_predictions,
        "scores": scores,
        "comparison": comparison,
        "scope": scope,
        "reason": reason.strip(),
        "options": options,
        "cohort": cohort,
        "n_available_pairs": int(valid.sum()),
        "n_primary_pairs": int(used.sum()),
    }


def _fmt(value):
    return (
        "Unavailable"
        if value is None or pd.isna(value)
        else f"{value:.4g}"
        if isinstance(value, (int, float, np.number))
        else str(value)
    )


def overview_content(result, view):
    slug = view["slug"]
    pred = view["predictions"]
    scores = view["scores"]
    unit = (
        result.settings.get("columns", {})
        .get(view["response"] or result.settings.get("target"), {})
        .get("unit", "not specified")
    )
    pair = (
        pred.dropna(subset=["reference", "prediction"]) if {"reference", "prediction"} <= set(pred) else pd.DataFrame()
    )
    row = scores.iloc[0] if not scores.empty else pd.Series(dtype=object)
    if slug == "matcheddoe":
        cards = [
            ("Used runs", row.get("n")),
            ("Fitted R²", row.get("r2_fitted")),
            ("Residual df", row.get("residual_df")),
            ("Residual SS (units²)", row.get("residual_ss")),
        ]
        caveat = (
            "These are in-sample fits. Predicted candidate conditions are not independent confirmation experiments."
        )
        statement = f"The selected {result.settings.get('model', '')} model describes {view['response'] or 'the selected response'} using {_fmt(row.get('n'))} complete runs. Fitted R² is {_fmt(row.get('r2_fitted'))}; residual degrees of freedom are {_fmt(row.get('residual_df'))}. "
        statement += (
            "Responses were fitted on their own available rows; their cohorts and coding may differ. "
            if result.settings.get("response_mode") == "per_response"
            else "Selected responses use the same complete runs and supported candidate conditions. "
        )
        statement += "Inspect observed versus fitted values and residuals before using the model. Coefficient or prediction intervals appear only where residual variation and the independence declaration support them. The data and fitted coefficients remain available even when an uncertainty measure or candidate grid is unavailable."
    else:
        key = "group_rmse" if slug != "assayreport" else "rmse"
        cards = [
            ("Group RMSE" if slug != "assayreport" else "RMSE", row.get(key)),
            ("MAE", row.get("mae")),
            ("Bias", row.get("bias")),
            ("Usable pairs", row.get("n", len(pair))),
        ]
        if slug == "sensefusion":
            caveat = "This held-out comparison is descriptive. Choosing the displayed winner does not independently validate a selection rule."
            statement = f"The selected method, {label(view['method'])}, gives group RMSE {_fmt(row.get(key))}, MAE {_fmt(row.get('mae'))} and signed bias {_fmt(row.get('bias'))} in response units. "
            comp = view["comparison"]
            single = comp[comp.model.astype(str).str.startswith("single_")] if "model" in comp else pd.DataFrame()
            fusion = comp[comp.model.eq("late_equal")] if "model" in comp else pd.DataFrame()
            if len(single) and len(fusion) and single.group_rmse.notna().any() and pd.notna(fusion.iloc[0].group_rmse):
                a = float(single.group_rmse.min())
                b = float(fusion.iloc[0].group_rmse)
                statement += f"On the stated common cohort, equal fusion {'reduced' if b < a else 'did not reduce'} error relative to the lowest displayed single-block error ({b:.4g} versus {a:.4g}). "
            statement += "Preprocessing and tuning use training data only. Missing blocks affect coverage; fusion need not improve performance. Sparse groups support exploratory conclusions only."
        elif slug == "calibshift":
            caveat = "The same unchanged physical formulation must be matched across conditions. Standards used for correction are excluded from held-out validation."
            statement = f"Transfer direction is {result.settings.get('source')} to {view['domain']}. The selected {label(view['method'])} uses {view['budget'] or 0} target standards and gives group RMSE {_fmt(row.get(key))} and bias {_fmt(row.get('bias'))}. "
            statement += "The budget plot uses the common held-out set. Unavailable fits and standard identities are recorded in extended tables. Increasing a budget or fitting a slope can worsen performance. This protocol does not establish transfer across arbitrary instruments or laboratories."
        else:
            caveat = "Error, R² and correlation do not establish interchangeability. Agreement depends on the selected unit and independence assumptions."
            statement = f"There are {len(pair)} usable paired values. RMSE is {_fmt(row.get('rmse'))}, MAE {_fmt(row.get('mae'))}, and bias {_fmt(row.get('bias'))} in response units. Positive bias means the comparison value exceeds the reference. "
            statement += f"Values are identified as {result.settings.get('comparison_kind', 'prediction')}; agreement is shown for {result.settings.get('agreement_unit', 'specimen_mean').replace('_', ' ')} units. "
            statement += "A recorded zero reference remains valid for absolute errors, while its percentage error is unavailable. Missing pairs are retained in the audit and excluded explicitly from the affected calculations. Uncertainty is withheld when the sample structure, variance or prediction provenance does not support it. Small tables describe their observations without establishing population performance."
    if slug in {"sensefusion", "calibshift"}:
        statement += f" Primary score and scatter: {view['n_primary_pairs']} paired rows ({view['scope'].replace('_', ' ')}); {view['n_available_pairs']} pairs are available for this method in the full export. Group RMSE weights physical groups equally; MAE and bias weight rows equally."
        if view["reason"]:
            caveat = view["reason"] + " " + caveat
    if slug == "assayreport" and len(result.tables.get("agreement_summary", [])):
        agreement = result.tables["agreement_summary"].iloc[0]
        statement += f" Agreement uses {agreement['n_agreement_units']} {agreement['estimand'].replace('_', ' ')} from {agreement['n_valid_pairs']} valid pairs; physical specimens: {_fmt(agreement['n_physical_specimens'])}. Independence: {agreement['independence_status'].replace('_', ' ')}."
    if result.status == "audit_only":
        statement = "The file was parsed and its available fields were inspected. The selected data do not support the requested numerical comparison. Review the capability reasons and column roles; recorded measurements have not been filled in or changed."
        cards = [
            ("Input rows", result.settings.get("n_input_rows")),
            ("Fields", len(result.settings.get("columns", {}))),
        ]
    if result.status != "complete":
        specific = next(
            (
                n
                for n in result.notes
                if any(
                    w in n.lower()
                    for w in [
                        "no complete",
                        "only one",
                        "fewer than",
                        "small-data",
                        "not confirmed",
                        "unavailable",
                        "rank is",
                    ]
                )
            ),
            None,
        )
        if specific:
            caveat = (view["reason"] + " " + specific).strip()
    return {
        "question": QUESTIONS.get(slug, result.title),
        "cards": cards,
        "unit": unit,
        "statement": statement,
        "caveat": caveat,
        "evidence": result.settings.get("evidence_summary", result.status),
    }


def _scatter(ax, x, y, color=COLORS[0]):
    finite = np.isfinite(np.asarray(x, float)) & np.isfinite(np.asarray(y, float))
    x = np.asarray(x, float)[finite]
    y = np.asarray(y, float)[finite]
    if len(x) > 2000:
        artist = ax.hexbin(x, y, gridsize=40, mincnt=1, cmap="cividis")
        ax.figure.colorbar(artist, ax=ax, label="Observations per cell")
        mode = f"All {len(x):,} pairs represented by hexagonal counts; no analysis rows removed."
    else:
        ax.scatter(x, y, s=24 if len(x) < 50 else 12, color=color, alpha=0.8 if len(x) < 50 else 0.5, edgecolors="none")
        mode = f"All {len(x):,} finite pairs displayed."
    return x, y, mode


def primary_figures(result, view):
    slug = view["slug"]
    pred = view["predictions"]
    comparison = view["comparison"]
    if pred.empty:
        return []
    pair = pred.dropna(subset=["reference", "prediction"])
    if pair.empty:
        return []
    outputs = []
    unit_label = target_label(result, view["response"])
    with plt.rc_context(STYLE | {"text.parse_math": False}):
        if slug == "sensefusion" and not comparison.empty:
            comparison = comparison[comparison.group_rmse.notna()]
            if not comparison.empty:
                fig, axes = plt.subplots(
                    1, 2, figsize=(9.2, 3.5), layout="constrained", gridspec_kw={"width_ratios": [3, 1]}
                )
                positions = np.arange(len(comparison))
                axes[0].barh(positions, comparison.group_rmse, color=COLORS[0], height=0.6)
                axes[0].set(
                    yticks=positions,
                    yticklabels=[wrapped(label(m), 31) for m in comparison.model],
                    xlabel="Group RMSE",
                    title="Common-cohort error",
                )
                axes[0].invert_yaxis()
                available = result.tables["scores"]
                available = available[available.cohort.eq("all_available_rows")].set_index("model")
                coverage = [available.loc[m, "coverage"] for m in comparison.model]
                axes[1].barh(positions, coverage, color=".55", height=0.6)
                axes[1].set(yticks=[], xlim=(0, 1.05), xlabel="Fraction scored", title="Available coverage")
                axes[1].invert_yaxis()
                outputs.append(
                    (
                        "primary_comparison",
                        "Prediction error and coverage",
                        f"Errors use {unit_label}. Error values refer to the same scored cohort; coverage uses each method's available labelled rows. No uncertainty bars are implied.",
                        fig,
                    )
                )
        elif slug == "calibshift" and not comparison.empty:
            fig, ax = plt.subplots(figsize=(9.2, 3.3), layout="constrained")
            for i, (method, part) in enumerate(comparison.groupby("method", sort=True)):
                part = part.dropna(subset=["group_rmse"]).sort_values("budget")
                if part.empty:
                    continue
                if method in ["source_pls", "source_mean"]:
                    ax.axhline(
                        part.group_rmse.iloc[0],
                        color=COLORS[i % len(COLORS)],
                        linestyle="--" if method == "source_pls" else ":",
                        label=label(method),
                    )
                else:
                    ax.plot(
                        part.budget,
                        part.group_rmse,
                        marker=MARKERS[i % len(MARKERS)],
                        color=COLORS[i % len(COLORS)],
                        label=label(method),
                    )
            ax.set(
                xlabel="Target standards used",
                ylabel="Group RMSE",
                title=wrapped(f"{result.settings.get('source')} to {view['domain']}: error and standard budget", 75),
                ylim=(0, None),
            )
            ax.legend(fontsize=8, ncols=2)
            outputs.append(
                (
                    "primary_comparison",
                    "Transfer error versus standard budget",
                    f"Errors use {unit_label}, on the recorded common held-out cohort. Lines join evaluated budgets only; they do not imply a continuous optimum. Unadapted source baselines use zero target standards.",
                    fig,
                )
            )
        if slug in ["sensefusion", "calibshift"]:
            fig, ax = plt.subplots(figsize=(7.6, 3.4), layout="constrained")
            x, y, display = _scatter(ax, pair.reference, pair.prediction)
            low, high = min(x.min(), y.min()), max(x.max(), y.max())
            padding = max((high - low) * 0.05, abs(high) * 0.01, 1e-12)
            ax.plot([low - padding, high + padding], [low - padding, high + padding], c=".4", ls="--")
            ax.set(
                xlabel=wrapped("Recorded " + unit_label, 65),
                ylabel="Held-out prediction",
                title=wrapped(
                    label(view["method"]) + (f" (k={view['budget']})" if view["budget"] is not None else ""), 70
                ),
                xlim=(low - padding, high + padding),
                ylim=(low - padding, high + padding),
            )
            outputs.append(
                (
                    "primary_prediction",
                    "Recorded versus held-out prediction",
                    display
                    + " Dashed line is equality. "
                    + unit_label
                    + f". Scope: {view['scope'].replace('_', ' ')}; exactly the {view['n_primary_pairs']} headline-score rows. All {view['n_available_pairs']} available pairs remain in extended predictions; summary_cohort.csv records membership.",
                    fig,
                )
            )
        elif slug == "matcheddoe":
            fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.4), layout="constrained")
            x, y, display = _scatter(axes[0], pair.reference, pair.prediction)
            low, high = min(x.min(), y.min()), max(x.max(), y.max())
            axes[0].plot([low, high], [low, high], ls="--", c=".4")
            axes[0].set(xlabel="Observed response", ylabel="Fitted response", title="Observed versus fitted")
            _scatter(axes[1], pair.prediction, pair.residual, COLORS[2])
            axes[1].axhline(0, c=".4", ls="--")
            axes[1].set(xlabel="Fitted response", ylabel="Fitted minus observed", title="Residuals")
            outputs.append(
                (
                    "primary_fit",
                    "Fitted values and residuals",
                    display
                    + " Units: "
                    + unit_label
                    + ". In-sample fitted values, not independent prediction validation.",
                    fig,
                )
            )
            factors = result.settings.get("factors", [])
            candidates = result.tables.get("candidates", pd.DataFrame())
            if result.settings.get("response_mode") == "per_response":
                candidates = result.tables.get("candidates_by_response", pd.DataFrame())
                if "response" in candidates:
                    candidates = candidates[candidates.response.eq(view["response"])]
            column = result.settings["candidate_columns"]["predictions"].get(view["response"])
            observed = result.tables.get("observed_factor_values", pd.DataFrame())
            if len(factors) == 1 and column in candidates and len(candidates):
                fig, ax = plt.subplots(figsize=(8, 3.2), layout="constrained")
                ax.plot(
                    candidates[result.settings["candidate_columns"]["factors"][factors[0]]],
                    candidates[column],
                    color=COLORS[2],
                    label="Fitted curve",
                )
                if not observed.empty:
                    lookup = (
                        observed[observed.factor.eq(factors[0])]
                        .drop_duplicates("sample_id")
                        .set_index("sample_id")
                        .value
                    )
                    x = pair.sample_id.map(lookup)
                    ax.scatter(x, pair.reference, color="black", s=22, label="Observed runs")
                ax.set(
                    xlabel=wrapped(factors[0], 55),
                    ylabel=wrapped(unit_label, 45),
                    title="Fitted response over the observed factor range",
                )
                ax.legend(fontsize=8)
                outputs.append(
                    (
                        "primary_effect",
                        "One-factor response curve",
                        "Curve uses the stated polynomial within the observed factor range. Points are recorded runs. No additional observations or confidence band are invented.",
                        fig,
                    )
                )
            elif "coefficients" in result.tables:
                coef = result.tables["coefficients"]
                coef = coef[coef.response.eq(view["response"]) & coef.term.ne("Intercept")].head(16)
                if len(coef):
                    fig, ax = plt.subplots(figsize=(8, max(2.4, min(4.2, 0.3 * len(coef) + 1))), layout="constrained")
                    ax.scatter(coef.coefficient_coded, np.arange(len(coef)), color=COLORS[2], s=25)
                    for i, row in enumerate(coef.itertuples()):
                        if pd.notna(row.ci95_low):
                            ax.plot([row.ci95_low, row.ci95_high], [i, i], c=COLORS[2])
                    ax.axvline(0, c=".5", ls=":")
                    ax.set(
                        yticks=np.arange(len(coef)),
                        yticklabels=[wrapped(x.replace("_", " ").replace(":", " × "), 30) for x in coef.term],
                        xlabel="Coefficient in coded-factor basis",
                        title="Factor coefficients",
                    )
                    ax.invert_yaxis()
                    outputs.append(
                        (
                            "primary_effect",
                            "Coded factor coefficients",
                            f"First {len(coef)} non-intercept terms in declared model order. Full table is exported. Lines, where available, are pointwise 95% coefficient intervals under the stated residual-variance and independence assumptions.",
                            fig,
                        )
                    )
        else:
            fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.5), layout="constrained")
            x, y, display = _scatter(axes[0], pair.reference, pair.prediction)
            low, high = min(x.min(), y.min()), max(x.max(), y.max())
            pad = max((high - low) * 0.05, abs(high) * 0.01, 1e-12)
            axes[0].plot([low - pad, high + pad], [low - pad, high + pad], c=".4", ls="--")
            axes[0].set(
                xlabel="Reference",
                ylabel="Comparison value",
                title="Reference versus comparison",
                xlim=(low - pad, high + pad),
                ylim=(low - pad, high + pad),
            )
            agreement = result.tables.get("agreement_pairs", pd.DataFrame())
            if len(agreement):
                _scatter(axes[1], agreement.mean_of_pair, agreement.difference, COLORS[2])
            limits = result.tables.get("agreement_summary", pd.DataFrame())
            if len(limits):
                for key in ["bias", "loa95_low", "loa95_high"]:
                    if key in limits and pd.notna(limits.iloc[0][key]):
                        axes[1].axhline(limits.iloc[0][key], c=".4", ls="-" if key == "bias" else "--")
            axes[1].set(
                xlabel="Mean of paired values",
                ylabel="Comparison minus reference",
                title="Differences: " + result.settings.get("agreement_unit", "specimen_mean").replace("_", " "),
            )
            outputs.append(
                (
                    "primary_agreement",
                    "Paired values and differences",
                    display
                    + " Units: "
                    + unit_label
                    + ". Difference points use the declared agreement unit. Dashed limits, only when available, are bias ± 1.96 sample SD of those differences; they are not confidence intervals or acceptance limits.",
                    fig,
                )
            )
    return outputs


def concise_table(view):
    scores = view["scores"]
    columns = ["response", "n", "n_groups", "group_rmse", "rmse", "mae", "bias", "r2", "r2_fitted", "residual_df"]
    columns = [c for c in columns if c in scores]
    return scores[columns].head(3)


def summary_html(result, view, content, figures):
    cards = "".join(
        f'<div class="metric"><span>{escape(name)}</span><strong>{escape(_fmt(value))}</strong></div>'
        for name, value in content["cards"]
    )
    gallery = "".join(
        f'<figure><img src="data:image/png;base64,{base64.b64encode(item["png"]).decode()}" alt="{escape(item["title"])}"><figcaption>{escape(item["caption"])}</figcaption></figure>'
        for item in figures
    )
    table = concise_table(view)
    if len(table):
        table = table.copy().map(_fmt).rename(columns=lambda c: c.replace("_", " "))
        table_html = table.to_html(index=False, border=0, escape=True)
    else:
        table_html = "<p>No eligible performance table. Input and capability details remain available.</p>"
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(result.title)}</title><style>
body{{font:10pt/1.5 'Times New Roman',serif;color:#172535;max-width:950px;margin:25px auto;padding:0 22px}}h1,h2{{font-size:12pt;font-weight:bold;line-height:1.5;margin:8px 0}}.status{{color:#445260}}.metrics{{display:flex;flex-wrap:wrap;gap:12px;margin:12px 0}}.metric{{border-top:1px solid #111;flex:1;min-width:120px;padding:7px}}.metric span{{display:block}}.metric strong{{font-size:14pt}}.caveat{{border-left:3px solid #536272;padding:6px 12px}}figure{{margin:15px 0;break-inside:avoid}}img{{max-width:100%;height:auto;max-height:370px;object-fit:contain}}figcaption{{font-size:9pt;line-height:1.4}}table{{width:100%;border-collapse:collapse;text-align:center;border-top:1px solid black;border-bottom:1px solid black}}th{{font-weight:bold;border-bottom:1px solid black}}th,td{{padding:5px;text-align:center;overflow-wrap:anywhere}}.footer{{font-size:9pt;color:#536272;overflow-wrap:anywhere}}@page{{size:A4;margin:15mm}}@media print{{body{{margin:0;padding:0;max-width:none}}button,nav{{display:none}}thead{{display:table-header-group}}img{{max-height:83mm}}figure{{margin:8px 0}}.metrics{{margin:6px 0}}h1,h2,figcaption{{break-after:avoid}}}}
</style></head><body><h1>{escape(content["question"])}</h1><p class="status">{escape(result.title)} · Version {escape(result.settings.get("software_version", ""))}<br>Execution completed. {escape(content["evidence"])}. Response units: {escape(content["unit"])}.</p><div class="metrics">{cards}</div><p>{escape(content["statement"])}</p><p class="caveat">{escape(content["caveat"])}</p>{table_html}{gallery}<p class="footer">Input: {escape(result.settings.get("input_name", "table"))}. Complete data tables, configuration, provenance and sample exclusions are in the optional extended bundle. Source fingerprint: {escape(result.settings.get("software_source_sha256", ""))}. Figures use one recorded calculation; changing the view does not refit a model.</p></body></html>"""


def summary_pdf(result, view, content, figures, *, font_family=None):
    from PIL import Image as PILImage
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    stream = io.BytesIO()
    doc = SimpleDocTemplate(stream, pagesize=A4, rightMargin=40, leftMargin=40, topMargin=35, bottomMargin=35)
    import hashlib
    from pathlib import Path

    from matplotlib import font_manager
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    report_fonts = {}
    for name, weight in [("ReportSerif", "normal"), ("ReportSerifBold", "bold")]:
        path = font_manager.findfont(
            font_manager.FontProperties(family=font_family or ["Times New Roman", "DejaVu Serif"], weight=weight)
        )
        unique_name = name + "_" + hashlib.sha256(Path(path).read_bytes()).hexdigest()[:12]
        report_fonts[weight] = unique_name
        if unique_name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(unique_name, path))
    body = ParagraphStyle("body", fontName=report_fonts["normal"], fontSize=10, leading=15, spaceAfter=7)
    title = ParagraphStyle("title", parent=body, fontName=report_fonts["bold"], fontSize=12, leading=18)
    caption = ParagraphStyle("caption", parent=body, fontSize=9, leading=12)
    footer = Paragraph(
        "Input: "
        + escape(result.settings.get("input_name", "table"))
        + ". Full tables, provenance and configuration: extended bundle.",
        caption,
    )
    _, footer_height = footer.wrap(doc.width, A4[1])
    doc.bottomMargin = 24 + footer_height + 8
    doc.height = A4[1] - doc.topMargin - doc.bottomMargin

    def page_footer(canvas, document):
        canvas.saveState()
        footer.drawOn(canvas, document.leftMargin, 24)
        canvas.restoreState()

    story = [
        Paragraph(escape(content["question"]), title),
        Paragraph(escape(result.title) + " | Version " + escape(result.settings.get("software_version", "")), body),
        Paragraph(
            "Execution completed. " + escape(content["evidence"]) + ". Units: " + escape(content["unit"]) + ".", body
        ),
    ]
    metrics = [
        [Paragraph(escape(n), caption) for n, _ in content["cards"]],
        [Paragraph(escape(_fmt(v)), title) for _, v in content["cards"]],
    ]
    table = Table(metrics, colWidths=[doc.width / len(metrics[0])] * len(metrics[0]))
    table.setStyle(
        TableStyle(
            [
                ("LINEABOVE", (0, 0), (-1, 0), 0.6, colors.black),
                ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.black),
                ("LINEBELOW", (0, -1), (-1, -1), 0.6, colors.black),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ]
        )
    )
    story += [
        table,
        Spacer(1, 8),
        Paragraph(escape(content["statement"]), body),
        Paragraph(escape(content["caveat"]), body),
    ]
    for item in figures:
        picture = PILImage.open(io.BytesIO(item["png"]))
        ratio = picture.height / picture.width
        width = min(doc.width, 200 / ratio)
        height = width * ratio
        story.append(
            KeepTogether(
                [
                    Image(io.BytesIO(item["png"]), width=width, height=height),
                    Paragraph(escape(item["caption"]), caption),
                ]
            )
        )
    doc.build(story, onFirstPage=page_footer, onLaterPages=page_footer)
    return stream.getvalue()
