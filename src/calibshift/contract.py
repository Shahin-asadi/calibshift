"""Typed public configuration and portable run metadata shared by all entry points."""

import hashlib
import inspect
import json
from functools import wraps
from pathlib import Path

import numpy as np
import pandas as pd

from .common import InputError, fingerprint

SCHEMA_VERSION = "1.2"


def string_list(value, field, allow_empty=False):
    if not isinstance(value, (list, tuple)) or any(not isinstance(x, str) or not x.strip() for x in value):
        raise InputError(f"{field}: supply a list of non-blank column names/labels.")
    if not allow_empty and not value:
        raise InputError(f"{field}: select at least one item.")
    if len(set(value)) != len(value):
        raise InputError(f"{field}: duplicate selections are not allowed; select each item once.")
    return list(value)


def real_number(value, field, minimum=0):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not np.isfinite(value) or value < minimum:
        raise InputError(f"{field}: supply a finite number greater than or equal to {minimum}.")
    return value


def validate_config(values, slug):
    for key in ["target", "domain_col", "source"]:
        if key in values and (not isinstance(values[key], str) or not values[key].strip()):
            raise InputError(f"{key}: supply a non-blank column name or domain label.")
    for key in ["id_col", "group_col", "cv_group_col", "prediction_column"]:
        if key in values and values[key] is not None and (not isinstance(values[key], str) or not values[key].strip()):
            raise InputError(f"{key}: supply a non-blank column name or null.")
    for key in ["factors", "responses", "feature_columns", "destinations"]:
        if key in values and values[key] is not None:
            values[key] = string_list(
                values[key], key, allow_empty=(key == "feature_columns" and slug == "assayreport")
            )
    if values.get("block_columns") is not None:
        blocks = values["block_columns"]
        if not isinstance(blocks, dict) or not 1 <= len(blocks) <= 6:
            raise InputError("block_columns: supply an object containing one to six named measurement blocks.")
        for name, columns in blocks.items():
            if not isinstance(name, str) or not name.strip():
                raise InputError("block_columns: each block needs a non-blank name.")
            string_list(columns, f"block_columns.{name}")
    if "independent_runs" in values and type(values["independent_runs"]) is not bool:
        raise InputError("independent_runs: use the JSON Boolean true or false, without quotation marks.")
    if "grid_points" in values and (type(values["grid_points"]) is not int or not 5 <= values["grid_points"] <= 41):
        raise InputError("grid_points: supply an integer from 5 through 41.")
    if "budgets" in values:
        b = values["budgets"]
        if not isinstance(b, (list, tuple)) or any(type(x) is not int or x < 0 for x in b) or len(set(b)) != len(b):
            raise InputError(
                "budgets: use distinct nonnegative integers, for example [0, 2, 4]; an empty list means baseline only. Booleans are not counts."
            )
        values["budgets"] = list(b)
    if "model" in values and values["model"] not in ["linear", "2fi", "additive_quadratic", "quadratic"]:
        raise InputError("model: choose linear, 2fi, additive_quadratic or quadratic.")
    if "prediction_origin" in values and values["prediction_origin"] not in [
        "unknown",
        "independent_holdout",
        "out_of_fold",
        "fitted",
    ]:
        raise InputError("prediction_origin: choose unknown, independent_holdout, out_of_fold or fitted.")
    if values.get("directions") is not None:
        directions = values["directions"]
        if not isinstance(directions, dict) or any(
            k not in (values.get("responses") or ["response"]) or v not in ["minimise", "maximise"]
            for k, v in directions.items()
        ):
            raise InputError("directions: map only selected response names to minimise or maximise.")
    for key in ["reference_atol", "reference_rtol"]:
        if key in values:
            real_number(values[key], key)
    roles = [
        values.get(k)
        for k in ["target", "id_col", "group_col", "domain_col", "prediction_column"]
        if values.get(k) is not None
    ]
    if len(roles) != len(set(roles)):
        raise InputError(
            "Column roles conflict: reference, row ID, group, domain and prediction require separate columns."
        )


def analysis_contract(function):
    signature = inspect.signature(function)
    slug = function.__module__.split(".")[0]

    @wraps(function)
    def wrapped(frame, *args, **kwargs):
        metadata = {k: kwargs.pop(k) for k in ["input_name", "column_metadata", "provenance"] if k in kwargs}
        unknown = set(kwargs) - set(signature.parameters)
        if unknown:
            raise InputError("Configuration: unknown field(s): " + ", ".join(sorted(unknown)))
        try:
            bound = signature.bind(frame, *args, **kwargs)
        except TypeError as exc:
            raise InputError(f"Configuration: {exc}") from exc
        bound.apply_defaults()
        values = dict(bound.arguments)
        values.pop("frame")
        validate_config(values, slug)
        if not isinstance(frame, pd.DataFrame) or frame.empty:
            raise InputError("frame: provide a table containing at least one observation.")
        if not all(isinstance(c, str) and c.strip() for c in frame.columns) or frame.columns.duplicated().any():
            raise InputError("frame: column headers must be distinct non-blank strings.")
        original_frame = frame
        frame = frame.copy()
        generated_id = None
        requested_id = values.get("id_col")
        if requested_id is None or (requested_id == "sample_id" and requested_id not in frame):
            generated_id = "__row_id__"
            while generated_id in frame:
                generated_id = "_" + generated_id
            frame[generated_id] = [f"row_{i + 1:08d}" for i in range(len(frame))]
            values["id_col"] = generated_id
        if values.get("group_col") == "group" and "group" not in frame:
            values["group_col"] = None
        label_meta = metadata.get("column_metadata") or {}
        if not isinstance(label_meta, dict):
            raise InputError("column_metadata: supply an object mapping column names to label/unit objects.")
        for column, item in label_meta.items():
            if (
                column not in frame
                or not isinstance(item, dict)
                or set(item) - {"label", "unit"}
                or any(not isinstance(v, str) or not v.strip() for v in item.values())
            ):
                raise InputError("column_metadata: use existing columns with non-blank string label/unit fields.")
        target_unit = label_meta.get(values.get("target"), {}).get("unit")
        prediction_unit = label_meta.get(values.get("prediction_column"), {}).get("unit")
        if target_unit and prediction_unit and target_unit != prediction_unit:
            raise InputError(
                "column_metadata: reference and prediction units differ; convert them to the same declared unit before analysis."
            )
        result = function(frame, **values)
        # Record inferred selections as explicit arguments for repeatable configuration.
        if "block_columns" in values and values["block_columns"] is None:
            values["block_columns"] = result.settings.get("blocks")
        if "feature_columns" in values and values["feature_columns"] is None:
            values["feature_columns"] = result.settings.get("features")
        if "destinations" in values and values["destinations"] is None:
            values["destinations"] = result.settings.get("destinations")
        if "responses" in values and values["responses"] is None:
            values["responses"] = ["response"]
        if "directions" in values and values["directions"] is None:
            values["directions"] = {r: "maximise" for r in values["responses"]}
        input_name = metadata.get("input_name", "in_memory_table")
        if not isinstance(input_name, str):
            raise InputError("input_name: supply a filename, without private directories.")
        input_name = input_name.replace("\\", "/").rsplit("/", 1)[-1]
        provenance = metadata.get("provenance")
        if provenance is None:
            provenance = {
                "kind": "user_provided",
                "attribution": "Supplied by the user; no public-data license is inferred.",
            }
        if not isinstance(provenance, dict) or provenance.get("kind") not in ["bundled_example", "user_provided"]:
            raise InputError("provenance: kind must be bundled_example or user_provided.")
        if provenance["kind"] == "bundled_example":
            example_name = provenance.get("example")
            resource = Path(__file__).with_name("examples") / str(example_name)
            if not resource.is_file() or resource.name != example_name:
                raise InputError("provenance.example: select an exact bundled example filename.")
            from .common import read_table

            if fingerprint(read_table(resource)) != fingerprint(original_frame):
                raise InputError(
                    "provenance: table differs from the named bundled example; identify modified data as user_provided."
                )
            catalog = json.loads(Path(__file__).with_name("provenance.json").read_text(encoding="utf-8"))
            provenance = catalog["examples"][example_name]
        from . import __version__

        values.update(
            column_metadata=label_meta,
            input_name=input_name,
            provenance={"kind": "bundled_example", "example": provenance["example"]}
            if provenance["kind"] == "bundled_example"
            else {"kind": "user_provided"},
        )
        source_digest = hashlib.sha256()
        source_root = Path(__file__).parent
        for source_file in sorted(source_root.rglob("*.py")):
            source_digest.update(source_file.relative_to(source_root).as_posix().encode("utf-8"))
            source_digest.update(b"\x00")
            source_digest.update(source_file.read_bytes())
            source_digest.update(b"\x00")
        protocol = {
            "sensefusion": {"outer_max_folds": 5, "inner_max_folds": 3, "pls_components": [1, 2, 3]},
            "calibshift": {
                "outer_split": "leave one formulation out",
                "inner_max_folds": 3,
                "source_pls_components": [1, 2, 3],
                "target_pls_components": [1, 2],
                "target_recalibration_min_budget": 4,
            },
            "matcheddoe": {
                "evaluation": "in-sample fitted design",
                "candidate_grid_points_per_factor": values.get("grid_points"),
            },
            "assayreport": {
                "outer_max_folds": 5,
                "inner_max_folds": 3,
                "pls_components": [1, 2, 3],
                "external_prediction_origin": values.get("prediction_origin", "not applicable"),
            },
        }[slug]
        result.settings.update(
            software_source_sha256=source_digest.hexdigest(),
            source_hash_definition="SHA256 of sorted relative Python paths and file bytes, each terminated by a NUL byte",
            application=slug,
            software_version=__version__,
            configuration_schema_version=SCHEMA_VERSION,
            call_parameters=values,
            input_name=input_name,
            columns={c: {"label": c, "unit": "not provided", **label_meta.get(c, {})} for c in frame},
            provenance=provenance,
            input_hash_definition="SHA256 of parsed table serialized as canonical CSV; not original file bytes",
            n_input_rows=len(frame),
            computation_status="completed",
            evidence_status=result.status,
            deterministic_protocol=protocol,
        )
        result.settings["input_preparation"] = {
            "generated_row_id": generated_id,
            "row_id_meaning": "Internal row alignment only; not a physical specimen or independence assertion"
            if generated_id
            else "Source observation ID",
            "import": frame.attrs.get("import_info", {}),
            "original_parsed_input_sha256": fingerprint(original_frame),
        }
        if generated_id:
            result.tables["row_mapping"] = pd.DataFrame(
                {
                    "source_row": np.arange(len(frame)) + frame.attrs.get("import_info", {}).get("header_row", 1) + 1,
                    "sample_id": frame[generated_id],
                }
            )
            result.settings["call_parameters"]["id_col"] = None
        if frame.attrs.get("pairing_audit"):
            result.settings["pairing_audit"] = frame.attrs["pairing_audit"]
        from .diagnostics import augment

        try:
            augment(result, frame)
        except Exception as exc:  # noqa: BLE001 - optional post-fit diagnostics are isolated; core errors propagate
            # This boundary is only for auxiliary post-fit tables. Core failures above propagate.
            result.settings.setdefault("diagnostic_failures", []).append(
                {"id": "post_fit_tables", "exception": type(exc).__name__, "message": str(exc)}
            )
            result.notes.append(
                "Some optional diagnostic tables could not be produced. Core results are retained; see diagnostic_failures in run details."
            )
            result.status = "partial"
        from .capabilities import describe_capabilities

        describe_capabilities(result)
        result.settings["evidence_status"] = result.status
        return result

    return wrapped
