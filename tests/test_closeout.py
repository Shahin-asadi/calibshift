"""Closeout regressions: report selection, cohort traces and export boundaries."""

import io
import json
from unittest.mock import patch

import pandas as pd

from calibshift import core, templates
from calibshift.presentation import select_view
from calibshift.reporting import files_for_result, summary_files


def test_summary_real_paragraphs_and_traceable_view():
    result = core.analyse(templates.starter_frame(), **templates.schema()["config"])
    with patch.object(core, "analyse", side_effect=AssertionError("Viewing must not refit")):
        output = summary_files(result)
        text = output["summary.txt"].decode("utf-8")
        assert "\n\n" in text and r"\n" not in text
        view = json.loads(output["summary_view.json"])
        cohort = pd.read_csv(io.BytesIO(output["summary_cohort.csv"]))
        assert cohort.included_in_primary_score_and_figure.sum() == view["n_primary_pairs"]


def test_stale_selection_resolves_and_zip_summary_matches():
    result = core.analyse(templates.starter_frame(), **templates.schema()["config"])
    default = select_view(result)
    stale = select_view(result, method="removed", domain="removed", response="removed", budget=9999)
    for key in ["method", "domain", "response", "budget", "scope"]:
        assert stale[key] == default[key]
    selection = {k: default[k] for k in ["method", "domain", "response", "budget"]}
    full = files_for_result(result, formats=("png",), png_dpi=70, **selection)
    assert json.loads(full["summary_view.json"])["scope"] == default["scope"]
    assert full["summary.txt"] == summary_files(result)["summary.txt"]


def test_all_domains_and_budgets_use_recorded_common_membership():
    result = core.analyse(templates.starter_frame(), **templates.schema()["config"])
    for domain, part in result.tables["predictions"].groupby("destination"):
        for (method, budget), subset in part.groupby(["method", "budget"]):
            view = select_view(result, domain=domain, method=method, budget=budget)
            if view["method"] != method or view["budget"] != budget:
                continue
            expected = set(subset.loc[subset.in_common_cohort, "group"])
            assert set(view["predictions"].group) == expected
            assert int(view["scores"].iloc[0]["n"]) == len(expected)
