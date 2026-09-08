# Methods and interpretation

## Question and inputs

How much does a source calibration deteriorate under changed acquisition conditions, and how much can a small set of target-condition standards correct it? The implemented comparison concerns source PLS, a source-mean baseline, bias correction, slope/intercept correction, and target spectral recalibration. It is an evaluation of interpretable correction choices and measurement budgets, not a complete implementation of every calibration-transfer algorithm [P15–P20].

Each physical formulation needs a stable group ID, a source/target condition label, matching spectral columns, and a recorded reference. The protocol assumes the formulation's response is unchanged across conditions. Conflicting responses within a group are rejected rather than averaged into a new reference. Spectra are averaged within each formulation and acquisition condition before evaluation. A blank target reference can be linked to that same formulation's recorded source reference; the link is recorded in `aggregated_input.csv`. This lookup is valid only for the unchanged, explicitly identified formulation. References from target-only rows are not used to fill missing source calibration labels.

## Capability rules

An empty budget list or budget zero retains the unadapted source mean and any estimable source PLS model. One remaining source training unit supports its mean only. At least two variable units permit a fixed one-component fit; component tuning is used when supported. One target standard permits bias correction, two distinct predicted standard values permit slope/intercept correction, and at least four selected standards permit the existing bounded target-PLS tuning. Target recalibration eligibility is independent of source-model availability. Unavailable operations are listed in splits.csv. Reference linking requires the same unchanged physical formulation across conditions.

## Validation and corrections

For each target formulation, all source and target rows with that formulation ID are excluded from model fitting and correction-standard selection. A source PLS model is fitted to the remaining labelled source formulations. Component counts 1–3 are selected by grouped cross-validation within that source training set. Median imputation, centering and total-variance scaling use training data only. Eligibility is assessed separately per fold and operation. The single held-out target spectrum is then predicted [P11–P14, P18].

For each requested budget k, candidate standards are the available target spectra whose formulation IDs occur in the source training set. Sort candidates by their source reference, then ID; choose k evenly spaced positions across that ordered list. This is an explicit reference-range sampling rule, not Kennard–Stone spectral selection. No held-out target error is consulted.

Bias correction adds the mean of (recorded reference − source prediction on the target standard) to the held-out source prediction. Slope/intercept correction fits recorded references to a constant plus the source predictions of the selected target standards, using ordinary least squares. It requires at least two standards and nonconstant standard predictions. With insufficient standards the corresponding correction is omitted and the reason is recorded. The uncorrected result remains available [P19].

A budget counts target-condition measurements of previously calibrated physical standards. It is not automatically the number of new chemical reference assays. Target spectra for the held-out formulation never enter preprocessing, model fitting or adaptation. This distinguishes the protocol from transductive adaptation that deliberately uses unlabelled test spectra.

## Reading the output

`predictions.csv` identifies the source, target condition, held-out group, method, budget and residual. `standards.csv` records every selected standard and correction coefficient. `splits.csv` records source training groups and unavailable budgets. `target_availability.csv` shows formulations that lack spectra or a recorded reference. The numerical scores use the same error definitions as documented in `GETTING_STARTED.md`.

Available-row scores retain missing-prediction coverage. Common-row scores compare methods on the same scored formulations within each target condition. Coverage is conditional on having a usable target spectrum; the availability table retains completely absent spectra. Unknown references remain unscored. More standards or a fitted slope can worsen performance. Choosing a budget after inspecting these errors does not independently validate that selected budget.

## Applicability

Simple corrections are appropriate comparisons when drift is approximately systematic. They do not repair arbitrary changes in sample chemistry or instrument resolution. Equal marginal distributions do not prove equal response relationships, and unsupervised adaptation does not guarantee successful transfer [P15, P17, P20]. DS, PDS, di-PLS and mdi-PLS were reviewed as alternative approaches; this release does not implement them or imply numerical equivalence to them.

The public example has nine acetaminophen formulations and four temperature-related acquisition domains from one MicroNIR setup. Its 3141 spectra are not 3141 independent formulations. Our 36 formulation/domain means and leave-formulation-out protocol differ from the source paper's scan-level evaluation [P18]. Endpoint holdouts may require concentration extrapolation. There is no second independent experimental transfer dataset in this release; the three target conditions share one experiment. Controlled mathematical fixtures test correction arithmetic separately from these public measurements.

## Target spectral recalibration and reference consistency

For budgets of at least four, target PLS is trained on the exact same selected standards used for correction. Components 1–2 are chosen by grouped inner validation of those standards. The held-out formulation is excluded throughout. Smaller budgets deliberately leave this method unavailable and record the reason. With few standards, target-only spectral fitting can be unstable and perform worse than the source model; the public benchmark retains that result.

Reference consistency is checked as range <= reference_atol + reference_rtol × maximum absolute reference, with defaults 0 and 1e-8. Set an absolute tolerance only in the actual reference unit. Unknown destination conditions and entirely unavailable budgets produce partial evidence. The all-method common cohort refers to available implemented method/budget combinations within a destination; use the split and availability tables to identify any requested combinations that could not be fitted.


## Reporting population

The core records `predictions.in_common_cohort` separately for each destination across implemented method/budget combinations. The headline and primary scatter use exactly those formulations. `summary_cohort.csv` records included identities; `summary_view.json` records the destination, method, budget and available/scored counts. If the common intersection is empty, the view explicitly reports a standalone available-pair result and omits the family comparison plot.

Default order is eligible bias correction, source PLS, then source mean, with the first available budget. Choices are deterministic and never based on the smallest held-out error. Switching views never refits.
