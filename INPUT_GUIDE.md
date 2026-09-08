# Prepare and use an ordinary table

1. Extract the complete repository. On Windows, double-click START_WINDOWS.cmd. The locally tested routes are Windows with Python 3.12 and 3.14; see VALIDATION.md for exact versions. Linux, macOS and Python 3.13 are not claimed as tested for this patch. The first launch installs runtime dependencies into a local .venv and needs internet.
2. Try Bundled example and 3. Run analysis. Read the Overview question, scientific metrics, units, main limitation and primary figures.
3. For your own measurements, choose Upload a table or Paste a table. Confirm the worksheet, header row and column roles. CSV, XLSX and pasted delimited text use the same parser.
4. Download concise HTML for a standalone view or PDF for printing. The optional extended bundle adds all eligible figures, vector exports, complete CSV/XLSX tables, provenance, input mapping and settings.

## Columns, worksheets and missing cells

Use one header row and one observation per row. The interface prefers a Data worksheet when present; confirm the selected sheet before analysis. Import options let you choose a different header row, repair duplicate or blank headers, select the decimal mark and declare missing tokens.

Artificial starter CSV/XLSX files explain roles. Replace every example row with real measurements. Their row count is not a sample-size recommendation. They are optional, unprotected and freely extensible. The XLSX has Data first and Instructions second; the blank-header download uses the same schema.

Labels with spaces, Unicode or numeric-looking names are accepted. Map recorded references, factors and measurement columns explicitly. Identifiers, specimen groups and acquisition conditions must not be predictors.

A unique row ID is optional. Generated internal keys identify source-row positions inside this parsed table only. They do not establish physical specimen identity or pair separate files. Physical specimen IDs group repeated readings; a separate validation batch keeps batches together during held-out prediction. Every specimen must belong to one validation group.

Blank measurements and declared tokens remain missing. Numeric conversion affects selected numeric roles only, preserving literal identifiers and zeroes. Eligible prediction models learn imputation from training data. Missing responses are never invented. Invalid numeric cells show examples and a corrective action. Uncached Excel formulas require recalculation and saving in Excel or LibreOffice; the tool does not evaluate formulas.

Default limits are 50 MB and two million declared cells. Clear distant blank workbook formatting or provide a smaller rectangular sheet if the limit is exceeded. Python callers can explicitly raise importer budgets after checking memory needs.

## Read and repeat the results

Overview contains at most two primary figures. Choose the displayed comparison changes the finished-run view without refitting. Diagnostics are generated after Prepare additional diagnostics. Tables contains complete tables and CSV downloads. Run details contains capabilities, assumptions and resolved configuration.

Execution status is separate from evidence strength. Optional diagnostic failures retain core tables and record their reason. Changing the input, parser, roles or analysis settings clears stale results and download callbacks.

Keep the original input and downloaded config.json. The CLI reads its import_options and analysis roles to repeat the run. Public example attribution is checked against the supplied parsed table and is never inferred for uploaded data.

## Troubleshooting

- Numeric error: correct the named cell, select its decimal mark, or declare its missing token.
- Duplicate row ID: use a truly unique ID or leave that role empty. Repeated physical specimens need a separate specimen column.
- Unestimable model: inspect model_support and capability reasons, then deliberately choose a supported simpler form or supply more independent information.
- Interrupted setup: rerun the launcher online. Rename an incomplete .venv before rebuilding it; preserve all input and result files.
- Occupied port: close your earlier tool session or run launch.ps1 -Port 8502. Do not stop unrelated processes.

Press Ctrl+C in the launcher terminal to stop the server. Use a new output directory for each command-line run. VALIDATION.md records actual checks and unrun platforms.

Operation-specific small-data rules are consolidated in [Methods](METHODS.md). There is no universal minimum row count. `summary_view.json` and `summary_cohort.csv` record the displayed selection and its evidence scope. The extended bundle preserves all predictions, including excluded or unscored rows.
