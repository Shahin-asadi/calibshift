import io
import json

import numpy as np
import pandas as pd
import pytest

from calibshift import core
from calibshift.cli import example_config, example_context, example_path
from calibshift.common import InputError, read_table
from calibshift.reporting import files_for_result


def test_resolved_configuration_and_portable_public_attribution():
    path = example_path()
    data = read_table(path)
    a = core.analyse(data, **(example_config(path.name) | example_context(path.name)))
    files = files_for_result(a)
    config = json.loads(files["config.json"])
    b = core.analyse(data, **config)
    assert a.settings["input_sha256"] == b.settings["input_sha256"]
    assert json.loads(files["run.json"])["software_version"] == "0.5.2"
    assert json.loads(files["provenance.json"])["original_source"]["license"] == "CC-BY-4.0"
    assert b.settings["provenance"]["kind"] == "bundled_example"
    assert "created_utc" not in config
    for key, table in a.tables.items():
        pd.testing.assert_frame_equal(table, b.tables[key], check_exact=False, rtol=1e-7, atol=1e-9)


def test_uploaded_data_does_not_inherit_bundled_citation():
    path = example_path()
    data = read_table(path)
    result = core.analyse(data, **example_config(path.name))
    assert result.settings["provenance"]["kind"] == "user_provided"
    assert "original_source" not in result.settings["provenance"]


def test_nonobject_cli_config_returns_clear_failure(tmp_path, capsys):
    from calibshift.cli import main

    file = tmp_path / "bad.json"
    file.write_text("[1,2]")
    assert main(["demo", "--config", str(file), "--output", str(tmp_path / "out")]) == 2
    assert "top level must be an object" in capsys.readouterr().err


def test_duplicate_xlsx_headers_are_rejected():
    frame = pd.DataFrame([["id", "x", "x"], ["001", 1, 2]])
    source = io.BytesIO()
    frame.to_excel(source, index=False, header=False)
    source.seek(0)
    with pytest.raises(InputError, match="unique"):
        read_table(source, "duplicate.xlsx")


def test_html_escapes_untrusted_labels():
    from calibshift.common import Result
    from calibshift.reporting import html_report

    result = Result("<script>alert(1)</script>", notes=["<img src=x onerror=alert(1)>"])
    html = html_report(result, "<bad>", False)
    assert "<script>alert" not in html and "&lt;script&gt;" in html


def shifted():
    return pd.DataFrame(
        [
            {
                "sample_id": f"{d}{i}",
                "group": str(i),
                "domain": d,
                "target": 2.0 * i + 5,
                "NIR__x": float(i) + (3 if d == "T" else 0),
            }
            for i in range(8)
            for d in ["S", "T"]
        ]
    )


def test_target_recalibration_uses_same_budget_and_excludes_held_group():
    r = core.analyse(shifted(), source="S", budgets=[2, 4])
    predictions = r.tables["predictions"]
    recal = predictions.query("method == 'target_recalibration'")
    assert set(recal.budget) == {4}
    np.testing.assert_allclose(recal.residual, 0, atol=1e-9)
    for _, row in r.tables["splits"].query("method == 'target_recalibration' and budget == 4").iterrows():
        standards = set(r.tables["standards"].query("fold == @row.fold and budget == 4").standard_group)
        assert set(row.training_standard_groups.split(";")) == standards
        assert row.fold.split(":")[-1] not in standards


@pytest.mark.parametrize("scale", [1e-12, 1e-9, 1e6])
def test_transfer_unit_invariance_and_stable_reference_tolerance(scale):
    data = shifted()
    a = core.analyse(data, source="S")
    data["target"] *= scale
    b = core.analyse(data, source="S")
    np.testing.assert_allclose(
        a.tables["predictions"].prediction, b.tables["predictions"].prediction / scale, rtol=1e-8, atol=1e-9
    )
    data.loc[0, "target"] += scale
    with pytest.raises(InputError, match="vary"):
        core.analyse(data, source="S")


def test_missing_target_spectra_and_impossible_budget_are_explicit():
    data = shifted()
    data.loc[data.domain.eq("T"), "NIR__x"] = np.nan
    assert core.analyse(data, source="S").status == "audit_only"
    r = core.analyse(shifted(), source="S", budgets=[20])
    assert r.status == "partial"
    assert r.tables["splits"].status.str.contains("insufficient").any()
