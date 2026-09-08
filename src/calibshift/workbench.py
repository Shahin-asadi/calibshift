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
        st.markdown(
            "**Read the results in order**\n\nOverview → scientific sections → downloads. Every calculated table remains available in All tables."
        )
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

    from .presentation import _fmt, concise_table, overview_content, select_view
    from .reporting import summary_files
    from .result_reader import (
        SCOPE_NOTE,
        archive_index,
        detailed_html,
        detailed_pdf,
        diagnostic_previews,
        key_bundle,
        report_tables,
        section_figures,
        sections,
        table_description,
    )

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
        st.caption(
            "These controls change the overview of the finished run. Detailed sections retain the comparisons labelled in their tables and captions. No model is refitted."
        )
    view = select_view(result, **selection)
    content = overview_content(result, view)
    view_key = json.dumps(selection, sort_keys=True, default=str)
    cache = st.session_state.setdefault("view_cache", {})
    if view_key not in cache:
        cache[view_key] = summary_files(result, **selection, png_dpi=140) if selection else outputs
    preview = cache[view_key]
    reader_state = st.session_state.setdefault("reader_state", {})

    def get_figures():
        # Captured session-owned state also works in deferred download callbacks.
        if "figures" not in reader_state:
            reader_state["figures"] = diagnostic_previews(result)
        return reader_state["figures"]

    @lru_cache(maxsize=1)
    def report_html_bytes():
        return detailed_html(result, selection, get_figures(), preview)

    @lru_cache(maxsize=1)
    def report_pdf_bytes():
        return detailed_pdf(result, selection, get_figures(), preview)

    @lru_cache(maxsize=1)
    def key_zip_bytes():
        return key_bundle(result, selection, get_figures(), preview)

    @lru_cache(maxsize=1)
    def selected_archive():
        import io
        import zipfile

        files = dict(full_export_files())
        for name in list(files):
            if name.startswith("primary_"):
                files.pop(name)
        files.update(summary_files(result, **selection, include_pdf=True, png_dpi=220))
        files["analysis_report.html"] = report_html_bytes()
        files["START_HERE.html"] = archive_index(files)
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as bundle:
            for name, data in files.items():
                bundle.writestr(name, data)
        return stream.getvalue()

    st.session_state["displayed_archive"] = selected_archive
    st.session_state["displayed_view"] = {k: view[k] for k in ["method", "domain", "response", "budget", "scope"]}
    st.session_state["reader_exports"] = {"html": report_html_bytes, "pdf": report_pdf_bytes, "key_zip": key_zip_bytes}
    pages = sections(result)
    names = ["Overview", *[s["title"] for s in pages], "All tables", "Downloads", "Run details"]
    if st.session_state.get("reader_page") not in names:
        st.session_state["reader_page"] = "Overview"
    st.caption("Read the report by section. Key figures and tables appear together; the full archive is optional.")
    page = st.radio("Results page", names, key="reader_page", horizontal=True)

    def show_table(name, table):
        st.markdown("### " + name.replace("_", " ").capitalize())
        st.caption(table_description(result, name))
        st.caption(f"{len(table):,} rows · {len(table.columns):,} columns · scroll to inspect all values")
        st.dataframe(readable(table), hide_index=True, width="stretch", height=min(460, 75 + 35 * len(table)))
        st.download_button(
            "Download " + name.replace("_", " ") + " (CSV)",
            table.to_csv(index=False).encode("utf-8-sig"),
            file_name=name + ".csv",
            mime="text/csv",
            key="reader_table_" + name,
            on_click="ignore",
        )

    def detailed_downloads():
        columns = st.columns(3)
        for slot, label, callback, suffix, mime in [
            (columns[0], "Download detailed report (HTML)", report_html_bytes, "analysis.html", "text/html"),
            (columns[1], "Download detailed report (PDF)", report_pdf_bytes, "analysis.pdf", "application/pdf"),
            (columns[2], "Download key results ZIP", key_zip_bytes, "key_results.zip", "application/zip"),
        ]:
            slot.download_button(
                label, callback, file_name=f"{slug}_{suffix}", mime=mime, key="reader_" + suffix, on_click="ignore"
            )

    if page == "Overview":
        slots = st.columns(len(content["cards"]))
        for slot, (name, value) in zip(slots, content["cards"]):
            slot.metric(name, _fmt(value))
        st.caption("Response units: " + content["unit"])
        st.markdown("**" + content["question"] + "**")
        st.write(content["statement"])
        st.info(content["caveat"])
        for item in json.loads(preview["primary_catalog.json"]):
            st.image(preview[item["stem"] + ".png"], caption=item["caption"])
        table = concise_table(view)
        if len(table):
            st.dataframe(readable(table), hide_index=True, width="stretch")
        st.markdown("### Continue reading")
        for section in pages:
            st.markdown("**" + section["title"] + "** — " + section["intro"])
        detailed_downloads()
        with st.expander("Short overview exports"):
            st.download_button(
                "Download concise report (HTML)",
                preview["report.html"],
                file_name=f"{slug}_summary.html",
                mime="text/html",
                key="summary_html",
                on_click="ignore",
            )
            st.download_button(
                "Download print report (PDF)",
                lambda: summary_files(result, **selection, include_pdf=True, png_dpi=220)["summary.pdf"],
                file_name=f"{slug}_summary.pdf",
                mime="application/pdf",
                key="summary_pdf",
                on_click="ignore",
            )
    elif page in [s["title"] for s in pages]:
        section = next(s for s in pages if s["title"] == page)
        st.subheader(section["title"])
        st.write(section["intro"])
        st.caption(SCOPE_NOTE)
        figures = []
        if section["prefixes"]:
            with st.spinner("Preparing this run's diagnostic figures…"):
                figures = section_figures(section, get_figures())
            for item in figures:
                st.markdown("### " + item["title"])
                st.image(item["png"], caption=item["caption"])
                st.download_button(
                    "Download figure (PNG)",
                    item["png"],
                    file_name=item["stem"] + ".png",
                    mime="image/png",
                    key="reader_figure_" + item["stem"],
                    on_click="ignore",
                )
        tables = report_tables(result, section)
        for name, table in tables:
            show_table(name, table)
        if not figures and not tables:
            st.info(
                "This section is unavailable for this input/configuration. Review the capabilities and limitations in Run details; other supported sections remain available."
            )
        for problem in result.settings.get("diagnostic_errors", []):
            st.warning(f"Optional diagnostic unavailable: {problem['message']}. Numerical tables remain available.")
    elif page == "All tables":
        st.write(
            "Every calculated table is available here, including full predictions and fields omitted from the print excerpts."
        )
        name = st.selectbox(
            "Result table",
            list(result.tables),
            format_func=lambda v: v.replace("_", " ").capitalize(),
            key="table_choice",
        )
        show_table(name, result.tables[name])
    elif page == "Downloads":
        st.subheader("Choose the output you need")
        st.write(
            "The detailed report follows the same reading sections as the web app. HTML works offline; PDF is paginated for printing. Large tables have labelled print excerpts; full values remain in their CSVs and the web app."
        )
        detailed_downloads()
        st.markdown(
            "**Key results ZIP:** 01_REPORTS, 02_TABLES, 03_FIGURES and 04_RUN_DETAILS, with START_HERE.txt. It contains the report tables and figures, not every intermediate output."
        )
        with st.expander("Advanced: complete reproducibility archive"):
            st.write(
                "All original outputs, configuration, predictions and detailed diagnostics. Open START_HERE.html after extracting it."
            )
            st.download_button(
                "Download extended reproducibility bundle",
                selected_archive,
                file_name=f"{slug}_results.zip",
                mime="application/zip",
                key="result_download",
                on_click="ignore",
            )
    else:
        if "capabilities" in result.tables:
            show_table("capabilities", result.tables["capabilities"])
        st.markdown("### Interpretation and limitations")
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
