# Recorded GitHub Actions result

Observed in Chrome on 2026-09-08: [scientific-checks run 34271537322](https://github.com/Shahin-asadi/calibshift/actions/runs/34271537322) shows **Success**, with four completed jobs and four evidence artifacts.

- Repository: `Shahin-asadi/calibshift`
- Exact commit: `705aed20833c23cb8cb76adc81427a0bfacbc9b1`
- Matrix: `ubuntu-latest` / `windows-latest`, each with Python `3.12` / `3.14`.
- Workflow: dependency installation, `pip check`, Ruff lint/format, complete pytest suite, package build and installed-package smoke script.

This is evidence for that committed snapshot. Exact resolved runner/interpreter/dependency versions and test counts belong to its logs/artifacts; they are not inferred from the matrix labels. CI is not an interactive browser-hosting test, native macOS validation or independent scientific validation.

The earlier local closeout records correctly marked remote CI and local Linux as NOT_RUN at that time. This later cloud-run observation adds evidence without changing those historical records. The README badge links to current workflow status rather than embedding a permanent PASS label.
