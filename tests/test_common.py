import io

import numpy as np
import pandas as pd
import pytest

from calibshift.common import (
    BlockPLS,
    InputError,
    folds,
    identifiers,
    metrics,
    numbers,
    read_table,
)


def test_scaling_is_training_only_and_has_unit_total_variance():
    train = np.array([[1.0, 10.0, np.nan], [2.0, 20.0, np.nan], [4.0, np.nan, np.nan], [8.0, 80.0, np.nan]])
    model = BlockPLS(1).fit([train], np.array([1.0, 2.0, 3.0, 4.0]))
    transformed = model.transform([train])
    assert transformed.shape == (4, 2)
    assert np.sum(np.var(transformed, axis=0, ddof=1)) == pytest.approx(1.0)
    before = model.transforms_[0][1].copy()
    model.predict([np.array([[999999.0, np.nan, 800.0]])])
    np.testing.assert_array_equal(model.transforms_[0][1], before)
    assert before[1] == 20


def test_group_splits_are_disjoint_and_cover_each_observation_once():
    groups = np.repeat(["a", "b", "c", "d", "e", "f"], [2, 3, 1, 4, 2, 1])
    tests = []
    for train, test in folds(groups):
        assert not set(groups[train]) & set(groups[test])
        tests.extend(test)
    assert sorted(tests) == list(range(len(groups)))


def test_constant_reference_has_no_r_squared_and_remains_finite():
    x = np.arange(12.0).reshape(6, 2)
    y = np.full(6, 3.0)
    model = BlockPLS(3).fit([x], y)
    np.testing.assert_allclose(model.predict([x]), y)
    assert metrics(y, y)["r2"] is None


def test_non_numeric_and_infinite_values_are_not_silently_imputed():
    for values in [["high", "1"], [np.inf, 1]]:
        with pytest.raises(InputError):
            numbers(pd.DataFrame({"x": values}), ["x"])


def test_ids_are_physical_keys_not_row_positions():
    with pytest.raises(InputError, match="repeat"):
        identifiers(pd.DataFrame({"id": ["a", "a"]}), "id")
    with pytest.raises(InputError, match="blank"):
        identifiers(pd.DataFrame({"id": ["a", None]}), "id")


def test_delimited_upload_and_group_weighted_error():
    frame = read_table(io.StringIO("id;value\na;1\nb;2\n"), "table.csv")
    assert frame.columns.tolist() == ["id", "value"]
    score = metrics([0, 0, 0], [2, 2, 0], ["a", "a", "b"])
    assert score["group_rmse"] == pytest.approx(np.sqrt(2))
    assert score["rmse"] == pytest.approx(np.sqrt(8 / 3))


@pytest.mark.parametrize("extension", ["csv", "xlsx"])
def test_uploaded_ids_preserve_leading_zeroes_and_literal_na(extension):
    source = pd.DataFrame({"id": ["001", "NA"], "value": ["1", " "]})
    if extension == "csv":
        buffer = io.BytesIO(source.to_csv(index=False).encode())
    else:
        buffer = io.BytesIO()
        source.to_excel(buffer, index=False)
        buffer.seek(0)
    frame = read_table(buffer, f"table.{extension}")
    assert frame.id.tolist() == ["001", "NA"]
    assert frame.value.isna().sum() == 1


def test_duplicate_original_csv_headers_are_rejected_before_pandas_renames_them():
    with pytest.raises(InputError, match="unique"):
        read_table(io.StringIO("id,x,x\na,1,2\nb,3,4\n"), "table.csv")
