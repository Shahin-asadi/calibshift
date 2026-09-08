# Maintainer instructions

- Read METHODS.md, DIAGNOSTICS.md and DATA_SOURCES.json before changing scientific behavior.
- Install dev tools: `python -m pip install -c constraints.txt -e ".[dev]"`.
- Check: `python -m ruff check src tests scripts`; `python -m ruff format --check src tests scripts`; `python -m pytest`; `python -m build`.
- Example: `calibshift demo --output runs/review_demo` (new directory required).
- Keep all fitted preprocessing and tuning within the appropriate training groups. Unknown references are not training labels. Descriptive diagnostics must not change model fitting or silently remove observations.
- Preserve unit invariance, ID normalization, pairing, cohort/coverage accounting, explicit independence and prediction-origin declarations, and unavailable-state explanations.
- Do not import private manuscripts/data, copy unlicensed code, or present mathematical fixtures as measurements. Packaged public fixtures retain CC BY 4.0 attribution.
- Run applicable tests after substantive changes; listing commands is not evidence that they ran. Rebuild benchmark outputs when their computation changes.
- Do not publish, push, create releases, or change account/visibility settings without an explicit user request for that action.
