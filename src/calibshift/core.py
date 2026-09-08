"""Leave-formulation-out calibration transfer with explicit standard budgets."""

import numpy as np
import pandas as pd

from .common import (
    BlockPLS,
    InputError,
    Result,
    audit,
    fingerprint,
    identifiers,
    metrics,
    numbers,
    tune_pls,
)
from .contract import analysis_contract


def choose_standards(source_rows, paired_groups, budget, group="group", target="target"):
    candidates = source_rows[source_rows[group].isin(paired_groups)].sort_values([target, group])
    if budget <= 0:
        return []
    if len(candidates) < budget:
        return None
    positions = np.rint(np.linspace(0, len(candidates) - 1, budget)).astype(int)
    return candidates.iloc[positions][group].tolist()


@analysis_contract
def analyse(
    frame,
    target="target",
    id_col="sample_id",
    group_col="group",
    domain_col="domain",
    source="X1",
    destinations=None,
    feature_columns=None,
    budgets=(2, 4),
    reference_atol=0.0,
    reference_rtol=1e-8,
):
    _, groups = identifiers(frame, id_col, group_col)
    if not group_col or domain_col not in frame or frame[domain_col].isna().any():
        raise InputError("Provide formulation/specimen IDs and a non-blank acquisition-domain column.")
    if frame[domain_col].astype(str).str.strip().eq("").any():
        raise InputError("Acquisition-domain labels cannot be blank.")
    if source not in set(frame[domain_col].astype(str).str.strip()):
        raise InputError("source: select a domain label observed in the selected acquisition-domain column.")
    features = (
        feature_columns
        if feature_columns is not None
        else [c for c in frame if "__" in c and c not in {target, id_col, group_col, domain_col}]
    )
    if not features or set(features) & {target, id_col, group_col, domain_col}:
        raise InputError("Choose spectral feature columns; identifiers, domains and responses must be excluded.")
    if any(type(b) is not int or b < 0 for b in budgets):
        raise InputError("Standard budgets must be nonnegative integers; zero means the unadapted baseline.")
    group_key = "__cs_physical_group__"
    while group_key in frame:
        group_key += "_"
    domain_key = "__cs_domain__"
    while domain_key in frame or domain_key == group_key:
        domain_key += "_"
    numeric = numbers(frame, features)
    result = Result(
        "CalibShift — transfer to changed acquisition conditions",
        {"input_audit": audit(frame)},
        settings={
            "input_sha256": fingerprint(frame),
            "target": target,
            "features": features,
            "source": source,
            "budgets": list(budgets),
            "protocol": "leave one physical formulation out of every fitting/adaptation domain",
        },
    )
    result.notes.extend(
        [
            "Spectra are averaged within each formulation and domain before evaluation. Responses must be consistent within each formulation.",
            "The held-out formulation is absent from source training and target-domain standards. Components are selected by grouped CV within source training.",
            "Standards are selected by evenly spaced source reference values among available training formulations; their held-out target errors are never used for selection.",
            "A budget counts target-condition measurements of known standards, not automatically new laboratory reference assays. No domain-shift uncertainty guarantee is made.",
        ]
    )
    if target not in frame:
        result.status = "audit_only"
        result.notes.append("Measured reference responses are missing; only file quality can be evaluated.")
        return result
    numeric[target] = numbers(frame, [target])[target]
    numeric[group_key] = groups
    numeric[domain_key] = frame[domain_col].astype(str).str.strip().to_numpy()
    spans = numeric.groupby(group_key)[target].agg(lambda x: x.max() - x.min())
    scale_by_group = numeric.groupby(group_key)[target].agg(lambda x: x.abs().max()).fillna(0)
    if (spans.fillna(0) > reference_atol + reference_rtol * scale_by_group).any():
        raise InputError(
            "Reference responses vary within a formulation ID. This paired-standard transfer protocol requires one stable response per physical formulation."
        )
    aggregated = numeric.groupby([group_key, domain_key], sort=True)[features + [target]].mean().reset_index()
    count_key = "acquisitions_averaged"
    while count_key in aggregated:
        count_key += "_"
    linked_key = "reference_linked_from_source"
    while linked_key in aggregated:
        linked_key += "_"
    aggregated[count_key] = numeric.groupby([group_key, domain_key], sort=True).size().to_numpy()
    source_references = aggregated[aggregated[domain_key].eq(str(source)) & aggregated[target].notna()].set_index(
        group_key
    )[target]
    known_reference = aggregated[group_key].map(source_references)
    linked = ~aggregated[domain_key].eq(str(source)) & aggregated[target].isna() & known_reference.notna()
    aggregated[linked_key] = linked
    aggregated.loc[linked, target] = known_reference[linked]
    if linked.any():
        result.notes.append(
            f"{int(linked.sum())} blank target-domain references were linked by formulation ID to the same formulation's recorded source reference. No reference was estimated; this requires an unchanged formulation response across conditions."
        )
    export_names = {}
    occupied = set(aggregated.columns) | {"group", "domain"}
    for column in features + [target]:
        if column in {"group", "domain"}:
            name = "feature::" + column
            while name in occupied:
                name += "_"
            export_names[column] = name
            occupied.add(name)
    result.settings["aggregation_annotations"] = {
        "acquisitions_averaged": count_key,
        "reference_linked_from_source": linked_key,
    }
    result.tables["aggregated_input"] = aggregated.rename(
        columns=export_names | {group_key: "group", domain_key: "domain"}
    )
    result.settings["aggregated_column_mapping"] = export_names
    result.settings["reference_consistency"] = {
        "absolute_tolerance_response_units": reference_atol,
        "relative_tolerance": reference_rtol,
        "definition": "within-formulation span <= atol + rtol * maximum absolute recorded reference",
    }
    src = aggregated[aggregated[domain_key].eq(str(source)) & aggregated[target].notna()].copy()
    src = src[src[features].notna().any(axis=1)]
    if src[group_key].nunique() < 1:
        result.status = "audit_only"
        result.notes.append(
            "No labelled formulation with usable source spectra is available. Choose the source condition or supply a recorded source reference."
        )
        return result
    destinations = sorted(set(aggregated[domain_key]) - {str(source)}) if destinations is None else destinations
    if not destinations or str(source) in destinations or not set(destinations) <= set(aggregated[domain_key]):
        raise InputError("Choose at least one observed target domain distinct from the source domain.")
    target_availability = aggregated[aggregated[domain_key].isin(destinations)][[group_key, domain_key]].copy()
    target_availability["has_spectral_measurement"] = (
        aggregated.loc[target_availability.index, features].notna().any(axis=1)
    )
    target_availability["has_recorded_reference"] = aggregated.loc[target_availability.index, target].notna()
    result.tables["target_availability"] = target_availability.rename(
        columns={group_key: "group", domain_key: "domain"}
    )
    if not target_availability.has_spectral_measurement.all():
        result.status = "partial"
        result.notes.append(
            "Target formulations without any spectral measurement cannot be predicted and are listed in target_availability. Score coverage is conditional on having a usable target spectrum."
        )
    predictions, standards_log, choices = [], [], []
    for destination in destinations:
        tgt = aggregated[aggregated[domain_key].eq(destination)].copy()
        tgt = tgt[tgt[features].notna().any(axis=1)]
        for _, held in tgt.iterrows():
            train = src[src[group_key].ne(held[group_key])]
            if len(train) < 1:
                result.status = "partial"
                choices.append(
                    {
                        "fold": f"{destination}:{held[group_key]}",
                        "status": "No independent source training formulation remains after excluding the held-out identity.",
                    }
                )
                continue
            x, y = train[features].to_numpy(), train[target].to_numpy()
            component = tune_pls([x], y, train[group_key].to_numpy()) if len(train) >= 3 else 1
            fitted = BlockPLS(component).fit([x], y) if len(train) >= 2 else None
            if fitted is not None and fitted.n_components_ == 0:
                fitted = None
            held_prediction = (
                float(fitted.predict([held[features].to_numpy(dtype=float).reshape(1, -1)])[0])
                if fitted is not None
                else None
            )
            if fitted is None:
                result.status = "partial"
            fold_key = f"{destination}:{held[group_key]}"
            choices.append(
                {
                    "fold": fold_key,
                    "held_out_group": held[group_key],
                    "components": component,
                    "source_training_groups": ";".join(train[group_key]),
                }
            )
            common = {
                "fold": fold_key,
                "source": source,
                "destination": destination,
                "group": held[group_key],
                "reference": held[target],
                "evaluation": "held_out_formulation" if pd.notna(held[target]) else "unscored_prediction",
            }
            if fitted is not None:
                predictions.append({**common, "method": "source_pls", "budget": 0, "prediction": held_prediction})
            else:
                choices.append(
                    {
                        "fold": fold_key,
                        "method": "source_pls",
                        "status": "Unavailable: source training has fewer than two units or no predictor/response variation. The source mean is a separate baseline.",
                    }
                )
            predictions.append({**common, "method": "source_mean", "budget": 0, "prediction": float(y.mean())})
            pool = tgt[tgt[group_key].isin(train[group_key]) & tgt[target].notna()]
            for budget in sorted(set(budgets) - {0}):
                selected = choose_standards(train, pool[group_key], budget, group=group_key, target=target)
                if selected is None:
                    choices.append(
                        {"fold": fold_key, "budget": budget, "status": "insufficient paired target standards"}
                    )
                    result.status = "partial"
                    continue
                standard_rows = pool.set_index(group_key).loc[selected]
                standard_prediction = (
                    fitted.predict([standard_rows[features].to_numpy()])
                    if fitted is not None
                    else np.full(budget, np.nan)
                )
                standard_y = standard_rows[target].to_numpy()
                bias = float(np.mean(standard_y - standard_prediction)) if fitted is not None else np.nan
                if fitted is not None:
                    predictions.append(
                        {**common, "method": "bias_correction", "budget": budget, "prediction": held_prediction + bias}
                    )
                else:
                    choices.append(
                        {
                            "fold": fold_key,
                            "budget": budget,
                            "method": "bias_correction",
                            "status": "unavailable: source calibration has no usable spectral fit",
                        }
                    )

                slope, intercept = np.nan, np.nan
                spread = np.max(np.abs(standard_prediction - standard_prediction.mean()))
                if fitted is not None and budget >= 2 and spread > 0:
                    centred_prediction = (standard_prediction - standard_prediction.mean()) / spread
                    y_scale = float(np.max(np.abs(standard_y - standard_y.mean()))) or 1.0
                    slope = float(
                        np.dot(centred_prediction, (standard_y - standard_y.mean()) / y_scale)
                        / np.dot(centred_prediction, centred_prediction)
                        * y_scale
                        / spread
                    )
                    intercept = float(standard_y.mean() - slope * standard_prediction.mean())
                    predictions.append(
                        {
                            **common,
                            "method": "slope_intercept",
                            "budget": budget,
                            "prediction": float(
                                standard_y.mean() + slope * (held_prediction - standard_prediction.mean())
                            ),
                        }
                    )
                else:
                    result.status = "partial"
                    choices.append(
                        {
                            "fold": fold_key,
                            "budget": budget,
                            "method": "slope_intercept",
                            "status": "unavailable: fewer than two standards or constant standard predictions",
                        }
                    )
                # A separate spectral calibration uses exactly the same target-standard IDs.
                # At least four standards permit bounded grouped inner selection; two only support correction.
                if budget >= 4:
                    tx = standard_rows[features].to_numpy()
                    target_components = tune_pls([tx], standard_y, np.array(selected), candidates=(1, 2))
                    target_fit = BlockPLS(target_components).fit([tx], standard_y)
                    target_prediction = float(
                        target_fit.predict([held[features].to_numpy(dtype=float).reshape(1, -1)])[0]
                    )
                    if target_fit.n_components_ > 0:
                        predictions.append(
                            {
                                **common,
                                "method": "target_recalibration",
                                "budget": budget,
                                "prediction": target_prediction,
                            }
                        )
                    else:
                        result.status = "partial"
                        choices.append(
                            {
                                "fold": fold_key,
                                "budget": budget,
                                "method": "target_recalibration",
                                "status": "unavailable: target-standard predictors or response have no usable variation",
                            }
                        )

                    choices.append(
                        {
                            "fold": fold_key,
                            "budget": budget,
                            "method": "target_recalibration",
                            "components": target_components,
                            "training_standard_groups": ";".join(selected),
                            "status": "fitted on selected target standards only"
                            if target_fit.n_components_ > 0
                            else "no spectral fit; mean fallback not scored as target recalibration",
                        }
                    )
                else:
                    choices.append(
                        {
                            "fold": fold_key,
                            "budget": budget,
                            "method": "target_recalibration",
                            "status": "not estimable: requires at least four selected standards for bounded tuning",
                        }
                    )
                for group_id, before, ref in zip(selected, standard_prediction, standard_y):
                    standards_log.append(
                        {
                            "fold": fold_key,
                            "budget": budget,
                            "standard_group": group_id,
                            "source_prediction_on_target": before,
                            "reference": ref,
                            "bias_adjustment": bias,
                            "slope": slope,
                            "intercept": intercept,
                        }
                    )
    pred = pd.DataFrame(predictions)
    if pred.empty:
        result.status = "audit_only"
        result.notes.append("No target spectra could be evaluated.")
        return result
    pred["residual"] = pred.prediction - pred.reference
    score_rows = []
    pred["in_common_cohort"] = False
    for destination, domain_predictions in pred.groupby("destination", sort=True):
        baseline = domain_predictions[domain_predictions.method.eq("source_mean")].set_index("group")
        scored_groups = set(baseline.index[baseline.reference.notna()])
        method_parts = list(domain_predictions.groupby(["method", "budget"], sort=True))
        common_groups = scored_groups.copy()
        for _, part in method_parts:
            common_groups &= set(part.loc[part.reference.notna() & part.prediction.notna(), "group"])
        pred.loc[domain_predictions.index, "in_common_cohort"] = domain_predictions.group.isin(common_groups)
        for (method, budget), part in method_parts:
            aligned = part.set_index("group").reindex(baseline.index)
            for cohort, selected_groups in [
                ("all_available_rows", scored_groups),
                ("common_scored_rows", common_groups),
            ]:
                index = [g for g in baseline.index if g in selected_groups]
                score_rows.append(
                    {
                        "destination": destination,
                        "method": method,
                        "budget": budget,
                        "cohort": cohort,
                        **metrics(baseline.loc[index, "reference"], aligned.loc[index, "prediction"], np.array(index)),
                    }
                )
    result.tables.update(
        predictions=pred,
        scores=pd.DataFrame(score_rows),
        standards=pd.DataFrame(standards_log),
        splits=pd.DataFrame(choices),
    )
    result.settings["destinations"] = destinations
    result.settings["method_availability"] = (
        "Target spectral recalibration is evaluated only for budgets >=4. Smaller budgets support correction only; unavailable choices are recorded in splits.csv."
    )
    result.settings.update(n_rows=len(frame), n_groups=int(aggregated[group_key].nunique()))
    if pred.reference.isna().any():
        result.status = "partial"
        result.notes.append(
            "Some target formulations have no recorded reference in either the source or target domain. Their predictions are unscored."
        )
    result.notes.append(
        "Compare budgets on the same reported held-out formulation set. Different available standards can change coverage; correction can worsen performance."
    )
    return result
