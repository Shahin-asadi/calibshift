"""Regression evidence for ordinary files, capability boundaries and v0.5.1 exports."""

import io
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from openpyxl import Workbook, load_workbook
from streamlit.testing.v1 import AppTest

from calibshift import core
from calibshift.common import InputError
from calibshift.importing import numeric_columns, read_table
from calibshift.reporting import files_for_result, summary_files
from calibshift.templates import schema, starter_bytes, starter_frame


def analyse_starter(frame=None, **changes):
    return core.analyse(starter_frame() if frame is None else frame, **(schema()["config"] | changes))


@pytest.mark.parametrize("extension", ["csv", "xlsx"])
def test_real_starter_can_be_extended_and_reopened(extension):
    original = read_table(io.BytesIO(starter_bytes(extension)), "starter." + extension)
    assert len(original) == len(starter_frame())
    assert list(original) == list(starter_frame())
    if extension == "xlsx":
        book = load_workbook(io.BytesIO(starter_bytes(extension)))
        assert book.sheetnames == ["Data", "Instructions"]
        assert book["Data"].freeze_panes == "A2"
        assert not book["Data"].protection.sheet
        assert not book["Data"].merged_cells
        assert book["Data"]["A1"].font.name == "Times New Roman"
        assert book["Data"]["A1"].font.bold
    a = analyse_starter(original)
    b = analyse_starter()
    key = "model_summary" if schema()["slug"] == "matcheddoe" else "scores"
    pd.testing.assert_frame_equal(a.tables[key], b.tables[key])


def test_locale_and_ids_are_separate_from_numeric_conversion():
    frame = read_table(
        io.BytesIO(b"ID;response;signal\n001;0;1,25\nNA;2,5;ND\n0003;NA;3,1\n"),
        "data.csv",
        decimal=",",
        missing_tokens=["NA", "ND"],
    )
    assert frame.ID.tolist() == ["001", "NA", "0003"]
    values = numeric_columns(frame, ["response", "signal"])
    assert values.response.iloc[0] == 0
    assert values.response.iloc[1] == 2.5
    assert np.isnan(values.signal.iloc[1])
    assert frame.ID.iloc[1] == "NA"


def test_sheet_header_choice_and_header_rename():
    book = Workbook()
    book.active.title = "Instructions"
    book.active.append(["Do not analyse"])
    data = book.create_sheet("Data")
    data.append(["Intro"])
    data.append(["", "x", "x"])
    data.append([0, 1, 2])
    data.append([3, 4, 5])
    stream = io.BytesIO()
    book.save(stream)
    with pytest.raises(InputError, match="unnamed"):
        read_table(stream, "data.xlsx", header_row=2)
    frame = read_table(stream, "data.xlsx", header_row=2, header_overrides=["Ref", "x1", "x2"])
    assert frame.attrs["import_info"]["worksheet"] == "Data"
    assert frame.iloc[0, 0] == 0
    assert frame.attrs["import_info"]["column_mapping"][0]["source_header"] == ""


def test_uncached_formula_is_actionable():
    book = Workbook()
    book.active.append(["x", "y"])
    book.active.append([1, "=A2*2"])
    stream = io.BytesIO()
    book.save(stream)
    with pytest.raises(InputError, match="Recalculate"):
        read_table(stream, "formula.xlsx")


def test_import_limits_and_bad_numeric_example_are_explained():
    with pytest.raises(InputError, match="limit"):
        read_table(io.BytesIO(b"a,b\n1,2\n3,4"), "x.csv", max_cells=2)
    frame = read_table(io.BytesIO(b"y,x\n0,bad\n1,2"), "x.csv")
    with pytest.raises(InputError, match="row 2.*bad"):
        numeric_columns(frame, ["x"])
    with pytest.raises(InputError, match="Infinite"):
        numeric_columns(pd.DataFrame({"x": [np.inf]}), ["x"])


@pytest.mark.parametrize(
    "name",
    [
        "feature",
        "group",
        "response",
        "prediction",
        "index",
        "a space",
        "Δ sensor",
        "123",
        "a long measurement header " + "signal " * 15,
    ],
)
def test_arbitrary_measurement_headers_survive_core_and_diagnostics(name):
    frame = starter_frame()
    config = schema()["config"].copy()
    slug = schema()["slug"]
    if slug == "sensefusion":
        old = "Sensor A"
        config["block_columns"] = {"A": [name], "B": ["Sensor B"]}
    elif slug == "calibshift":
        old = "Signal"
        config["feature_columns"] = [name]
    elif slug == "matcheddoe":
        old = "Time (min)"
        config["factors"] = [name]
    else:
        old = "Comparison"
        config["prediction_column"] = name
    frame = frame.rename(columns={old: name})
    result = core.analyse(frame, **config)
    assert not result.settings.get("diagnostic_failures")
    assert "predictions" in result.tables
    assert name in result.settings["columns"]
    if "feature_correlation_preview" in result.tables:
        table = result.tables["feature_correlation_preview"]
        assert not table.columns.duplicated().any()
        assert name in table.columns


def test_no_identifier_generates_internal_keys_without_independence_claim():
    result = analyse_starter()
    assert result.settings["input_preparation"]["generated_row_id"]
    assert result.tables["row_mapping"].sample_id.is_unique
    assert result.settings["call_parameters"]["id_col"] is None
    assert "not a physical specimen" in result.settings["input_preparation"]["row_id_meaning"]


def test_optional_post_fit_failure_preserves_numerical_core(monkeypatch):
    from calibshift import diagnostics

    expected = analyse_starter().tables["predictions"]

    def fail(*args):
        raise ValueError("injected optional diagnostic")

    monkeypatch.setattr(diagnostics, "augment", fail)
    result = analyse_starter()
    pd.testing.assert_frame_equal(result.tables["predictions"], expected)
    assert result.settings["diagnostic_failures"][0]["exception"] == "ValueError"
    assert result.status == "partial"
    with pytest.raises(InputError):
        core.analyse(pd.DataFrame(), **schema()["config"])


def test_summary_is_standalone_and_small_while_bundle_keeps_all_tables():
    result = analyse_starter()
    preview = summary_files(result, include_pdf=True)
    assert preview["summary.pdf"].startswith(b"%PDF")
    assert b"data:image/png;base64," in preview["report.html"]
    assert b"Analysis settings" not in preview["report.html"]
    assert len(json.loads(preview["primary_catalog.json"])) <= 2
    full = files_for_result(result, formats=("png",), png_dpi=90)
    assert {"report.html", "extended_report.html", "summary.pdf", "results.xlsx", "run.json", "config.json"} <= set(
        full
    )
    assert all(name + ".csv" in full for name in result.tables)
    assert json.loads(full["run.json"])["software_version"] == "0.5.2"


def test_real_ui_starter_upload_and_import_change_clear_stale_downloads():
    app = Path(__file__).resolve().parents[1] / "app.py"
    at = AppTest.from_file(str(app), default_timeout=60).run()
    at.radio(key="data_mode").set_value("Upload a table").run()
    at.file_uploader(key="input_file").set_value(("starter.csv", starter_bytes("csv"), "text/csv")).run()
    assert not at.exception
    at.button(key="run_analysis").click().run()
    assert not at.exception and not at.error
    assert "analysis_result" in at.session_state
    assert len(json.loads(at.session_state["analysis_files"]["primary_catalog.json"])) <= 2
    at.selectbox(key="decimal").set_value(",").run()
    assert "analysis_result" not in at.session_state
    assert "result_archive" not in at.session_state


@pytest.mark.parametrize("budgets", [[], [0], [0, 1, 2]])
def test_baseline_only_and_small_correction_budgets(budgets):
    result = analyse_starter(budgets=budgets)
    methods = set(result.tables["predictions"].method)
    assert {"source_mean", "source_pls"} <= methods
    if max(budgets or [0]) == 0:
        assert methods == {"source_mean", "source_pls"}
    if 1 in budgets:
        assert "bias_correction" in methods


def test_target_fit_eligibility_does_not_depend_on_source_fit():
    frame = starter_frame()
    frame.loc[frame.Condition.eq("Source"), "Signal"] = 1.0
    result = analyse_starter(frame, budgets=[4])
    methods = set(result.tables["predictions"].method)
    assert "source_mean" in methods and "source_pls" not in methods
    assert "target_recalibration" in methods
    assert not result.tables["standards"].standard_group.isna().any()


def test_two_source_units_keep_source_mean_held_out():
    frame = starter_frame().head(4)
    result = analyse_starter(frame, budgets=[])
    assert set(result.tables["predictions"].method) == {"source_mean"}
    for row in result.tables["predictions"].itertuples():
        assert np.isfinite(row.prediction)


def test_empty_input_does_not_invent_measurements():
    with pytest.raises(InputError, match="observation"):
        analyse_starter(starter_frame().iloc[:0])


def test_bad_default_workbook_sheet_does_not_hide_worksheet_selector():
    book = Workbook()
    book.active.title = "Data"
    book.active.append(["a", "b"])
    book.active.append([1, "=A2"])
    useful = book.create_sheet("Measurements")
    useful.append(list(starter_frame().columns))
    for row in starter_frame().itertuples(index=False, name=None):
        useful.append(list(row))
    stream = io.BytesIO()
    book.save(stream)
    app = Path(__file__).resolve().parents[1] / "app.py"
    at = AppTest.from_file(str(app), default_timeout=60).run()
    at.radio(key="data_mode").set_value("Upload a table").run()
    at.file_uploader(key="input_file").set_value(
        ("sheets.xlsx", stream.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    ).run()
    assert not at.exception
    assert at.error
    at.selectbox(key="import_sheet").set_value("Measurements").run()
    assert not at.exception and not at.error
    assert at.button(key="run_analysis")
