# Contributing

For a reproducible issue, record the software/Python versions, resolved settings, expected and observed behavior, and the smallest shareable input that demonstrates the problem. Remove private measurements and personal information before sharing. Include the relevant diagnostic table and traceback if one occurred.

Install development tools with `python -m pip install -c constraints.txt -e ".[dev]"`, then run `python -m ruff check src tests scripts`, `python -m ruff format --check src tests scripts`, and `python -m pytest`. A scientific correction should include a test of the mathematical property or held-out-data boundary it changes; never tune a test merely to make a preferred method win.

Keep schemas, public examples, reports and documentation consistent. Preserve source attribution and data licensing. Shared helper changes must be reviewed across all four repositories before being copied. Record substantive contributions in the development declaration when performed.
