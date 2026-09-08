import importlib
import io
import zipfile
from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_section_reader_and_detailed_exports_preserve_finished_result(monkeypatch):
    at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=90).run()
    at.button(key="run_analysis").click().run()
    assert not at.exception
    result = at.session_state["analysis_result"]
    before = result.tables["predictions"].copy(deep=True)

    def forbidden_refit(*args, **kwargs):
        raise AssertionError("Reading results must not refit")

    monkeypatch.setattr(importlib.import_module("calibshift.core"), "analyse", forbidden_refit)
    pages = at.radio(key="reader_page").options
    for page in pages:
        at.radio(key="reader_page").set_value(page).run()
        assert not at.exception, page
    assert result.tables["predictions"].equals(before)
    exports = at.session_state["reader_exports"]
    html = exports["html"]()
    assert b"data:image/png;base64," in html
    pdf = exports["pdf"]()
    assert pdf.startswith(b"%PDF")
    with zipfile.ZipFile(io.BytesIO(exports["key_zip"]())) as archive:
        names = archive.namelist()
        assert "START_HERE.txt" in names
        assert any(n.startswith("02_TABLES/") for n in names)
        assert "01_REPORTS/analysis_report.pdf" in names
    at.radio(key="data_mode").set_value("Upload a table").run()
    assert "reader_exports" not in at.session_state
