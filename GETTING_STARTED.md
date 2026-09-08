# Getting started

Open the [web app](https://calibshift.streamlit.app/) in your browser. For local processing on Windows, install Python 3.12 or 3.14, download and extract the complete repository, and double-click `START_WINDOWS.cmd`. The first launch installs dependencies. Online uploads are processed on the hosting server; use the local installation for confidential measurements.

## Import and run

Start with a bundled example, or upload CSV/XLSX or paste a table. Select the worksheet, header row and decimal convention as needed. Map measurement columns and physical specimen/validation groups using their actual scientific roles. Review the input preview, then click **3. Run analysis**. Missing measurements can limit individual analyses; read the capability reasons instead of treating missing results as zero. See [Input guide](INPUT_GUIDE.md) for examples.

## Read the result

Use **Results page** to move between the overview and scientific sections. Each section places related plots and full tables together with interpretation guidance. Overview selectors change the selected evidence view; detailed sections retain their explicitly labelled methods and populations. Navigation does not fit the model again. **All tables** includes every calculated table, and **Run details** records configuration, input mapping and limitations.

## Download

- **Detailed report (HTML):** a self-contained report that opens offline.
- **Detailed report (PDF):** a paginated print report; large tables have labelled excerpts.
- **Key results ZIP:** extract it and read `START_HERE.txt`. Reports, full report tables, figures and scoring-cohort records are in numbered folders.
- **Advanced complete archive:** all predictions, configuration and reproducibility outputs; start with `START_HERE.html`.

Full table values remain available in the app and CSV exports. Short overview reports remain available separately. Input/configuration changes clear stale results; run the analysis again before downloading. Scientific support and conditional inference are described in [Methods](METHODS.md); environment evidence is in [Validation](VALIDATION.md).
