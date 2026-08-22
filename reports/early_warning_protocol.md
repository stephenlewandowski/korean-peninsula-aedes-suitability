# Early-warning prototype protocol

## Decision boundary

This repository can support a research prototype that tests incremental
predictive value. It does not currently support an operational early-warning
claim. A public operational product would require human approval, a defined
decision owner, a documented action threshold, real-time data governance,
monitoring, and a safety review.

## Model ladder

For a pre-specified binary monthly outcome, compare:

1. a month-of-year seasonal baseline estimated only from the training period;
2. a logistic model using conventional climate indicators; and
3. the same climate model plus the recent suitability estimate.

`scripts/evaluate_early_warning.py` implements this comparison. The input
template requires a case/outcome definition, climate predictors, suitability,
optional suitability low/high bounds, and reporting-change notes. A count must
be converted to a documented binary or rate outcome before this script is run;
the model must not silently choose a case definition.

## Validation and calibration

The default time split trains on 1975–2004, uses 2005–2014 for validation, and
holds out 2015–2024 for the final test. The split is temporal, not random. A
future implementation should add geography holdouts and repeated rolling-origin
evaluation when enough observations exist. Keep source and reporting changes
visible in the test table; do not let a reporting transition become a hidden
predictor.

Report AUROC, average precision, Brier score, log loss, threshold metrics,
matched-row counts, and calibration plots. The script also writes bootstrap
intervals for test metrics and, when bounds are supplied, low/mid/high
suitability prediction columns. These are uncertainty displays, not guarantees
of predictive coverage.

The default decision threshold is 0.5 and is labeled provisional and
non-operational. Before any operational language, specify the action, the cost
of false positives and false negatives, the threshold-selection data, and a
calibration acceptance criterion. Do not tune the threshold on the final test
period.

## Interpretation

An improvement in a held-out metric would mean that the supplied suitability
feature added predictive information for that outcome under that validation
design. It would not establish disease causation, human transmission risk, or
generalizability to the DPRK, another pathogen, another surveillance system, or
an installation-level setting.
