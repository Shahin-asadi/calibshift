"""Processing-location disclosure for local and hosted use."""

from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_interface_explains_hosted_upload_processing():
    app = Path(__file__).resolve().parents[1] / "app.py"
    at = AppTest.from_file(str(app), default_timeout=30).run()
    assert not at.exception
    captions = " ".join(item.value for item in at.caption)
    assert "Online uploads are sent to that server" in captions
    assert "local installation for confidential measurements" in captions
    assert "No AI service or API key is used" in captions
    assert "LOCAL RESEARCH WORKBENCH" not in captions
