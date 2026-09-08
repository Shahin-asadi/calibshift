"""Explicit information availability, distinct from successful execution."""

import pandas as pd


def describe_capabilities(result):
    tables = result.tables
    rows = []

    def add(name, available, reason, level="descriptive"):
        rows.append({"capability": name, "available": bool(available), "level": level, "reason": reason})

    add("input_quality", "input_audit" in tables, "Parsed rows and selected field availability are retained.")
    prediction = tables.get("predictions", pd.DataFrame())
    paired = (
        prediction.dropna(subset=["reference", "prediction"])
        if {"reference", "prediction"} <= set(prediction)
        else pd.DataFrame()
    )
    add(
        "paired_descriptions",
        not paired.empty,
        "Available finite reference/comparison pairs; no missing reference is invented."
        if not paired.empty
        else "No usable finite reference/comparison pairs.",
    )
    add(
        "fitted_model",
        "coefficients" in tables and not tables["coefficients"].empty,
        "Rank-supported coefficients are available."
        if "coefficients" in tables and not tables["coefficients"].empty
        else "No estimable requested factor model was fitted.",
        "fitting",
    )
    held = (
        not prediction.empty
        and "fold" in prediction
        and prediction["fold"].map(lambda value: pd.notna(value) and str(value) != "-1").any()
    )
    add(
        "held_out_evaluation",
        held,
        "Recorded disjoint training/held-out units; interpret small samples as exploratory."
        if held
        else "No held-out model evaluation is supported by this run.",
        "evaluation",
    )
    summary = tables.get("model_summary", pd.DataFrame())
    uncertainty = (
        "coefficient_variance_estimable" in summary and summary["coefficient_variance_estimable"].fillna(False).any()
    ) or (
        "coefficients" in tables
        and "standard_error" in tables["coefficients"]
        and tables["coefficients"].standard_error.notna().any()
    )
    agreement = tables.get("agreement_summary", pd.DataFrame())
    uncertainty = uncertainty or any("ci95" in c and agreement[c].notna().any() for c in agreement)
    add(
        "conditional_uncertainty",
        uncertainty,
        "Only the stated estimand and confirmed independence/variance assumptions support these intervals."
        if uncertainty
        else "Required independence, variance, sample structure or prediction provenance is unavailable.",
        "inference",
    )
    rows.extend(result.settings.get("capability_details", []))
    result.settings["capabilities"] = rows
    tables["capabilities"] = pd.DataFrame(rows)
    result.settings["computation_status"] = "completed"
    result.settings["evidence_summary"] = (
        "Input audit; performance unavailable"
        if not len(paired) and "coefficients" not in tables
        else "Exploratory results; selected uncertainty measures unavailable"
        if not uncertainty
        else "Results with conditional uncertainty; review assumptions"
    )
