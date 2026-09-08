# Reproducing an analysis

Install runtime dependencies with `python -m pip install -c constraints.txt -e .`. Developer tools are separate: `python -m pip install -c constraints.txt -e ".[dev]"`. Exact environment versions from the review are in the validation record; constraints fix direct tested dependencies, while dependency resolvers may select newer transitive packages later.

Run `calibshift demo --output runs/demo`, or choose an example using `--example` and the CSV filename in `src/calibshift/project.json`. All analysis, diagnostics, figure captions and reports derive from one result object. Repeating a run with identical parsed input and resolved configuration preserves the scientific calculation; timestamps, archive metadata and backend floating-point details need not be byte-identical.

`scripts/reproduce_examples.py --raw-dir PATH --output NEW_FOLDER` rebuilds the bundled processed CSVs from checksum-verified original source files. Add `--download` only to explicitly fetch missing public originals. The four versioned deposits are CC BY 4.0; raw downloads are not needed for ordinary bundled use. Preserve grouping, pairing and documented aggregation when using a different dataset.

For comparison, align observation IDs, method/budget/condition keys and cohorts first. The controlled 0.5.2 Windows comparison retains rtol=1e-9 and atol=1e-10 for common numeric fields in all 99 original CSV tables, with candidate-column schema mapping recorded explicitly. No model-fitting numbers changed to improve a result or force agreement. Missing legacy metadata fields and new cohort flags are documented schema changes.

The supplied independent 0.5.1 Linux audit compared 99 tables: all shapes, column names and text fields matched, while 89 met that numerical tolerance and 10 differed by up to 1.0538148664807068e-7 under its different environment. That historical result is not byte-identical cross-platform output and does not validate Linux for this patch. Record Python, library and BLAS versions when comparing another environment; justify any numerical tolerance for the particular computation.

No remote CI execution is claimed before upload. Shared internal helpers are duplicated so each repository runs independently; their common ancestry is documented in [Third-party notices](THIRD_PARTY_NOTICES.md).
