# Resolved configuration

The interface exports `config.json` using the same validated arguments as `calibshift.core.analyse`. The CLI accepts it with `--config`. Unknown keys, duplicate selections, contradictory column roles and incorrectly typed Boolean/count fields are rejected. Use JSON `true`/`false`, not quoted strings; a Boolean is not a standard budget or grid count.

This is the bundled default. For a different or modified table, use provenance `{"kind":"user_provided"}`; bundled attribution is only accepted when the parsed table matches the packaged example exactly.

```json
{
  "input_name": "temperature_transfer.csv",
  "column_metadata": {
    "target": {
      "label": "Acetaminophen content",
      "unit": "% w/w"
    }
  },
  "provenance": {
    "kind": "bundled_example",
    "example": "temperature_transfer.csv"
  }
}
```

After execution, inferred features, blocks, destination lists and defaults are resolved into explicit arguments. `input_name` retains only the filename. `column_metadata` maps actual headers to `label` and `unit` strings. Declared units are descriptions, not conversion instructions. `run.json` records computational completion separately from evidence availability, the schema/software versions, parsed-table checksum, Python-source checksum, deterministic protocol and environment. Original file bytes and normalized table bytes are different identities.

The source checksum hashes sorted relative Python paths and file bytes, with a NUL separator after each. It is reproducible from an installed wheel and does not invent a Git commit. Creation time is informational and is excluded from numerical comparisons.

The UI exports import_options beside core arguments. The CLI passes these to the shared importer before analysis. Python callers can pass sheet, header_row, decimal, missing_tokens and header_overrides to read_table. INPUT_GUIDE.md describes roles and METHODS.md describes eligible small-data routes.

Analysis configuration uses schema 1.2. Display choices are separate: `summary_view.json` records method, response, destination, budget and evidence scope; changing them does not change fitted parameters. `summary_cohort.csv` records primary figure/score membership. API-specific table semantics are defined once in METHODS.md.
