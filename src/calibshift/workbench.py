"""English local research workbench with traceable diagnostic downloads."""

import json

import streamlit as st

from .reporting import method_label


def header(info):
    """Present project identity without external fonts, tracking or accounts."""
    accent = "#17466b" if info["slug"] in {"sensefusion", "calibshift"} else "#7a263a"
    st.markdown(
        f"""<style>
    .stApp {{background:#f7f9fb;color:#182431}}
    .block-container {{max-width:1280px;padding-top:2.1rem;padding-bottom:3rem}}
    h1,h2,h3 {{color:#172f43;letter-spacing:-.025em}}
    [data-testid="stSidebar"] {{background:#edf1f5;border-right:1px solid #d4dde4}}
    [data-testid="stMetric"] {{background:white;border:1px solid #dce3e8;border-top:3px solid {accent};border-radius:7px;padding:16px}}
    [data-testid="stExpander"] {{background:white;border-color:#dce3e8}}
    [data-baseweb="tab-list"] {{gap:1.4rem;border-bottom:1px solid #ccd7df}}
    [data-baseweb="tab"] {{height:3rem;font-weight:600}}
    .stButton>button[kind="primary"] {{background:{accent};border-color:{accent};min-height:2.8rem}}
    @media(max-width:700px) {{.block-container {{padding:1rem}} [data-baseweb="tab-list"] {{gap:.35rem}}}}
    </style>""",
        unsafe_allow_html=True,
    )
    with st.sidebar:
        st.caption("RESEARCH WORKBENCH")
        st.title(info["title"])
        st.markdown(
            "**Your workflow**\n\n1. Choose an example or your table.\n2. Confirm the measurement roles.\n3. Run, inspect and export."
        )
        st.divider()
        st.markdown("**Read the results in order**\n\nOverview → diagnostics → complete tables → run details.")
        st.caption("Missing measurements are handled explicitly. Unknown references are never invented.")
        st.divider()
        st.caption(
            "Version 0.5.2 · CPU analysis\n\nAnalysis runs on the computer or server hosting this app. "
            "Online uploads are sent to that server; use a local installation for confidential measurements. "
            "No AI service or API key is used."
        )
    st.caption("MEASUREMENTS  /  VALIDATION  /  REPRODUCIBLE RESULTS")
    st.title(info["title"])
    st.write(info["summary"])
    st.caption("Start with a public example, then use the same workflow with your own measurements.")


def readable(table):
    output = table.copy()
    for column in ["model", "method", "baseline"]:
        if column in output:
            output[column] = output[column].map(method_label)
    output.columns = [
        ("Factor: " + str(c).removeprefix("factor::"))
        if str(c).startswith("factor::")
        else ("Prediction: " + str(c).removeprefix("prediction::"))
        if str(c).startswith("prediction::")
        else str(c).replace("_", " ").capitalize()
        for c in output
    ]
    return output


def results(result, outputs, archive, slug, full_export_files):
    from functools import lru_cache

    from .presentation import concise_table, overview_content, select_view
    from .reporting import summary_files

    st.divider()
    st.subheader("Results workspace")
    st.caption("Execution completed · " + result.settings.get("evidence_summary", result.status))
    selection = {}

    def choose(label, values, key, default=None, format_func=str):
        if not values:
            st.session_state.pop(key, None)
            return None
        if st.session_state.get(key) not in values:
            st.session_state[key] = default if default in values else values[0]
        return st.selectbox(label, values, key=key, format_func=format_func)

    with st.expander("Choose the displayed comparison"):
        for key in ["domain", "response"]:
            initial = select_view(result, **selection)
            options = initial["options"][key]
            if len(options) > 1:
                selection[key] = choose("Displayed " + key, options, "view_" + key, initial[key])
        initial = select_view(result, **selection)
        if initial["options"]["method"]:
            selection["method"] = choose(
                "Displayed method", initial["options"]["method"], "view_method", initial["method"], method_label
            )
        initial = select_view(result, **selection)
        if initial["options"]["budget"]:
            selection["budget"] = choose(
                "Displayed standard budget", initial["options"]["budget"], "view_budget", initial["budget"]
            )
        st.caption("This changes the view of the finished run. It does not fit or select another model.")
    view = select_view(result, **selection)
    content = overview_content(result, view)
    view_key = json.dumps(selection, sort_keys=True, default=str)
    cache = st.session_state.setdefault("view_cache", {})
    if view_key not in cache:
        cache[view_key] = summary_files(result, **selection, png_dpi=140) if selection else outputs
    preview = cache[view_key]
    slots = st.columns(len(content["cards"]))
    from .presentation import _fmt

    for slot, (name, value) in zip(slots, content["cards"]):
        slot.metric(name, _fmt(value))
    st.caption("Response units: " + content["unit"])
    overview, diagnostics, tables, details = st.tabs(["Overview", "Diagnostics", "Tables", "Run details"])
    with overview:
        st.markdown("**" + content["question"] + "**")
        st.write(content["statement"])
        st.info(content["caveat"])
        for item in json.loads(preview["primary_catalog.json"]):
            st.image(preview[item["stem"] + ".png"], caption=item["caption"])
        table = concise_table(view)
        if len(table):
            st.dataframe(readable(table), hide_index=True, width="stretch")
        columns = st.columns(2)
        columns[0].download_button(
            "Download concise report (HTML)",
            preview["report.html"],
            file_name=f"{slug}_summary.html",
            mime="text/html",
            key="summary_html",
            on_click="ignore",
        )

        @lru_cache(maxsize=1)
        def pdf_bytes():
            return summary_files(result, **selection, include_pdf=True, png_dpi=220)["summary.pdf"]

        columns[1].download_button(
            "Download print report (PDF)",
            pdf_bytes,
            file_name=f"{slug}_summary.pdf",
            mime="application/pdf",
            key="summary_pdf",
            on_click="ignore",
        )
        st.caption(
            "The concise report is self-contained. All eligible tables and additional figures are in the optional extended bundle."
        )

        @lru_cache(maxsize=1)
        def selected_archive():
            import io
            import zipfile

            files = dict(full_export_files())
            for name in list(files):
                if name.startswith("primary_"):
                    files.pop(name)
            files.update(summary_files(result, **selection, include_pdf=True, png_dpi=220))
            stream = io.BytesIO()
            with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as bundle:
                for name, data in files.items():
                    bundle.writestr(name, data)
            return stream.getvalue()

        st.session_state["displayed_archive"] = selected_archive
        st.session_state["displayed_view"] = {k: view[k] for k in ["method", "domain", "response", "budget", "scope"]}
        st.download_button(
            "Download extended reproducibility bundle",
            selected_archive,
            file_name=f"{slug}_results.zip",
            mime="application/zip",
            key="result_download",
            on_click="ignore",
        )
    with diagnostics:
        st.write("Additional diagnostics are generated when requested. They do not change the fitted analysis.")
        if st.button("Prepare additional diagnostics", key="prepare_diagnostics"):
            with st.spinner("Preparing diagnostic previews…"):
                import matplotlib.pyplot as plt

                from .reporting import encode_figure, guarded_diagnostics

                prepared = []
                for stem, title, caption, figure in guarded_diagnostics(result):
                    try:
                        prepared.append(
                            {
                                "stem": stem,
                                "title": title,
                                "caption": caption,
                                "png": encode_figure(figure, ("png",), 140)["png"],
                            }
                        )
                    finally:
                        plt.close(figure)
                st.session_state["diagnostic_cache"] = prepared
        prepared = st.session_state.get("diagnostic_cache", [])
        if prepared:
            index = st.selectbox(
                "Diagnostic figure",
                range(len(prepared)),
                format_func=lambda i: prepared[i]["title"],
                key="diagnostic_choice",
            )
            item = prepared[index]
            st.image(item["png"], caption=item["caption"])
            for slot, ext, mime in zip(
                st.columns(3), ["png", "pdf", "svg"], ["image/png", "application/pdf", "image/svg+xml"]
            ):
                slot.download_button(
                    "Download " + ext.upper(),
                    lambda e=ext, s=item["stem"]: full_export_files()[s + "." + e],
                    file_name=item["stem"] + "." + ext,
                    mime=mime,
                    key="diagnostic_" + ext,
                    on_click="ignore",
                )
        for problem in result.settings.get("diagnostic_errors", []):
            st.warning(
                f"Optional diagnostic {problem['id']} unavailable: {problem['message']}. Core numerical tables remain available."
            )
    with tables:
        name = st.selectbox(
            "Result table",
            list(result.tables),
            format_func=lambda v: v.replace("_", " ").capitalize(),
            key="table_choice",
        )
        table = result.tables[name]
        st.caption(f"{len(table):,} rows · {len(table.columns):,} columns")
        st.dataframe(readable(table), hide_index=True, width="stretch")
        st.download_button(
            "Download this table (CSV)",
            table.to_csv(index=False).encode("utf-8-sig"),
            file_name=name + ".csv",
            mime="text/csv",
            key="table_download",
            on_click="ignore",
        )
    with details:
        if "capabilities" in result.tables:
            st.dataframe(readable(result.tables["capabilities"]), hide_index=True, width="stretch")
        with st.expander("Interpretation and limitations"):
            for note in result.notes:
                st.write(note)
        st.json(
            {
                "application": slug,
                "version": result.settings.get("software_version"),
                "input": result.settings.get("input_name"),
                "source_sha256": result.settings.get("software_source_sha256"),
                "evidence": result.settings.get("evidence_summary"),
            },
            expanded=False,
        )
        st.download_button(
            "Download resolved configuration",
            outputs["config.json"],
            file_name="config.json",
            mime="application/json",
            key="config_download",
            on_click="ignore",
        )
        with st.expander("All settings, provenance and input mapping"):
            st.json(result.settings, expanded=False)
