# Validation — 0.5.2

## Results reader checks — 2026-09-09

Windows / Python 3.14.7: **82 tests passed**, including section navigation without refitting, detailed HTML/PDF/ZIP generation and stale-download reset. Ruff lint and formatting passed. [JUnit cases](validation/results_reader/pytest.xml) and [environment/source fingerprints](validation/results_reader/checks.json) identify the tested snapshot. Wheel and source Python modules matched. These changes have not yet been checked by remote CI or tested under production cloud load.

## Historical 0.5.2 baseline

The records below describe historical tested snapshots; current CI status is linked from the README.

The complete suite passed **80 tests on Windows Python 3.12.14** and **80 tests on Windows Python 3.14.7**, with actual Streamlit 1.63.0. Both final runs checked an unchanged Python-source/test/configuration snapshot. [Machine-readable evidence](validation/record.json) identifies each run and its full JUnit record. Across the four tools this is 351 tests per interpreter, not 702 independent validations.

All four final wheel/sdist pairs built. Each wheel was installed with runtime dependencies into its own genuinely new Windows Python 3.14 environment without system site packages. `pip check`, imports outside the checkout, installed Python-byte comparison, all seven bundled CLI examples and all four CLI starters passed. The numerical comparison covers 99 original CSV tables, preserving their existing numeric fields within rtol 1e-9 / atol 1e-10 after documented schema mapping. No tolerance was loosened to pass a failure. Unfavourable fusion and target recalibration remain present.

Real installed Chrome 152.0.7977.76 ran in isolated headless profiles on this Windows computer. CSV, non-first-sheet XLSX, pasted data, edge cases, malformed numbers, complete downloads and a fresh 430-pixel viewport were exercised. Downloaded HTML/PDF/ZIP and selected-view/cohort records were checked after the view finished updating. An AppTest regression also prevents refitting during view changes. Browser tests use genuine Streamlit, not substitutes.

The representative native Windows PowerShell 5.1 launcher route was freshly installed in a path containing spaces and Persian characters, checked offline, and started successfully with an HTTP health response. This patch repeats that native launch for SenseFusion; the other native-launch cases in the separate historical evidence belong to 0.5.1. All four current tools have fresh wheel, CLI and browser evidence. No native macOS check is claimed.

The seven actual installed-example PDFs have one page each. Normal and DejaVu Serif fallback reports were rendered for the examples, starters, small/partial inputs and long labels, including plots using the fallback. All pages were inspected. Three long-label fallback cases use a useful second page with a complete figure; no footer-only trailing page is accepted. Standalone HTML was checked with network access disabled.

At the local closeout, Linux, macOS, Python 3.13 and remote GitHub Actions were **NOT_RUN**. Subsequent owner-triggered GitHub Actions completed successfully on Ubuntu and Windows with Python 3.12 and 3.14; [CI_STATUS.md](CI_STATUS.md) records the exact published commit and run. This adds cloud CI evidence, not hosted-app or native Linux browser evidence. WSL is not installed and Docker is unavailable on this host. The tested-support claim is limited to the recorded Windows routes. The independently supplied Linux 3.13.5 audit concerns the original 0.5.1: 273 non-UI passes and 30 unrun UI cases. Its wheel installation reused dependencies and was not a fresh isolated install. Those records are retained as historical evidence, not passes for this patch.

Historical test records remain under validation/historical_v051. Verification was executed during development with Codex assistance; DECLARATION.md remains the attribution record. Local evidence does not certify unseen measurements or establish external adoption.
