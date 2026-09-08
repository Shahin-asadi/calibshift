# Diagnostic reading guide

Every diagnostic is computed after model fitting from the same result object used for the CSV exports. It never changes tuning, removes an observation, or supplies an additional validation sample. `figure_catalog.json` maps the actual available figures to titles and captions; unavailable views are omitted or explained.

| Question | Table / view | What to check |
|---|---|---|
| Where are errors concentrated? | `group_diagnostics` and group residual map | Physical-group mean bias can cancel opposing errors; also read within-group RMSE and row counts. |
| Is performance different over the response range? | `reference_range_diagnostics` | Up to four common post-prediction reference bins. Sparse bins are descriptive; no uncertainty interval is inferred. |
| Does a method beat its baseline on identical observations? | `paired_baseline_comparison`, when applicable | Each method uses its own exact intersection with the baseline. Negative RMSE difference favours that method on that subset; subsets can differ. |
| Are input features incomplete or redundant? | `feature_quality` and correlation preview | First 12 selected columns in input order are visualized. Correlations use at least three available pairs; these are not feature-selection or independence tests. |
| Are transfer standards informative over the held-out range? | `standard_range_diagnostics`, CalibShift | Held-out references are examined retrospectively, never used to select standards. Being inside a range does not prove valid transfer. |
| Are fusion weights stable? | `fitted_choices`, SenseFusion | Fold-to-fold differences describe predictive fits; weights are not causal sensor importance. |
| Do particular runs influence a surface? | `influence_diagnostics`, MatchedDoE | Cook's distance and internal studentization require usable residual variance and the independence declaration. The 4/n line is a review heuristic; no rows are deleted. |
| Which two-response candidates involve a tradeoff? | `candidate_tradeoff`, MatchedDoE | Nondominance uses the declared minimize/maximize directions on the finite common grid. It is not measured confirmation or a continuous optimum. |
| Do group-mean differences support interchangeability? | Agreement plot, AssayReport | The plot describes differences; practical acceptability needs an external, prespecified tolerance and suitable study design. |

Figures use truthful axes, consistent within-comparison scales, direct labels, marker shapes/facets and signed zero-centred residual colours. PDF is the preferred scalable print format. SVG retains editable text and uses the receiving system's fonts. PNG is exported at 300 dpi. The Excel companion uses Times New Roman, restrained black table rules, explicit small-value scientific notation and literal text cells.

## Reading in the app

The Results page selector groups key diagnostic figures and full tables into scientific sections. These describe the already computed result. Detailed HTML/PDF exports follow the same sections; large printed tables use explicit excerpts. The key-results ZIP includes the full corresponding CSVs. All tables and the advanced archive retain additional calculations and full predictions. Overview cohort selection remains separate from the explicitly labelled diagnostic populations.
