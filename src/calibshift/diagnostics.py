"""Descriptive diagnostics computed after fitting; never used for model selection."""

import numpy as np
import pandas as pd

from .common import metrics, numbers


def pareto_minima(values):
    """Exact two-objective nondominance, retaining ties, without a quadratic matrix."""
    values = np.asarray(values, float)
    if values.ndim != 2 or values.shape[1] != 2 or not np.isfinite(values).all():
        raise ValueError("Two finite objectives are required.")
    order = np.lexsort((values[:, 1], values[:, 0]))
    keep = np.zeros(len(values), dtype=bool)
    best_second = np.inf
    best_first = np.inf
    for index in order:
        first, second = values[index]
        if second < best_second or (second == best_second and first == best_first):
            keep[index] = True
            best_second, best_first = second, first
    return keep


def augment(result, frame):
    """Add review tables using the already-computed predictions and original input.

    These tables do not tune, refit, discard outliers, or infer additional
    independent observations. Bins, influence flags and pairwise differences
    are diagnostic descriptions, not confirmatory hypothesis tests.
    """
    params = result.settings.get("call_parameters", {})
    slug = result.settings["application"]
    manifest = []

    def add(name, table, question, interpretation):
        result.tables[name] = table
        manifest.append({"table": name, "question": question, "interpretation": interpretation, "rows": len(table)})

    features = params.get("feature_columns") or [
        c for columns in (params.get("block_columns") or {}).values() for c in columns
    ]
    if features:
        quality = []
        for column in features:
            values = numbers(frame, [column])[column].dropna()
            quality.append(
                {
                    "feature": column,
                    "observed_rows": len(values),
                    "missing_fraction": 1 - len(values) / len(frame),
                    "minimum": values.min(),
                    "median": values.median(),
                    "maximum": values.max(),
                    "distinct_values": values.nunique(),
                }
            )
        add(
            "feature_quality",
            pd.DataFrame(quality),
            "Which measurement columns are incomplete or constant?",
            "Input-only descriptive audit; no feature is selected or removed using these summaries.",
        )
        preview = features[:12]
        correlation = numbers(frame, preview).corr(min_periods=3)
        row_label = "feature"
        while row_label in correlation.columns:
            row_label = "_" + row_label
        correlation.index.name = row_label
        result.settings["feature_correlation_schema"] = {
            "row_name_column": row_label,
            "measurement_columns": preview,
            "source_names_preserved": True,
        }
        add(
            "feature_correlation_preview",
            correlation.reset_index(),
            "Are measurement features redundant?",
            "Pearson correlations of available row pairs, first 12 selected columns in input order; repeated rows are not independent evidence.",
        )

    prediction = result.tables.get("predictions", pd.DataFrame()).copy()
    if prediction.empty:
        result.settings["diagnostics"] = manifest
        return
    prediction = prediction.dropna(subset=["reference", "prediction"])
    if prediction.empty:
        result.settings["diagnostics"] = manifest
        return
    if "group" not in prediction:
        prediction["group"] = prediction.sample_id
    keys = [k for k in ["destination", "model", "method", "budget", "response"] if k in prediction]
    if not keys:
        prediction["analysis"] = "prediction"
        keys = ["analysis"]
    group_rows = []
    for values, part in prediction.groupby(keys + ["group"], sort=True, dropna=False):
        values = values if isinstance(values, tuple) else (values,)
        score = metrics(part.reference, part.prediction)
        group_rows.append(
            dict(zip(keys + ["group"], values))
            | {
                "n": len(part),
                "reference_mean": part.reference.mean(),
                "prediction_mean": part.prediction.mean(),
                "rmse": score["rmse"],
                "mae": score["mae"],
                "bias": score["bias"],
            }
        )
    add(
        "group_diagnostics",
        pd.DataFrame(group_rows),
        "Which physical groups have the largest errors?",
        "One summary per method and physical group; group means and within-group RMSE are different quantities. No rows are excluded.",
    )

    range_rows = []
    response_keys = ["response"] if "response" in prediction else []
    partitions = prediction.groupby(response_keys[0], sort=True) if response_keys else [(None, prediction)]
    for response, population in partitions:
        unit_id = "sample_id" if "sample_id" in population else "group"
        identity = [c for c in ["destination", unit_id] if c in population]
        reference = population.drop_duplicates(identity).reference.to_numpy(float)
        edges = np.unique(np.quantile(reference, [0, 0.25, 0.5, 0.75, 1]))
        if len(edges) < 2:
            edges = np.array([reference[0], reference[0]])
        bin_index = np.searchsorted(edges[1:-1], population.reference.to_numpy(), side="left")
        population = population.assign(reference_bin=bin_index)
        for values, part in population.groupby(keys + ["reference_bin"], sort=True, dropna=False):
            values = values if isinstance(values, tuple) else (values,)
            code = int(values[-1])
            score = metrics(part.reference, part.prediction, part.group)
            range_rows.append(
                dict(zip(keys + ["reference_bin"], values))
                | {
                    "lower_reference": edges[code],
                    "upper_reference": edges[code + 1],
                    "reference_mean": part.reference.mean(),
                    "n": len(part),
                    "n_groups": part.group.nunique(),
                    "rmse": score["rmse"],
                    "group_rmse": score["group_rmse"],
                    "bias": score["bias"],
                }
            )
    add(
        "reference_range_diagnostics",
        pd.DataFrame(range_rows),
        "Does error vary across the measured response range?",
        "Up to four shared reference-quantile bins, determined after prediction for diagnosis only. Bin counts and group counts are retained; no uncertainty is inferred.",
    )

    if slug in {"sensefusion", "calibshift"}:
        method_col = "model" if slug == "sensefusion" else "method"
        baseline = "training_mean" if slug == "sensefusion" else "source_pls"
        identity = [c for c in ["destination", "sample_id", "group"] if c in prediction]
        base = prediction[prediction[method_col].eq(baseline)][identity + ["prediction"]].rename(
            columns={"prediction": "baseline_prediction"}
        )
        paired = prediction[~prediction[method_col].eq(baseline)].merge(
            base, on=identity, how="inner", validate="many_to_one"
        )
        rows = []
        for values, part in paired.groupby(keys, sort=True, dropna=False):
            values = values if isinstance(values, tuple) else (values,)
            a = metrics(part.reference, part.prediction, part.group)
            b = metrics(part.reference, part.baseline_prediction, part.group)
            rows.append(
                dict(zip(keys, values))
                | {
                    "baseline": baseline,
                    "paired_rows": len(part),
                    "paired_groups": part.group.nunique(),
                    "method_group_rmse": a["group_rmse"],
                    "baseline_group_rmse": b["group_rmse"],
                    "delta_group_rmse": a["group_rmse"] - b["group_rmse"],
                    "interpretation": "negative difference favours the method on this paired subset",
                }
            )
        add(
            "paired_baseline_comparison",
            pd.DataFrame(rows),
            "Does each method improve on its baseline using exactly the same observations?",
            "Descriptive paired comparisons; each method may have a different intersection. Differences do not supply independent confidence intervals or a global ranking.",
        )

    if slug == "calibshift":
        standards = result.tables.get("standards", pd.DataFrame())
        rows = []
        if not standards.empty:
            for (fold, budget), part in standards.groupby(["fold", "budget"], sort=True):
                predictions = result.tables["predictions"]
                held = predictions.loc[predictions.fold.eq(fold)].iloc[0]
                low, high = part.reference.min(), part.reference.max()
                rows.append(
                    {
                        "fold": fold,
                        "destination": held.destination,
                        "budget": budget,
                        "held_out_group": held.group,
                        "standard_reference_min": low,
                        "standard_reference_max": high,
                        "held_out_reference": held.reference,
                        "outside_standard_reference_range": bool(held.reference < low or held.reference > high)
                        if pd.notna(held.reference)
                        else None,
                    }
                )
        add(
            "standard_range_diagnostics",
            pd.DataFrame(rows),
            "Which held-out formulations lie beyond the selected standards' response range?",
            "Retrospective diagnostic uses the held-out reference only after fitting. It never changes standard selection or tuning.",
        )

    if slug == "matcheddoe":
        summaries = result.tables["model_summary"]
        coef = result.tables["coefficients"]
        influence = []
        for response, part in prediction.groupby("response", sort=True):
            summary = summaries[summaries.response.eq(response)].iloc[0]
            n, p = len(part), len(coef[coef.response.eq(response)])
            mse = summary.residual_ss / summary.residual_df if summary.residual_df > 0 else np.nan
            infer = coef[coef.response.eq(response)].standard_error.notna().any() and mse > 0
            for row in part.itertuples():
                denom = 1 - row.leverage
                estimable = infer and denom > 8 * np.finfo(float).eps
                student = row.residual / np.sqrt(mse * denom) if estimable else np.nan
                cook = (row.residual**2 / (p * mse)) * row.leverage / (denom**2) if estimable else np.nan
                influence.append(
                    {
                        "sample_id": row.sample_id,
                        "response": response,
                        "leverage": row.leverage,
                        "internal_studentized_residual": student,
                        "cooks_distance": cook,
                        "reference_cooks_threshold": 4 / n,
                        "exceeds_reference_threshold": bool(cook > 4 / n) if estimable else None,
                        "status": "descriptive influence flag; retain observation"
                        if estimable
                        else "variance or leverage does not support diagnostic",
                    }
                )
        add(
            "influence_diagnostics",
            pd.DataFrame(influence),
            "Are fitted coefficients sensitive to a particular observed run?",
            "Internal studentization and Cook's distance require estimable residual variance and the independence declaration. 4/n is a review heuristic, never an automatic removal rule.",
        )
        candidates = result.tables.get("candidates", pd.DataFrame())
        responses = result.settings["responses"]
        if len(responses) == 2 and not candidates.empty:
            columns = [result.settings["candidate_columns"]["predictions"][r] for r in responses]
            signs = np.array([1 if params["directions"][r] == "minimise" else -1 for r in responses])
            table = candidates.copy()
            table["nondominated"] = pareto_minima(table[columns].to_numpy() * signs)
            add(
                "candidate_tradeoff",
                table,
                "Which supported candidates offer a tradeoff between the two response objectives?",
                "Exact nondominance on the finite common candidate grid, using the declared objective directions. Fitted predictions, not measured confirmation or a continuous optimum.",
            )
    result.settings["diagnostics"] = manifest
