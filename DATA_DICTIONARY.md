# Bundled data dictionary

| Field | Meaning |
|---|---|
| `sample_id` | Unique domain/formulation combination |
| `group` | One of nine physical acetaminophen formulation IDs |
| `domain` | Deposited acquisition subset X1, X2, X3 or X4 |
| `target` | Recorded acetaminophen concentration, % w/w |
| `NIR__*` | NIR absorbance, with wavelength in nm in the column name |

The compact file has 36 formulation/domain rows and 125 spectral features. The original has 3141 acquired spectra; each spectrum was already an average of 200 scans. Preparation takes arithmetic means within the original subset and sample IDs. Domains represent the source paper's temperature-related acquisition conditions, not four independent laboratories. Preserve the original subset labels when reproducing the benchmark. The acquisition order and lack of independent formulation-preparation replicates limit broader interpretation.

Source attribution and licenses: `DATA_SOURCES.json`. Transformations: `scripts/reproduce_examples.py`.
