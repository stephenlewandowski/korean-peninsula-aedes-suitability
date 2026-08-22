# Senior-level case: suitability is not consequence

## Case brief

You are advising a regional environmental-health team reviewing a static
Korea–Japan comparison of *Aedes aegypti* and *Aedes albopictus* suitability.
The analysis covers 1975–2024 on a 0.25-degree source grid and compares
1975–1984, 1995–2004, and 2015–2024. It reports monthly suitability, first and
last suitable calendar month, suitable-month count, suitable-season span, and
the longest contiguous run.

The team asks: “Does a longer modeled suitable season mean more disease, and
should we issue an early warning for the peninsula?” Your job is to produce a
defensible one-page answer from the repository tables and figures, then design
the next evidence-gathering step.

## Student tasks

1. Write two statements the tables support and two statements they do not
   support. Include the difference between environmental suitability, vector
   presence/abundance, infection, incidence, and transmission risk.
2. Compare suitable-month count with first-to-last span. Construct a toy
   12-month example where the span is longer than the number of suitable
   months, and explain why a reader could misinterpret the span as a continuous
   season.
3. Audit the extraction: identify the cell-center boundary rule, latitude
   weighting, suitability threshold, missing-value rule, and why the DPRK map
   must be labeled modeled extrapolation in the absence of direct records.
4. Design a validation split using ROK occurrence or trap observations. Explain
   why a random point split can overstate performance when nearby cells or
   repeated traps share climate and sampling conditions.
5. Propose a surveillance comparison. Keep Aedes suitability separate from the
   KDCA malaria-vector/*Plasmodium vivax* lead and identify the lag and reporting
   changes that must be tested.
6. Decide whether a time slider, location selector, population overlay, or
   early-warning model improves the decision. Justify the choice in terms of
   user task and unsupported precision.

## Instructor notes

Strong answers distinguish a change in a model-derived environmental field from
an observed biological or public-health outcome. They mention threshold
sensitivity, spatial aggregation, missingness, model uncertainty, boundary
approximation, surveillance bias, and the absence of direct DPRK surveillance.
They do not convert the maps into military/site-risk claims.

The reproducible pathway is:

```text
analyze_korea.py
    -> validate_outputs.py
analyze_korea_japan.py
    -> validate_korea_japan.py
prepare_population_exposure.py
analyze_surveillance_lags.py
analyze_driver_correlations.py
evaluate_early_warning.py
```

The last four applications are intentionally source-gated. A completed class
exercise may use a clearly labeled synthetic or public subset, but students
must not present a synthetic run as validation or an operational warning.

## Extension and assessment

Ask students to revise a misleading headline such as “Korea’s mosquito season
expanded, increasing disease risk” into a source-bounded headline. Grade the
revision on claim scope, uncertainty, observation-model distinction,
surveillance-bias treatment, and reproducibility. Capture recurring student
questions as future research prompts without storing student identities or
evaluative personal data.
