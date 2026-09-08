import numpy as np
import pandas as pd
import pytest

from calibshift.cli import example_path
from calibshift.common import InputError, read_table
from calibshift.core import analyse


def shifted_calibration():
    rows = []
    for i in range(8):
        for domain, shift in [("source", 0), ("target", 3)]:
            rows.append(
                {
                    "sample_id": f"{domain}{i}",
                    "group": str(i),
                    "domain": domain,
                    "target": 2 * i + 5.0,
                    "NIR__x": i + shift,
                }
            )
    return pd.DataFrame(rows)


def test_known_additive_shift_is_removed_without_test_standards():
    result = analyse(shifted_calibration(), source="source", budgets=(2, 4))
    pred = result.tables["predictions"]
    np.testing.assert_allclose(pred[pred.method.eq("source_pls")].residual, 6.0, atol=1e-10)
    np.testing.assert_allclose(pred[pred.method.eq("bias_correction")].residual, 0.0, atol=1e-10)
    standards = result.tables["standards"]
    for _, row in standards.iterrows():
        assert row.standard_group != row.fold.split(":")[-1]


def test_changed_held_out_reference_cannot_change_its_prediction():
    data = shifted_calibration()
    first = analyse(data, source="source")
    data.loc[data.group.eq("0"), "target"] += 100
    second = analyse(data, source="source")
    np.testing.assert_allclose(
        first.tables["predictions"].query("group == '0'").prediction,
        second.tables["predictions"].query("group == '0'").prediction,
        atol=1e-10,
    )


def test_inconsistent_formulation_responses_are_rejected():
    data = shifted_calibration()
    data.loc[0, "target"] += 1
    with pytest.raises(InputError, match="vary"):
        analyse(data, source="source")


def test_public_temperature_three_directions_and_missing_target_reference():
    data = read_table(example_path())
    result = analyse(data)
    assert set(result.tables["scores"].destination) == {"X2", "X3", "X4"}
    assert result.tables["scores"].n.min() == 9
    data.loc[data.domain.eq("X4"), "target"] = np.nan
    incomplete = analyse(data)
    x4 = incomplete.tables["predictions"].query("destination == 'X4'")
    assert x4.reference.notna().all() and x4.prediction.notna().all()
    np.testing.assert_allclose(result.tables["predictions"].query("destination == 'X4'").prediction, x4.prediction)
    linked = incomplete.tables["aggregated_input"].query("domain == 'X4'")
    assert linked.reference_linked_from_source.all()


def test_unknown_formulation_is_unscored_and_empty_features_are_rejected():
    data = shifted_calibration()
    data.loc[data.group.eq("0"), "target"] = np.nan
    result = analyse(data, source="source")
    held = result.tables["predictions"].query("group == '0'")
    assert held.reference.isna().all() and held.prediction.notna().all()
    assert result.status == "partial"
    with pytest.raises(InputError, match="feature"):
        analyse(data, source="source", feature_columns=[])


def test_missing_spectra_leave_common_cohort_and_coverage_explicit():
    data = shifted_calibration()
    data.loc[data.domain.eq("target") & data.group.isin(["0", "1", "2", "3"]), "NIR__x"] = np.nan
    result = analyse(data, source="source", budgets=(2, 4))
    assert set(result.tables["scores"].cohort) == {"all_available_rows", "common_scored_rows"}
    assert result.tables["scores"].n.max() == 4
    assert "insufficient paired target standards" in set(result.tables["splits"].status.dropna())
