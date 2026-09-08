"""Shared numerical infrastructure, vendored into each independent package."""

import hashlib
import json
import platform
from dataclasses import dataclass, field
from importlib.metadata import PackageNotFoundError, version

import numpy as np
import pandas as pd
from sklearn.cross_decomposition import PLSRegression
from sklearn.model_selection import GroupKFold


class InputError(ValueError):
    """An input problem that can be explained without a traceback."""


@dataclass
class Result:
    title: str
    tables: dict = field(default_factory=dict)
    notes: list = field(default_factory=list)
    settings: dict = field(default_factory=dict)
    status: str = "complete"


def read_table(source, filename=None, **options):
    from .importing import read_table as parse_table

    return parse_table(source, filename, **options)


def numbers(frame, columns):
    from .importing import numeric_columns

    return numeric_columns(frame, columns)


def identifiers(frame, id_col, group_col=None):
    if id_col not in frame:
        raise InputError("Select a column containing one unique observation ID per row.")
    ids = frame[id_col]
    if ids.isna().any() or ids.astype(str).str.strip().eq("").any():
        raise InputError("Observation IDs cannot be blank.")
    ids = ids.astype(str).str.strip().to_numpy()
    if len(set(ids)) != len(ids):
        raise InputError(
            "Observation IDs repeat. Give each acquisition a unique row ID and use a separate group column for the physical sample."
        )
    if group_col:
        if (
            group_col not in frame
            or frame[group_col].isna().any()
            or frame[group_col].astype(str).str.strip().eq("").any()
        ):
            raise InputError("Every row needs a physical sample/batch ID in the selected group column.")
        groups = frame[group_col].astype(str).str.strip().to_numpy()
    else:
        groups = ids.copy()
    return ids, groups


def audit(frame):
    return pd.DataFrame(
        {
            "column": frame.columns,
            "missing_cells": frame.isna().sum().to_numpy(),
            "observed_cells": frame.notna().sum().to_numpy(),
            "unique_observed": [frame[c].nunique(dropna=True) for c in frame],
        }
    )


def fingerprint(frame):
    return hashlib.sha256(frame.to_csv(index=False, lineterminator="\n").encode("utf-8")).hexdigest()


def environment():
    names = ["numpy", "pandas", "scipy", "scikit-learn", "matplotlib", "streamlit"]
    versions = {}
    for name in names:
        try:
            versions[name] = version(name)
        except PackageNotFoundError:
            versions[name] = "not installed"
    return {
        "python": platform.python_version(),
        "platform": platform.system(),
        "architecture": platform.machine(),
        **versions,
    }


def folds(groups, max_folds=5):
    count = len(np.unique(groups))
    if count < 2:
        raise InputError("At least two independent groups are needed for held-out evaluation.")
    return list(GroupKFold(n_splits=min(max_folds, count)).split(np.zeros(len(groups)), groups=groups))


def stable_rms(values):
    """RMS with normalization before squaring; zero remains exactly zero."""
    values = np.asarray(values, float)
    scale = float(np.max(np.abs(values))) if values.size else 0.0
    return scale * float(np.sqrt(np.mean((values / scale) ** 2))) if scale else 0.0


def metrics(y, prediction, groups=None):
    """Available-pair errors; dimensionless R2 uses response spread, not units.

    Nonfinite pairs are omitted. R2 is unavailable only for an exactly constant
    finite reference (including all-zero); negative R2 is retained. Inputs whose
    subtraction overflows float64 must be expressed in a numerically smaller unit.
    """
    y, prediction = np.asarray(y, float), np.asarray(prediction, float)
    if y.ndim != 1 or y.shape != prediction.shape:
        raise InputError("Reference and prediction must be equal-length one-dimensional arrays.")
    if groups is not None and len(groups) != len(y):
        raise InputError("groups must contain one ID for each reference/prediction pair.")
    valid = np.isfinite(y) & np.isfinite(prediction)
    n_total = int(np.isfinite(y).sum())
    if not valid.any():
        return {
            "n": 0,
            "n_groups": 0,
            "coverage": 0.0,
            "rmse": None,
            "mae": None,
            "bias": None,
            "r2": None,
            "group_rmse": None,
        }
    residual = prediction[valid] - y[valid]
    centred = y[valid] - y[valid][0]
    centred -= centred.mean()
    if not np.isfinite(residual).all() or not np.isfinite(centred).all():
        raise InputError("Numeric range exceeds float64 subtraction; rescale reference and prediction units together.")
    spread = float(np.max(np.abs(centred)))
    r2 = float(1 - np.sum((residual / spread) ** 2) / np.sum((centred / spread) ** 2)) if spread else None
    group_rmse = None
    selected_groups = np.asarray(groups)[valid] if groups is not None else np.arange(valid.sum())
    if groups is not None:
        group_rms = [stable_rms(residual[selected_groups == group]) for group in np.unique(selected_groups)]
        group_rmse = stable_rms(group_rms)
    return {
        "n": int(valid.sum()),
        "n_groups": len(np.unique(selected_groups)),
        "coverage": float(valid.sum() / n_total) if n_total else 0.0,
        "rmse": stable_rms(residual),
        "mae": float(np.mean(abs(residual))),
        "bias": float(residual.mean()),
        "r2": r2,
        "group_rmse": group_rmse,
    }


class BlockPLS:
    """Median imputation and total-variance block weights learned on training rows."""

    def __init__(self, components=2):
        self.components = components

    def fit(self, blocks, y):
        y = np.asarray(y, float)
        if not np.isfinite(y).all() or len(y) < 2:
            raise InputError("Model training needs at least two measured, finite responses.")
        self.mean_y_ = float(y[0] + (y - y[0]).mean())
        self.response_scale_ = float(np.max(np.abs(y - self.mean_y_)))
        if not np.isfinite(self.response_scale_):
            raise InputError("Response range exceeds float64 arithmetic; use a smaller numerical unit.")
        self.transforms_ = []
        transformed = []
        for block in blocks:
            block = np.asarray(block, float)
            keep = np.isfinite(block).any(axis=0)
            reduced = block[:, keep]
            if reduced.shape[1] == 0:
                self.transforms_.append((keep, np.array([]), np.array([]), 1.0))
                continue
            medians = np.nanmedian(reduced, axis=0)
            complete = np.where(np.isnan(reduced), medians, reduced)
            means = complete.mean(axis=0)
            centred = complete - means
            magnitude = float(np.max(np.abs(centred)))
            divisor = magnitude * np.sqrt(np.sum((centred / magnitude) ** 2) / (len(y) - 1)) if magnitude else 1.0
            self.transforms_.append((keep, medians, means, divisor))
            transformed.append((complete - means) / divisor)
        self.model_ = None
        self.n_components_ = 0
        if transformed and self.response_scale_ > 0:
            x = np.column_stack(transformed)
            rank = np.linalg.matrix_rank(x)
            self.n_components_ = min(self.components, rank, len(y) - 1, x.shape[1])
            if self.n_components_ > 0:
                self.model_ = PLSRegression(n_components=self.n_components_, scale=False, max_iter=1000)
                self.model_.fit(x, (y - self.mean_y_) / self.response_scale_)
        return self

    def transform(self, blocks):
        if len(blocks) != len(self.transforms_):
            raise InputError("Prediction blocks must match the training blocks.")
        pieces = []
        for block, (keep, medians, means, divisor) in zip(blocks, self.transforms_):
            block = np.asarray(block, float)
            if block.shape[1] != len(keep):
                raise InputError("Prediction feature columns must match training columns and order.")
            if keep.any():
                x = block[:, keep]
                pieces.append((np.where(np.isnan(x), medians, x) - means) / divisor)
        return np.column_stack(pieces) if pieces else np.empty((len(blocks[0]), 0))

    def predict(self, blocks):
        x = self.transform(blocks)
        if self.model_ is None:
            return np.full(len(x), self.mean_y_)
        return self.mean_y_ + self.response_scale_ * self.model_.predict(x).ravel()


def tune_pls(blocks, y, groups, candidates=(1, 2, 3)):
    """Choose complexity only with grouped predictions from the supplied training set."""
    groups = np.asarray(groups)
    if len(np.unique(groups)) < 3:
        return 1
    scored = []
    for count in candidates:
        predictions = np.full(len(y), np.nan)
        for train, test in folds(groups, 3):
            fitted = BlockPLS(count).fit([b[train] for b in blocks], y[train])
            predictions[test] = fitted.predict([b[test] for b in blocks])
        scored.append((metrics(y, predictions, groups)["group_rmse"], count))
    return min(scored)[1]


def subset(blocks, index):
    return [b[index] for b in blocks]


def clean_json(value):
    if isinstance(value, dict):
        return {str(k): clean_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean_json(v) for v in value]
    if isinstance(value, np.ndarray):
        return clean_json(value.tolist())
    if isinstance(value, (np.integer, np.floating)):
        value = value.item()
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def json_text(value):
    return json.dumps(clean_json(value), ensure_ascii=False, indent=2, allow_nan=False)
