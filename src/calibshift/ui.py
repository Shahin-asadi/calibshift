"""Guided, local analysis with explicit input roles and deferred exports."""

import hashlib
import io
import json
import zipfile
from functools import lru_cache

import pandas as pd
import streamlit as st
from threadpoolctl import threadpool_limits

from . import core
from .cli import example_config, example_context, example_path, project_info
from .common import InputError, fingerprint, json_text
from .importing import inspect_source, read_table, sheet_names
from .reporting import files_for_result, summary_files
from .templates import schema, starter_bytes

RESULT_KEYS = (
    "analysis_result",
    "analysis_files",
    "result_archive",
    "full_export_files",
    "result_signature",
    "view_cache",
    "diagnostic_cache",
    "summary_pdf_cache",
    "displayed_archive",
    "displayed_view",
    "view_method",
    "view_domain",
    "view_response",
    "view_budget",
    "reader_state",
    "reader_page",
    "reader_exports",
    "table_choice",
)


def clear_result():
    for key in RESULT_KEYS:
        st.session_state.pop(key, None)


def main():
    info = project_info()
    slug = info["slug"]
    spec = schema()
    st.set_page_config(page_title=info["title"], layout="wide")
    from .workbench import header, results

    header(info)
    st.subheader("1. Choose data")
    mode = st.radio(
        "Data source", ["Bundled example", "Upload a table", "Paste a table"], key="data_mode", horizontal=True
    )
    sample_name = info["examples"][0]
    if mode == "Bundled example":
        sample_name = st.selectbox("Example", info["examples"], key="example_name")
        st.download_button(
            "Download this public example",
            example_path(sample_name).read_bytes(),
            file_name=sample_name,
            mime="text/csv",
            on_click="ignore",
        )
        payload = example_path(sample_name).read_bytes()
        input_name = sample_name
    else:
        with st.expander("Optional starter files"):
            st.caption(
                "Artificial examples explain the column roles. Replace every example row with your measurements. Rows, columns and labels can be extended freely."
            )
            st.table(pd.DataFrame(spec["roles"], columns=["Role", "Example column"]))
            for slot, fmt in zip(st.columns(2), ["csv", "xlsx"]):
                slot.download_button(
                    "Download starter " + fmt.upper(),
                    lambda f=fmt: starter_bytes(f),
                    file_name=f"{slug}_artificial_starter.{fmt}",
                    key="starter_" + fmt,
                    on_click="ignore",
                )
            st.download_button(
                "Download blank headers (CSV)",
                lambda: starter_bytes("csv", blank=True),
                file_name=f"{slug}_headers.csv",
                key="blank_headers",
                on_click="ignore",
            )
        if mode == "Upload a table":
            upload = st.file_uploader("CSV or XLSX table", type=["csv", "xlsx"], max_upload_size=50, key="input_file")
            payload = upload.getvalue() if upload is not None else b""
            input_name = upload.name if upload is not None else ""
        else:
            pasted = st.text_area(
                "Paste headers and rows (comma, semicolon or tab separated)", key="pasted_table", height=150
            )
            payload = pasted.encode("utf-8")
            input_name = "pasted_table.csv"
    identity = (mode, input_name, hashlib.sha256(payload).hexdigest())
    if st.session_state.get("input_identity") != identity:
        clear_result()
        protected = {"data_mode", "input_file", "pasted_table", "example_name"}
        for key in list(st.session_state):
            if key not in protected:
                st.session_state.pop(key, None)
        st.session_state["input_identity"] = identity
    if not payload:
        st.info("Choose your file, paste a table, or use a bundled example.")
        return
    options = {}
    try:
        if mode != "Bundled example":
            source = io.BytesIO(payload)
            if input_name.lower().endswith(".xlsx"):
                sheets = sheet_names(source)
                try:
                    initial = inspect_source(source, input_name)[1]["worksheet"]
                except InputError:
                    initial = sheets[0]  # Keep the selector usable when the default sheet needs repair.
                options["sheet"] = st.selectbox(
                    "Data worksheet", sheets, index=sheets.index(initial), key="import_sheet"
                )
            with st.expander("Import options: headers, locale and missing cells"):
                options["header_row"] = int(
                    st.number_input("Header row (starts at 1)", min_value=1, value=1, step=1, key="header_row")
                )
                if not input_name.lower().endswith(".xlsx"):
                    separators = {"Automatic": "auto", "Comma": ",", "Semicolon": ";", "Tab": "\t"}
                    options["separator"] = separators[
                        st.selectbox("Column separator", list(separators), key="separator")
                    ]
                    options["encoding"] = st.selectbox(
                        "Text encoding", ["utf-8-sig", "cp1252", "utf-16"], key="encoding"
                    )
                options["decimal"] = st.selectbox("Decimal mark in numeric cells", [".", ","], key="decimal")
                markers = st.text_input(
                    "Missing-value markers (separate with |)", value="NA|N/A|ND|<LOD", key="missing_tokens"
                )
                options["missing_tokens"] = [v.strip() for v in markers.split("|") if v.strip()]
                st.caption(
                    "Markers affect selected numeric columns only. A recorded zero and literal specimen IDs remain unchanged."
                )
                raw = inspect_source(
                    source, input_name, **{k: v for k, v in options.items() if k not in {"decimal", "missing_tokens"}}
                )
                if st.checkbox("Rename headers before mapping", key="rename_headers"):
                    editor = st.data_editor(
                        pd.DataFrame(
                            {
                                "Original header": [str(v or "") for v in raw[0][0]],
                                "Use this name": [str(v or "") for v in raw[0][0]],
                            }
                        ),
                        disabled=["Original header"],
                        hide_index=True,
                        key="header_editor",
                        width="stretch",
                    )
                    options["header_overrides"] = editor["Use this name"].tolist()
            frame = read_table(source, input_name, **options)
        else:
            frame = read_table(io.BytesIO(payload), input_name)
    except InputError as exc:
        clear_result()
        st.error(str(exc))
        return
    st.caption(f"{len(frame):,} observations · {len(frame.columns):,} columns. Confirm roles before running.")
    with st.expander("Preview parsed data"):
        st.dataframe(frame.head(12), hide_index=True, width="stretch")
        for notice in frame.attrs.get("import_info", {}).get("notices", []):
            st.caption(notice)
    columns = list(frame.columns)
    defaults = example_config(sample_name) if mode == "Bundled example" else spec["config"]
    if slug == "matcheddoe" and mode != "Bundled example":
        for example in info["examples"]:
            candidate = example_config(example)
            if set(candidate.get("factors", [])) <= set(columns):
                defaults = candidate
                break

    def choose(label, default, key, optional=False, choices=None):
        choices = columns if choices is None else choices
        available = ["(none)"] + choices if optional else choices
        if not available:
            return None
        if st.session_state.get(key) not in available:
            st.session_state.pop(key, None)
        choice = st.selectbox(label, available, index=available.index(default) if default in available else 0, key=key)
        return None if choice == "(none)" else choice

    st.subheader("2. Confirm column roles")
    id_col = choose("Unique row ID (optional)", "sample_id", "id_col", True)
    if id_col is None:
        st.caption(
            "Internal row keys will be generated for traceability. They do not identify a physical specimen or match separate files."
        )
    params = {"id_col": id_col}
    declared = example_context(sample_name).get("column_metadata", {}).copy() if mode == "Bundled example" else {}
    if slug != "matcheddoe":
        target_default = next(
            (c for c in ["target", defaults.get("target"), "Reference", "response"] if c in columns), None
        )
        target = choose(
            "Recorded reference / response",
            target_default,
            "target_col",
            True,
            choices=[c for c in columns if c != id_col],
        )
        group_default = next((c for c in ["group", defaults.get("group_col")] if c in columns), None)
        group_col = choose(
            "Physical specimen / formulation (optional)",
            group_default,
            "group_col",
            True,
            choices=[c for c in columns if c not in {id_col, target}],
        )
        params.update(target=target or "__missing_reference__", group_col=group_col)
        if group_col is None:
            st.caption(
                "Without specimen IDs, each row is a separate observational unit; independence is not established by the software."
            )
        cv_group_col = None
        if slug != "calibshift":
            with st.expander("Repeated readings and validation batches"):
                st.caption(
                    "Physical specimen IDs control specimen means and grouping. A separate batch ID controls held-out folds; it never turns a batch into one specimen."
                )
                cv_group_col = choose(
                    "Optional held-out batch / validation group",
                    None,
                    "cv_group_col",
                    True,
                    choices=[c for c in columns if c not in {id_col, target, group_col}],
                )
            params["cv_group_col"] = cv_group_col
        candidates = [c for c in columns if c not in {id_col, target, group_col, cv_group_col}]
        if slug == "calibshift":
            domain = choose(
                "Acquisition condition / domain",
                "domain" if "domain" in columns else defaults.get("domain_col"),
                "domain_col",
                choices=candidates,
            )
            if domain is None:
                st.error("Select a condition column and physical specimen IDs.")
                return
            candidates = [c for c in candidates if c != domain]
            domains = list(frame[domain].dropna().astype(str).str.strip().unique())
            if not domains:
                st.error("The acquisition condition column is empty.")
                return
            source = choose(
                "Source condition",
                "X1" if "X1" in domains else defaults.get("source"),
                "source_domain",
                choices=domains,
            )
            destination_options = [v for v in domains if v != source]
            old = st.session_state.get("destinations")
            if old is not None and not set(old) <= set(destination_options):
                st.session_state.pop("destinations", None)
            destinations = st.multiselect(
                "Target conditions", destination_options, default=destination_options, key="destinations"
            )
            feasible = max(0, int(frame[group_col].nunique()) - 1) if group_col else 0
            initial = [k for k in [0, 2, 4] if k <= feasible]
            budget_text = st.text_input(
                "Target-standard budgets (comma separated; 0 = baseline)",
                value=",".join(map(str, initial or [0])),
                key="budgets",
            )
            st.caption(
                f"Observed identity count permits at most {feasible} standards before per-fold availability checks. Empty budgets retain unadapted baselines."
            )
            try:
                budgets = [int(v.strip()) for v in budget_text.split(",") if v.strip()]
            except ValueError:
                clear_result()
                st.error("Enter nonnegative integer budgets separated by commas.")
                return
            params.update(domain_col=domain, source=source, destinations=destinations, budgets=budgets)
        comparison = False
        if slug == "assayreport":
            route = st.radio(
                "Analysis route",
                ["Paired comparison", "Build held-out predictions from measurements"],
                index=1 if mode == "Bundled example" else 0,
                key="assay_route",
            )
            comparison = route == "Paired comparison"
            if comparison:
                prediction = choose(
                    "Comparison value column",
                    "prediction" if "prediction" in columns else defaults.get("prediction_column"),
                    "prediction_col",
                    choices=candidates,
                )
                kind = st.radio(
                    "Comparison values are",
                    ["Measured values", "Model predictions"],
                    key="comparison_kind",
                    horizontal=True,
                )
                origin = "unknown"
                if kind == "Model predictions":
                    origin = st.selectbox(
                        "Prediction origin",
                        ["unknown", "independent_holdout", "out_of_fold", "fitted"],
                        key="prediction_origin",
                    )
                params.update(
                    prediction_column=prediction,
                    comparison_kind="measured" if kind == "Measured values" else "prediction",
                    prediction_origin=origin,
                    feature_columns=[],
                )
            unit = st.selectbox(
                "Agreement unit",
                ["specimen_mean", "individual"],
                index=0 if group_col else 1,
                key="agreement_unit",
                format_func=lambda s: {
                    "specimen_mean": "Mean within each physical specimen",
                    "individual": "Individual paired readings",
                }[s],
            )
            independent = st.checkbox(
                "Pairs / specimens are independent by design", value=False, key="independent_pairs"
            )
            params.update(agreement_unit=unit, independent_pairs=independent)
        if not comparison:
            initial = [c for c in candidates if "__" in c]
            if not initial:
                initial = [c for c in defaults.get("feature_columns", []) if c in candidates]
            if not initial and mode != "Bundled example":
                initial = candidates
            if "features" in st.session_state:
                st.session_state["features"] = [c for c in st.session_state["features"] if c in candidates]
            selected = st.multiselect("Measurement feature columns", candidates, default=initial, key="features")
            if slug == "sensefusion":
                inferred = {}
                for c in selected:
                    inferred.setdefault(c.split("__", 1)[0] if "__" in c else "Measurements", []).append(c)
                manual = st.checkbox(
                    "Map measurement blocks manually", value=not any("__" in c for c in selected), key="manual_blocks"
                )
                if manual:
                    count = int(
                        st.number_input(
                            "Number of blocks",
                            min_value=1,
                            max_value=6,
                            value=min(2, max(1, len(selected))),
                            step=1,
                            key="block_count",
                        )
                    )
                    blocks = {}
                    assigned = set()
                    for i in range(count):
                        name = st.text_input(f"Block {i + 1} name", value=f"Block {i + 1}", key=f"block_name_{i}")
                        opts = [c for c in selected if c not in assigned]
                        old = st.session_state.get(f"block_features_{i}")
                        if old is not None and not set(old) <= set(opts):
                            st.session_state.pop(f"block_features_{i}", None)
                        cols = st.multiselect(
                            f"Block {i + 1} features",
                            opts,
                            default=opts if i == count - 1 else opts[:1],
                            key=f"block_features_{i}",
                        )
                        if name in blocks:
                            clear_result()
                            st.error("Give each measurement block a distinct name.")
                            return
                        blocks[name] = cols
                        assigned.update(cols)
                    params["block_columns"] = blocks
                else:
                    params["block_columns"] = inferred
                st.caption(
                    "One block supports a single-block comparison. Fusion requires at least two usable blocks. Empty or unavailable blocks are reported separately."
                )
            else:
                params["feature_columns"] = selected
        with st.expander("Response label and units"):
            meta = declared.get(target, {})
            label = st.text_input(
                "Response display label", value=meta.get("label", target or "Response"), key="target_label"
            )
            unit = st.text_input("Response unit (blank if unknown)", value=meta.get("unit", ""), key="target_units")
            if target:
                declared[target] = {"label": label or target, **({"unit": unit} if unit else {})}
            if params.get("prediction_column") and unit:
                declared[params["prediction_column"]] = {"unit": unit}
    else:
        opts = [c for c in columns if c != id_col]
        if "factors" in st.session_state:
            st.session_state["factors"] = [c for c in st.session_state["factors"] if c in opts]
        factors = st.multiselect(
            "Numeric factors (one or more)",
            opts,
            default=[c for c in defaults.get("factors", []) if c in opts],
            key="factors",
        )
        ropts = [c for c in opts if c not in factors]
        if "responses" in st.session_state:
            st.session_state["responses"] = [c for c in st.session_state["responses"] if c in ropts]
        responses = st.multiselect(
            "Recorded responses",
            ropts,
            default=[c for c in defaults.get("responses", []) if c in ropts],
            key="responses",
        )
        models = ["linear", "2fi", "additive_quadratic", "quadratic"]
        model = st.selectbox("Model form", models, index=models.index(defaults.get("model", "linear")), key="model")
        response_mode = st.radio(
            "Response cohort",
            ["matched", "per_response"],
            horizontal=True,
            key="response_mode",
            format_func=lambda v: {
                "matched": "Same complete runs for every response",
                "per_response": "Each response uses its available runs",
            }[v],
        )
        st.caption(
            "Rank determines whether the chosen model is estimable. More than three factors retain fits and residuals; automatic candidate grids are disabled."
        )
        independent = st.checkbox(
            "Rows represent independently performed experimental runs",
            value=mode == "Bundled example",
            key="independent_runs",
        )
        directions = {}
        with st.expander("Response objectives and units"):
            for r in responses:
                directions[r] = st.selectbox(
                    "Objective for " + r,
                    ["minimise", "maximise"],
                    index=0 if defaults.get("directions", {}).get(r) == "minimise" else 1,
                    key="direction_" + r,
                )
                unit = st.text_input(
                    "Unit for " + r + " (blank if unknown)", value=declared.get(r, {}).get("unit", ""), key="unit_" + r
                )
                declared[r] = {"label": r, **({"unit": unit} if unit else {})}
        params.update(
            factors=factors,
            responses=responses or ["__missing_response__"],
            model=model,
            directions=directions,
            response_mode=response_mode,
            independent_runs=independent,
        )
        with st.expander("Optional reported-equation check"):
            st.caption(
                "Enter coefficients in a declared basis; expressions are never executed. All terms, including explicit zero coefficients, are required."
            )
            enabled = st.checkbox("Compare a reported coefficient table", key="equation_enabled")
            if enabled and factors and responses:
                import numpy as np

                from .core import design_matrix
                from .equations import coefficient_table_specification

                terms = design_matrix(np.zeros((1, len(factors))), factors, model)[1]
                basis = st.selectbox("Coefficient basis", ["actual", "coded"], key="equation_basis")
                table = st.data_editor(
                    pd.DataFrame(
                        [{"response": r, "term": term, "coefficient": None} for r in responses for term in terms]
                    ),
                    disabled=["response", "term"],
                    hide_index=True,
                    key="coefficient_editor",
                    column_config={"coefficient": st.column_config.NumberColumn(required=True)},
                )
                coding = None
                if basis == "coded":
                    coding = st.data_editor(
                        pd.DataFrame(
                            {"factor": factors, "centre": [None] * len(factors), "half_range": [None] * len(factors)}
                        ),
                        disabled=["factor"],
                        hide_index=True,
                        key="coding_editor",
                    )
                try:
                    params["reported_equations"] = coefficient_table_specification(table, basis, coding)
                except InputError as exc:
                    clear_result()
                    st.info(str(exc))
                    return
    context = example_context(sample_name) if mode == "Bundled example" else {"input_name": input_name}
    params.update(context | {"column_metadata": {k: v for k, v in declared.items() if k in frame}})
    signature = fingerprint(frame) + json.dumps(params, sort_keys=True) + json.dumps(options, sort_keys=True)
    if st.session_state.get("result_signature") != signature:
        clear_result()
    if st.button("3. Run analysis", type="primary", key="run_analysis"):
        clear_result()
        try:
            with st.spinner("Calculating eligible analyses…"), threadpool_limits(limits=1):
                result = core.analyse(frame, **params)
                output = summary_files(result, png_dpi=140)
                result.settings["import_options"] = options
                # Import settings accompany analysis settings without entering the scientific core.
                config = result.settings.get("call_parameters", {}) | {"import_options": options}
                result.settings["export_config"] = config
                output["config.json"] = json_text(config).encode("utf-8")

                @lru_cache(maxsize=1)
                def full_export_files():
                    with threadpool_limits(limits=1):
                        return files_for_result(result)

                @lru_cache(maxsize=1)
                def complete_archive():
                    memory = io.BytesIO()
                    with zipfile.ZipFile(memory, "w", zipfile.ZIP_DEFLATED) as archive:
                        for name, data in full_export_files().items():
                            archive.writestr(name, data)
                    return memory.getvalue()

                st.session_state.update(
                    analysis_result=result,
                    analysis_files=output,
                    result_signature=signature,
                    result_archive=complete_archive,
                    full_export_files=full_export_files,
                )
        except InputError as exc:
            st.error("Please review the input: " + str(exc))
            return
    result = st.session_state.get("analysis_result")
    if result is not None:
        results(
            result,
            st.session_state["analysis_files"],
            st.session_state["result_archive"],
            slug,
            st.session_state["full_export_files"],
        )
