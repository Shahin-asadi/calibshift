import numpy as np
import pandas as pd
import pytest

from calibshift import core
from calibshift.common import BlockPLS, InputError, metrics


@pytest.mark.parametrize("scale", [1e-12, 1e-9, 1, 1e6])
def test_metric_units_are_invariant(scale):
    a = metrics([1, 2, 3], [1.1, 1.8, 3.1], ["a", "b", "c"])
    b = metrics(np.array([1, 2, 3]) * scale, np.array([1.1, 1.8, 3.1]) * scale, ["a", "b", "c"])
    assert b["r2"] == pytest.approx(0.97, abs=1e-12)
    for key in ["rmse", "mae", "bias", "group_rmse"]:
        assert b[key] / scale == pytest.approx(a[key], abs=1e-12)


@pytest.mark.parametrize("scale", [1e-12, 1e-9, 1e6])
def test_pls_response_and_predictor_units_roundtrip(scale):
    x = np.array([[1.0, 2], [2, 1], [3, 7], [4, 3], [6, 8], [8, 10]])
    y = np.array([1.0, 2, 3, 2, 7, 8])
    a = BlockPLS(2).fit([x], y).predict([x])
    b = BlockPLS(2).fit([x * scale], y * scale).predict([x * scale]) / scale
    np.testing.assert_allclose(a, b, rtol=1e-8, atol=1e-10)


def test_metrics_translation_negative_r2_and_missing_pairs():
    y = np.array([1.0, 2, 3])
    p = np.array([5.0, 6, 7])
    assert metrics(y, p)["r2"] < 0
    assert metrics(y + 100, p + 100)["r2"] == metrics(y, p)["r2"]
    assert metrics([0, 0], [0, 0])["r2"] is None
    assert metrics([np.nan, 1], [1, np.nan])["n"] == 0


def test_api_rejects_unknown_configuration_with_field_name():
    with pytest.raises(InputError, match="unknown_option"):
        core.analyse(pd.DataFrame(), unknown_option=True)


def shifted():
    return pd.DataFrame(
        [
            {
                "sample_id": f"{d}{i}",
                "specimen": str(i),
                "condition": d,
                "target": 2.0 * i + 5,
                "group": float(i) + (3 if d == "T" else 0),
            }
            for i in range(8)
            for d in ["S", "T"]
        ]
    )


def test_feature_named_group_does_not_collide_with_internal_key():
    r = core.analyse(shifted(), group_col="specimen", domain_col="condition", source="S", feature_columns=["group"])
    np.testing.assert_allclose(r.tables["predictions"].query("method == 'bias_correction'").residual, 0, atol=1e-10)


@pytest.mark.parametrize("budgets", [[True], [2, 2], [-1], [2.0], ["2"]])
def test_invalid_budget_types_are_actionable(budgets):
    with pytest.raises(InputError, match="budgets"):
        core.analyse(
            shifted(),
            group_col="specimen",
            domain_col="condition",
            source="S",
            feature_columns=["group"],
            budgets=budgets,
        )
