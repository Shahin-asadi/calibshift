# CalibShift

[![Scientific checks](https://github.com/Shahin-asadi/calibshift/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/Shahin-asadi/calibshift/actions/workflows/tests.yml)

[![Download code](docs/assets/download.svg)](https://github.com/Shahin-asadi/calibshift/archive/refs/heads/main.zip)
[![Run locally](docs/assets/start.svg)](WEB_ACCESS.md#run-the-app-on-your-computer)
[![Example report](docs/assets/example.svg)](benchmarks/reference_run/temperature_transfer/summary.pdf)
[![Streamlit hosting](docs/assets/hosting.svg)](https://share.streamlit.io/)

**Browser app:** start `START_WINDOWS.cmd` on Windows, then use the local address printed by the launcher (normally `http://127.0.0.1:8501`). The Streamlit hosting link opens the owner deployment dashboard; a direct live-app URL will be added after deployment. The Actions badge reports automated checks; it does not launch or host the app.

**How far can a source calibration be corrected with a limited number of target standards?**

For researchers comparing acquisition conditions, evaluate source calibration, source mean, bias correction, slope/intercept correction and target spectral recalibration on held-out formulations. Inspect the measurement budget, paired standards and extrapolation for each condition. Analysis runs on the computer or server hosting the app, without an AI service or API key. The local launcher keeps processing on your computer; an online deployment processes uploads on its server.

```mermaid
flowchart LR
    A["Formulation and domain IDs"] --> B["Leave one formulation out"] --> C["Fit source calibration"] --> D["Select paired target standards"] --> E["Correct or recalibrate"] --> F["Compare transfer error and standard coverage"]
```

![Computed temperature transfer example](benchmarks/reference_run/temperature_transfer/primary_comparison.png)

The figure uses the processed public measurements documented in [Data sources](DATA_SOURCES.json). It is an evaluated example, with its sample structure and limitations, rather than a claim of general laboratory performance. [Read the numerical results and diagnostic gallery](RESULTS.md).

## Start in three steps

1. Install Python **3.12 or 3.14** on Windows and extract the complete project folder.
2. On Windows, double-click **START_WINDOWS.cmd**. The first launch installs runtime dependencies into a local `.venv`; later launches can use the bundled examples offline.
3. Select a **Bundled example**, click **3. Run analysis**, then inspect **Overview**, **Diagnostics**, **Tables**, and **Run details**. Use the concise HTML/PDF report first; additional diagnostics and the extended bundle are available on request.

The [worked walkthrough](GETTING_STARTED.md) explains input preparation, missing values, supported calculations and troubleshooting. [Validation](VALIDATION.md) records the actual environments and remaining browser/CI limits. Version **0.5.2** has local verification and a recorded [successful CI run](https://github.com/Shahin-asadi/calibshift/actions/runs/34271537322). See [CI evidence](CI_STATUS.md) for its exact commit and scope, and [local hosting preparation](HOSTING_PREPARATION.md) for the subsequent uncommitted changes; a test pass does not establish hosting or independent scientific validation.

CSV, XLSX and pasted tables share one parser; row keys are optional. [Artificial starters](src/calibshift/starter_files/) explain the roles. Use [Input guide](INPUT_GUIDE.md) and [Methods](METHODS.md) for missing data and operation-specific support.

## What you receive

- A concise numerical overview with at most two primary figures. Additional diagnostics are optional and use the same fitted result.
- Individual 300 dpi PNG, vector PDF and editable SVG figures; a figure catalogue explains every view.
- Complete CSV tables and a formatted `results.xlsx` workbook with separate sheets.
- A navigable, printable `report.html`, resolved `config.json`, environment/run record, source-code fingerprint and applicable dataset attribution.

Unknown reference measurements are never fabricated. Incomplete inputs can yield partial evidence or an input audit; a successful computation is not a validation certificate. Figures and diagnostic flags do not silently remove observations or change model fitting.

## Command line

```text
python -m venv .venv
```

Activate that environment, then install the runtime only:

```text
python -m pip install -c constraints.txt -e .
calibshift demo --output runs/first_example
calibshift app
```

For your own table, export the configuration from the interface and run:

```text
calibshift analyse --input data.csv --config config.json --output runs/my_analysis
```

Choose a new or empty output directory so previous work is preserved. See [Configuration](CONFIGURATION.md), [Methods](METHODS.md), [Diagnostic guide](DIAGNOSTICS.md), [Data dictionary](DATA_DICTIONARY.md), [Reproducibility](REPRODUCIBILITY.md), and [References](REFERENCES.md).

Maintainer: [Shahin-asadi](https://github.com/Shahin-asadi). Code: MIT. Example measurements retain their original CC BY 4.0 attribution. [Development contributions](DECLARATION.md) · [Third-party notices](THIRD_PARTY_NOTICES.md) · [Contributing](CONTRIBUTING.md).
