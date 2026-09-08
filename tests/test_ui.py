from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest

from calibshift.cli import example_path, project_info

APP = Path(__file__).resolve().parents[1] / "app.py"


def test_guided_demo_produces_downloadable_report():
    at = AppTest.from_file(str(APP), default_timeout=30).run()
    assert not at.exception
    at.button(key="run_analysis").click().run()
    assert not at.exception and not at.error
    assert at.session_state["analysis_result"].status == "complete"
    files = at.session_state["analysis_files"]
    assert {"report.html", "config.json", "primary_catalog.json"} <= set(files)
    assert "results.xlsx" not in files  # The expensive workbook is deferred until export.
    assert any(
        name.startswith("primary_") and name.endswith(".png") and len(data) > 5000 for name, data in files.items()
    )
    assert callable(at.session_state["result_archive"])
    assert callable(at.session_state["full_export_files"])


def test_changing_input_removes_stale_result_before_rerun():
    at = AppTest.from_file(str(APP), default_timeout=30).run()
    at.button(key="run_analysis").click().run()
    assert "analysis_result" in at.session_state
    data = pd.read_csv(example_path()).iloc[1:].copy()
    at.radio(key="data_mode").set_value("Upload a table").run()
    at.file_uploader(key="input_file").set_value(("changed.csv", data.to_csv(index=False).encode(), "text/csv")).run()
    assert not at.exception
    assert "analysis_result" not in at.session_state


def test_upload_with_missing_response_returns_partial_report():
    data = pd.read_csv(example_path())
    column = "response" if project_info()["slug"] == "matcheddoe" else "target"
    data = data.drop(columns=column)
    at = AppTest.from_file(str(APP), default_timeout=30).run()
    at.radio(key="data_mode").set_value("Upload a table").run()
    at.file_uploader(key="input_file").set_value(
        ("missing_response.csv", data.to_csv(index=False).encode(), "text/csv")
    ).run()
    assert not at.exception
    at.button(key="run_analysis").click().run()
    assert not at.exception and not at.error
    assert at.session_state["analysis_result"].status == "audit_only"


def test_duplicate_id_upload_gives_actionable_error_not_traceback():
    data = pd.read_csv(example_path())
    data.loc[1, "sample_id"] = data.loc[0, "sample_id"]
    at = AppTest.from_file(str(APP), default_timeout=30).run()
    at.radio(key="data_mode").set_value("Upload a table").run()
    at.file_uploader(key="input_file").set_value(("duplicate.csv", data.to_csv(index=False).encode(), "text/csv")).run()
    at.button(key="run_analysis").click().run()
    assert not at.exception
    assert at.error and "repeat" in at.error[0].value


def test_leaving_example_clears_download_before_file_selection():
    at = AppTest.from_file(str(APP), default_timeout=60).run()
    at.button(key="run_analysis").click().run()
    assert "analysis_result" in at.session_state
    at.radio(key="data_mode").set_value("Upload a table").run()
    assert "analysis_result" not in at.session_state
    assert "analysis_files" not in at.session_state


def test_view_changes_keep_frozen_predictions_and_download_selection(monkeypatch):
    import io
    import json
    import zipfile

    from calibshift import core
    from calibshift.presentation import select_view

    at = AppTest.from_file(str(APP), default_timeout=60).run()
    if project_info()["slug"] == "matcheddoe":
        at.selectbox(key="example_name").set_value("banana_design.csv").run()
    at.button(key="run_analysis").click().run()
    assert not at.exception and not at.error
    result = at.session_state["analysis_result"]
    before = result.tables["predictions"].to_csv(index=False)

    def forbidden(*args, **kwargs):
        raise AssertionError("Changing result views must not refit")

    monkeypatch.setattr(core, "analyse", forbidden)
    for key in ["view_domain", "view_response", "view_method", "view_budget"]:
        widgets = [s for s in at.selectbox if s.key == key]
        if widgets and len(widgets[0].options) > 1:
            widgets[0].select_index(len(widgets[0].options) - 1).run()
            assert not at.exception and not at.error
    at.run()
    assert not at.exception
    assert result.tables["predictions"].to_csv(index=False) == before
    selected = at.session_state["displayed_view"]
    view = select_view(result, **{k: v for k, v in selected.items() if k != "scope"})
    with zipfile.ZipFile(io.BytesIO(at.session_state["displayed_archive"]())) as bundle:
        recorded = json.loads(bundle.read("summary_view.json"))
        for key in selected:
            assert recorded[key] == view[key]
        assert "summary_cohort.csv" in bundle.namelist()
    at.radio(key="data_mode").set_value("Upload a table").run()
    assert "displayed_archive" not in at.session_state
    assert "analysis_result" not in at.session_state
