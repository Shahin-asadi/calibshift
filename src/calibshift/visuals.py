"""Publication exports from traceable diagnostic tables; no model fitting here."""

import math
import textwrap

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap

STYLE = {
    "font.family": "serif",
    "font.serif": ["Times New Roman", "DejaVu Serif"],
    "font.size": 10,
    "axes.titlesize": 12,
    "axes.titleweight": "bold",
    "axes.labelsize": 10,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.linewidth": 0.8,
    "xtick.direction": "out",
    "ytick.direction": "out",
    "legend.frameon": False,
    "figure.facecolor": "white",
    "savefig.facecolor": "white",
    "pdf.fonttype": 42,
}
COLORS = ["#17466b", "#176b63", "#7a263a", "#a36b24", "#62507a", "#4c5966", "#262626"]
MARKERS = ["o", "s", "^", "D", "v", "P", "X"]
DIVERGING = LinearSegmentedColormap.from_list("signed_residual", ["#17466b", "#fafafa", "#7a263a"])


def label(key):
    names = {
        "early_pls": "Early fusion (PLS)",
        "late_equal": "Late fusion: equal",
        "late_weighted": "Late fusion: trained",
        "late_inverse_rmse": "Late fusion: inverse RMSE",
        "training_mean": "Training mean",
        "source_pls": "Source calibration",
        "source_mean": "Source mean",
        "bias_correction": "Bias correction",
        "slope_intercept": "Slope/intercept",
        "target_recalibration": "Target recalibration",
        "prediction": "Prediction",
    }
    return names.get(str(key), str(key).replace("single_", "Single block: "))


def target_label(result, response=None):
    name = response or result.settings.get("target", "response")
    item = result.settings.get("columns", {}).get(name, {})
    return f"{item.get('label', name)} ({item.get('unit', 'unit not supplied')})"


def wrapped(value, width=25):
    return textwrap.fill(str(value), width)


def series_table(frame):
    data = frame.copy()
    method = "model" if "model" in data else "method" if "method" in data else None
    data["series"] = data[method].map(label) if method else "Prediction"
    if "budget" in data:
        data["series"] += data.budget.map(lambda x: f" (k={int(x)})")
    return data


def panel_grid(count, width=10.8, height=3.3, columns=2):
    rows = math.ceil(count / columns)
    fig, axes = plt.subplots(rows, columns, figsize=(width, height * rows), squeeze=False, layout="constrained")
    for ax in axes.flat[count:]:
        ax.set_axis_off()
    return fig, list(axes.flat[:count])


def overview(result):
    """Error and coverage on aligned method axes, separated by acquisition domain."""
    scores = result.tables.get("scores", pd.DataFrame())
    if (
        scores.empty
        or "cohort" not in scores
        or not scores.loc[scores.cohort.eq("common_scored_rows"), "group_rmse"].notna().any()
    ):
        return None
    scores = series_table(scores)
    domains = list(scores.destination.unique()) if "destination" in scores else [None]
    with plt.rc_context(STYLE):
        fig, axes = plt.subplots(
            len(domains),
            2,
            figsize=(11, max(4.4, 4.1 * len(domains))),
            squeeze=False,
            layout="constrained",
            gridspec_kw={"width_ratios": [2.7, 1]},
        )
        for d, domain in enumerate(domains):
            part = scores[scores.destination.eq(domain)] if domain is not None else scores
            common = part[part.cohort.eq("common_scored_rows")].reset_index(drop=True)
            available = part[part.cohort.eq("all_available_rows")].set_index("series")
            positions = np.arange(len(common))
            axis, coverage = axes[d]
            axis.barh(positions, common.group_rmse, color=COLORS[0], height=0.6)
            axis.set_yticks(positions, [wrapped(s, 29) for s in common.series])
            axis.invert_yaxis()
            maximum = common.group_rmse.max()
            axis.set_xlim(0, maximum * 1.25 if pd.notna(maximum) and maximum > 0 else 1)
            for y, row in enumerate(common.itertuples()):
                if pd.notna(row.group_rmse):
                    axis.text(row.group_rmse, y, f"  {row.group_rmse:.3g}", va="center", fontsize=9)
            prefix = f"{domain}: " if domain is not None else ""
            axis.set(title=prefix + "Common-cohort prediction error", xlabel="Group RMSE: " + target_label(result))
            coverage.barh(
                positions,
                [available.loc[s, "coverage"] for s in common.series],
                color="0.65",
                edgecolor="0.25",
                height=0.6,
            )
            coverage.set(
                yticks=positions,
                yticklabels=[],
                xlim=(0, 1.18),
                xticks=[0, 0.5, 1],
                xticklabels=["0%", "50%", "100%"],
                title="Usable coverage",
            )
            coverage.invert_yaxis()
            for y, row in enumerate(common.itertuples()):
                c = available.loc[row.series]
                coverage.text(c.coverage, y, f" {int(c.n)} rows", va="center", fontsize=8)
            coverage.set_xlabel("Available scored rows / labelled rows")
            if not common.group_rmse.notna().any():
                axis.text(0.5, 0.5, "Common comparison unavailable", ha="center", transform=axis.transAxes)
        return fig


def figures(result):
    """Yield (safe filename stem, title, caption, Matplotlib figure)."""
    with plt.rc_context(STYLE):
        yield from _figures(result)


def _figures(result):
    slug = result.settings["application"]
    prediction = result.tables.get("predictions", pd.DataFrame())
    finite = prediction.dropna(subset=["reference", "prediction"]) if not prediction.empty else prediction
    if not finite.empty and slug in {"sensefusion", "calibshift"}:
        parts = finite.groupby("destination", sort=True) if "destination" in finite else [(None, finite)]
        for index, (domain, part) in enumerate(parts, 1):
            data = series_table(part)
            names = data.series.unique().tolist()
            fig, axes = panel_grid(len(names))
            low = min(data.reference.min(), data.prediction.min())
            high = max(data.reference.max(), data.prediction.max())
            pad = (high - low) * 0.06 if high > low else max(abs(low) * 0.05, 1)
            for j, (ax, name) in enumerate(zip(axes, names)):
                group = data[data.series.eq(name)]
                ax.scatter(
                    group.reference,
                    group.prediction,
                    s=27,
                    marker=MARKERS[j % 7],
                    facecolors="none",
                    edgecolors=COLORS[j % 7],
                    alpha=0.75,
                )
                ax.plot([low - pad, high + pad], [low - pad, high + pad], "--", color=".35", lw=0.9)
                ax.set(
                    xlim=(low - pad, high + pad),
                    ylim=(low - pad, high + pad),
                    xlabel="Measured reference",
                    ylabel="Held-out prediction",
                    title=f"{chr(65 + j)}  {name}",
                )
                ax.text(
                    0.04,
                    0.96,
                    f"{len(group)} rows / {group.group.nunique()} groups",
                    transform=ax.transAxes,
                    va="top",
                    fontsize=8,
                )
                if len(group) <= 9:
                    extremes = group.assign(absolute_error=(group.prediction - group.reference).abs()).nlargest(
                        2, "absolute_error"
                    )
                    for position, row in enumerate(extremes.itertuples()):
                        ax.annotate(
                            str(row.group),
                            (row.reference, row.prediction),
                            xytext=(8, 14 if position == 0 else -17),
                            textcoords="offset points",
                            fontsize=7,
                            arrowprops={"arrowstyle": "-", "lw": 0.5, "color": ".4"},
                        )
                unit = (
                    result.settings.get("columns", {})
                    .get(result.settings.get("target"), {})
                    .get("unit", "unit not supplied")
                )
                ax.set_xlabel("Reference (" + unit + ")")
                ax.set_ylabel("Prediction (" + unit + ")")
            title = "Prediction diagnostics" + (f" - {domain}" if domain is not None else "")
            yield (
                f"diagnostic_prediction_{index}",
                title,
                f"{title}. {target_label(result)}. Identical axes across methods; each point is a scored observation. Dashed line is identity. For nine or fewer rows, the two largest absolute errors are labelled; all identifiers remain in predictions.csv. No fit line, replicate uncertainty or additional validation is implied.",
                fig,
            )

    group = result.tables.get("group_diagnostics", pd.DataFrame())
    if not group.empty and slug != "matcheddoe":
        data = series_table(group)
        parts = data.groupby("destination", sort=True) if "destination" in data else [(None, data)]
        for index, (domain, part) in enumerate(parts, 1):
            matrix = part.pivot(index="series", columns="group", values="bias")
            matrix = matrix.iloc[:, :30]
            limit = np.nanmax(np.abs(matrix.to_numpy())) or 1
            fig, ax = plt.subplots(
                figsize=(max(8.5, 0.3 * len(matrix.columns) + 4), max(3.6, 0.43 * len(matrix) + 1.5)),
                layout="constrained",
            )
            plot = ax.imshow(matrix, aspect="auto", cmap=DIVERGING, vmin=-limit, vmax=limit)
            ax.set(
                yticks=np.arange(len(matrix)),
                yticklabels=[wrapped(s, 29) for s in matrix.index],
                xticks=np.arange(len(matrix.columns)),
                xticklabels=matrix.columns.astype(str),
                xlabel="Physical group",
                title="Mean signed residual by physical group" + (f" - {domain}" if domain else ""),
            )
            ax.tick_params(axis="x", labelrotation=60, labelsize=8)
            if matrix.size <= 100:
                for (i, j), value in np.ndenumerate(matrix.to_numpy()):
                    if np.isfinite(value):
                        ax.text(
                            j,
                            i,
                            f"{value:.2g}",
                            ha="center",
                            va="center",
                            fontsize=7,
                            color="white" if abs(value) > 0.6 * limit else "black",
                        )
            fig.colorbar(plot, ax=ax, label="Prediction minus reference (response units)", shrink=0.8)
            yield (
                f"diagnostic_group_residuals_{index}",
                "Group residual map" + (f" - {domain}" if domain else ""),
                "Mean signed errors per physical group. Positive means overprediction; the symmetric scale is centred at zero. The first 30 sorted groups are shown when necessary; group_diagnostics.csv retains every group. Group means can hide within-group variation.",
                fig,
            )

    ranges = result.tables.get("reference_range_diagnostics", pd.DataFrame())
    if not ranges.empty and slug != "matcheddoe":
        data = series_table(ranges)
        parts = data.groupby("destination", sort=True) if "destination" in data else [(None, data)]
        for index, (domain, part) in enumerate(parts, 1):
            fig, axes = plt.subplots(1, 2, figsize=(11, 4.6), layout="constrained")
            for j, (name, series) in enumerate(part.groupby("series", sort=False)):
                series = series.sort_values("reference_bin")
                for ax, column in zip(axes, ["group_rmse", "bias"]):
                    ax.scatter(
                        series.reference_mean,
                        series[column],
                        marker=MARKERS[j % 7],
                        color=COLORS[j % 7],
                        s=42,
                        label=name,
                    )
            axes[0].set(title="A  Error across the reference range", ylabel="Group RMSE (response units)")
            axes[0].set_ylim(bottom=0)
            axes[1].set(title="B  Signed error across the reference range", ylabel="Mean residual (response units)")
            axes[1].axhline(0, color=".4", ls="--", lw=0.8)
            for ax in axes:
                ax.set_xlabel("Mean reference within bin")
            axes[0].legend(fontsize=7, loc="upper left", bbox_to_anchor=(0, -0.2), ncols=2)
            yield (
                f"diagnostic_reference_range_{index}",
                "Reference-range diagnostics" + (f" - {domain}" if domain else ""),
                "Up to four shared quantile bins are used after prediction, for diagnosis only. Dots are bin summaries, not a fitted trend. Bin and physical-group counts are in reference_range_diagnostics.csv; sparse bins do not establish a stable error profile.",
                fig,
            )

    if slug == "sensefusion":
        choices = result.tables.get("fitted_choices", pd.DataFrame())
        if not choices.empty:
            choices = choices[choices.fold.astype(str).ne("unscored_full_fit")]
            fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.2), layout="constrained")
            for ax, column, title in zip(
                axes, ["weight", "inverse_rmse_weight"], ["A  Trained convex weights", "B  Inverse-RMSE weights"]
            ):
                matrix = choices.pivot(index="block", columns="fold", values=column)
                m = ax.imshow(matrix, vmin=0, vmax=1, cmap="Greys", aspect="auto")
                ax.set(
                    xticks=np.arange(len(matrix.columns)),
                    xticklabels=matrix.columns.astype(str),
                    yticks=np.arange(len(matrix)),
                    yticklabels=matrix.index,
                    title=title,
                    xlabel="Outer training fold",
                )
                for (i, j), value in np.ndenumerate(matrix.to_numpy()):
                    ax.text(
                        j,
                        i,
                        f"{value:.2f}",
                        ha="center",
                        va="center",
                        color="white" if value > 0.55 else "black",
                        fontsize=9,
                    )
            fig.colorbar(m, ax=list(axes), label="Block weight", shrink=0.7)
            yield (
                "diagnostic_fusion_weights",
                "Fusion weight stability",
                "Each cell is a weight learned using only that outer fold's training data and nested out-of-fold predictions. Folds are categorical. Variation is descriptive; weights are not causal sensor importance. Exact components and fallbacks remain in fitted_choices.csv.",
                fig,
            )

    if slug == "calibshift":
        table = result.tables.get("standard_range_diagnostics", pd.DataFrame())
        if not table.empty:
            domains = table.destination.unique()
            fig, axes = panel_grid(len(domains), height=4.4, columns=1)
            for ax, domain in zip(axes, domains):
                part = table[table.destination.eq(domain)].head(30).reset_index(drop=True)
                for i, row in enumerate(part.itertuples()):
                    ax.plot([row.standard_reference_min, row.standard_reference_max], [i, i], color=".65", lw=3)
                    ax.scatter(
                        row.held_out_reference,
                        i,
                        marker="s" if row.outside_standard_reference_range else "o",
                        s=36,
                        color=COLORS[2] if row.outside_standard_reference_range else COLORS[0],
                        zorder=3,
                    )
                ax.set(
                    yticks=np.arange(len(part)),
                    yticklabels=[f"{r.held_out_group} / k={r.budget}" for r in part.itertuples()],
                    xlabel=target_label(result),
                    title=f"{domain}: held-out reference and selected-standard range",
                )
                ax.invert_yaxis()
            yield (
                "diagnostic_standard_ranges",
                "Selected-standard coverage",
                "Horizontal intervals span the selected standards' references; dots mark the held-out reference and squares flag extrapolation beyond that range. This retrospective check never influences fitting or selection. First 30 rows per condition are displayed; complete table: standard_range_diagnostics.csv.",
                fig,
            )

    if slug == "matcheddoe":
        coefficients = result.tables.get("coefficients", pd.DataFrame())
        responses = result.settings.get("responses", [])
        if not coefficients.empty:
            fig, axes = panel_grid(len(responses), columns=1, height=3.9)
            for ax, response in zip(axes, responses):
                part = coefficients[coefficients.response.eq(response) & coefficients.term.ne("Intercept")].reset_index(
                    drop=True
                )
                for i, row in enumerate(part.itertuples()):
                    if pd.notna(row.ci95_low):
                        ax.plot([row.ci95_low, row.ci95_high], [i, i], color=COLORS[2], lw=1.5)
                    ax.scatter(row.coefficient_coded, i, color=COLORS[2], s=32)
                ax.axvline(0, color=".4", ls="--", lw=0.8)
                ax.set(
                    yticks=np.arange(len(part)),
                    yticklabels=part.term,
                    title="Coded coefficients: " + response,
                    xlabel="Coefficient (response units per coded term)",
                )
                ax.invert_yaxis()
            yield (
                "diagnostic_coefficients",
                "Coded coefficient estimates",
                "Dots show coefficients for non-intercept terms. Lines are the existing pointwise 95% coefficient intervals where estimable and independence was declared. An absent interval is not zero uncertainty. Full coefficients, including intercept, are retained in coefficients.csv.",
                fig,
            )
        candidates = result.tables.get("candidates", pd.DataFrame())
        coding = result.tables.get("factor_coding", pd.DataFrame())
        factors = result.settings.get("factors", [])
        if not candidates.empty and len(factors) >= 2:
            for index, response in enumerate(responses, 1):
                subset = candidates.copy()
                slice_note = ""
                if len(factors) == 3:
                    third = factors[2]
                    third_column = result.settings["candidate_columns"]["factors"][third]
                    centre = float(coding.loc[coding.factor.eq(third), "centre"].iloc[0])
                    level = subset[third_column].unique()[np.argmin(np.abs(subset[third_column].unique() - centre))]
                    subset = subset[subset[third_column].eq(level)]
                    slice_note = f"; {third} fixed at {level:.6g}"
                table = (
                    subset.pivot(
                        index=result.settings["candidate_columns"]["factors"][factors[1]],
                        columns=result.settings["candidate_columns"]["factors"][factors[0]],
                        values=result.settings["candidate_columns"]["predictions"][response],
                    )
                    .sort_index()
                    .sort_index(axis=1)
                )
                fig, ax = plt.subplots(figsize=(7.8, 5.5), layout="constrained")
                p = ax.pcolormesh(
                    table.columns.to_numpy(),
                    table.index.to_numpy(),
                    np.ma.masked_invalid(table.to_numpy()),
                    shading="nearest",
                    cmap="cividis",
                )
                ax.set(
                    xlabel=target_label(result, factors[0]),
                    ylabel=target_label(result, factors[1]),
                    title="Supported fitted surface: " + response,
                )
                observed = result.tables.get("observed_factor_values", pd.DataFrame())
                observed_count = 0
                if not observed.empty:
                    coords = observed.pivot(index="sample_id", columns="factor", values="value")
                    if len(factors) == 3:
                        coords = coords[np.isclose(coords[factors[2]], level)]
                    if len(coords):
                        ax.scatter(
                            coords[factors[0]],
                            coords[factors[1]],
                            facecolors="none",
                            edgecolors="white",
                            linewidths=1.0,
                            s=45,
                            label="Observed settings in this plane",
                        )
                        observed_count = len(coords)
                        ax.legend(loc="best", fontsize=8)
                fig.colorbar(p, ax=ax, label=target_label(result, response))
                yield (
                    f"diagnostic_surface_{index}",
                    "Supported response surface - " + response,
                    "Fitted values on the common supported grid"
                    + slice_note
                    + f". Open circles mark {observed_count} observed settings in this plane. Blank cells are outside the observed design hull. The pixel boundaries show grid cells; predictions are defined at the grid centres. No independent confirmation or continuous optimum is implied.",
                    fig,
                )
        influence = result.tables.get("influence_diagnostics", pd.DataFrame())
        if not influence.empty:
            fig, axes = panel_grid(len(responses), columns=1, height=3.8)
            for ax, response in zip(axes, responses):
                part = influence[influence.response.eq(response)]
                if part.cooks_distance.notna().any():
                    ax.vlines(np.arange(len(part)), 0, part.cooks_distance, color=".65")
                    ax.scatter(np.arange(len(part)), part.cooks_distance, color=COLORS[2], s=30)
                    ax.axhline(
                        part.reference_cooks_threshold.iloc[0], color=".3", ls="--", label="4/n review reference"
                    )
                    ax.legend(fontsize=8)
                else:
                    ax.text(0.5, 0.5, "Influence variance is not estimable", ha="center", transform=ax.transAxes)
                ax.set(
                    xticks=np.arange(len(part)),
                    xticklabels=part.sample_id.astype(str),
                    ylabel="Cook's distance",
                    title="Run influence: " + response,
                    xlabel="Observed run",
                )
                ax.tick_params(axis="x", labelrotation=55, labelsize=8)
                ax.set_ylim(bottom=0)
            yield (
                "diagnostic_influence",
                "Observed-run influence",
                "Cook's distance measures fitted-model sensitivity under its assumptions. The 4/n line is a screening heuristic only; no observation is automatically removed. Internal studentization and leverage are exported in influence_diagnostics.csv.",
                fig,
            )
        tradeoff = result.tables.get("candidate_tradeoff", pd.DataFrame())
        if not tradeoff.empty:
            first, second = responses
            fig, ax = plt.subplots(figsize=(7.8, 5.5), layout="constrained")
            ax.scatter(
                tradeoff[result.settings["candidate_columns"]["predictions"][first]],
                tradeoff[result.settings["candidate_columns"]["predictions"][second]],
                s=10,
                color=".65",
                alpha=0.5,
                label="Supported grid",
            )
            frontier = tradeoff[tradeoff.nondominated]
            ax.scatter(
                frontier[result.settings["candidate_columns"]["predictions"][first]],
                frontier[result.settings["candidate_columns"]["predictions"][second]],
                s=46,
                facecolors="none",
                edgecolors=COLORS[2],
                lw=1.1,
                label="Nondominated candidates",
            )
            ax.set(
                xlabel="Fitted " + target_label(result, first),
                ylabel="Fitted " + target_label(result, second),
                title="Two-response candidate tradeoff",
            )
            ax.legend(fontsize=9)
            yield (
                "diagnostic_tradeoff",
                "Two-response tradeoff",
                f"{len(frontier)} of {len(tradeoff)} supported grid candidates are nondominated for the declared directions. The open circles identify predicted tradeoffs, not a joint optimum or independent confirmation. All candidate conditions remain in candidate_tradeoff.csv.",
                fig,
            )

    if slug == "assayreport":
        pairs = result.tables.get("agreement_pairs", pd.DataFrame())
        limits = result.tables.get("agreement_summary", pd.DataFrame())
        if not pairs.empty:
            fig, axes = plt.subplots(1, 2, figsize=(11, 4.6), layout="constrained")
            axes[0].scatter(
                pairs.mean_of_pair, pairs.difference, s=40, color=COLORS[2], marker="o", edgecolors="white", lw=0.4
            )
            if not limits.empty and "bias" in limits:
                for key, line in [("bias", "-"), ("loa95_low", "--"), ("loa95_high", "--")]:
                    if key not in limits or pd.isna(limits.iloc[0][key]):
                        continue
                    value = limits.iloc[0][key]
                    axes[0].axhline(value, color=".3", ls=line, lw=1, label=f"{key.replace('_', ' ')}: {value:.3g}")
                axes[0].legend(fontsize=8, loc="best")
            axes[0].set(
                title="A  Agreement: " + result.settings.get("agreement_unit", "specimen_mean").replace("_", " "),
                xlabel="Mean of reference and prediction",
                ylabel="Prediction minus reference",
            )
            if len(pairs) >= 8:
                axes[1].hist(
                    pairs.difference, bins=min(10, max(4, int(np.sqrt(len(pairs))))), color=".7", edgecolor="white"
                )
                axes[1].set_ylabel("Agreement units")
            else:
                axes[1].scatter(pairs.difference, np.arange(len(pairs)), color=COLORS[2])
                axes[1].set(
                    yticks=np.arange(len(pairs)),
                    yticklabels=pairs.group.astype(str),
                    ylabel="Agreement unit / specimen ID",
                )
            axes[1].axvline(0, color=".3", ls="--", lw=0.8)
            axes[1].set(title="B  Distribution of differences", xlabel="Prediction minus reference")
            yield (
                "diagnostic_agreement",
                "Agreement and difference distribution",
                f"{len(pairs)} agreement units: {result.settings.get('agreement_unit', 'specimen_mean')}. Response units: {target_label(result)}. Normal-difference limits, when available, describe that declared estimand and do not establish interchangeability. No confidence intervals are added to out-of-fold predictions.",
                fig,
            )

    quality = result.tables.get("feature_quality", pd.DataFrame())
    if not quality.empty:
        part = quality.head(12)
        matrix = result.tables["feature_correlation_preview"].set_index(
            result.settings.get("feature_correlation_schema", {}).get("row_name_column", "feature")
        )
        fig, axes = plt.subplots(1, 2, figsize=(11, 5.3), layout="constrained")
        axes[0].barh(np.arange(len(part)), part.missing_fraction, color=".55", edgecolor=".25", height=0.6)
        axes[0].set(
            yticks=np.arange(len(part)),
            yticklabels=[wrapped(c, 22) for c in part.feature],
            xlim=(0, 1),
            xlabel="Missing fraction",
            title="A  Measurement availability",
        )
        axes[0].invert_yaxis()
        m = axes[1].imshow(matrix, vmin=-1, vmax=1, cmap=DIVERGING)
        axes[1].set(
            xticks=np.arange(len(matrix)),
            yticks=np.arange(len(matrix)),
            xticklabels=range(1, len(matrix) + 1),
            yticklabels=range(1, len(matrix) + 1),
            title="B  Feature correlation",
            xlabel="Feature index (input order)",
            ylabel="Feature index (input order)",
        )
        fig.colorbar(m, ax=axes[1], label="Pearson r", shrink=0.75)
        yield (
            "diagnostic_feature_audit",
            "Feature availability and association",
            "First 12 selected features in input order, without choosing them for apparent association. Correlations use available row pairs, with at least three pairs; blank cells are unavailable. Repeated observations can drive associations. Full availability statistics and preview feature names are exported; this view does not select model features.",
            fig,
        )
