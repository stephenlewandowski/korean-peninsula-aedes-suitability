# Surveillance comparison and lag protocol

## Purpose and boundary

The comparison is designed to test whether a regional suitability series is
temporally consistent with a separately defined vector or disease indicator.
Suitability is one environmental input. It is not abundance, infection,
incidence, or a forecast of human transmission.

## Observation types must remain separate

The first application is Aedes suitability. The supplied Korean leads include
surveillance of *Anopheles sinensis* and *Plasmodium vivax*, which are relevant
validation leads for a separate malaria-vector branch but are not direct
validation of the Aedes suitability output. The [KDCA 2024 malaria vector
surveillance report](https://www.kdca.go.kr/bbs/chungcheong/142/293598/download.do)
describes a Republic of Korea programme in malaria-risk areas; it does not
provide direct DPRK coverage. The [Goyang PLOS One study](https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0244479)
is a useful small ROK feasibility series, with its own trap, identification,
and climate-covariate limitations.

Do not merge opportunistic GBIF occurrences, trap abundance, mosquito infection
tests, and human disease counts as though they were interchangeable outcomes.
Each row in `inputs/surveillance_monthly.csv` must retain a source ID,
indicator, unit, denominator, observation effort, case definition, and any
reporting-change note.

## Required comparison steps

1. Select a public series with a defined geography and time basis. Register the
   source before analysis; distinguish collection date, report date, and
   publication date.
2. Align the series to month and geography without filling unobserved DPRK
   surveillance with ROK values. Label any DPRK suitability result as modeled
   extrapolation when no direct observations exist.
3. Run `scripts/analyze_surveillance_lags.py` for lags from -6 to +6 months.
   A positive lag means suitability leads the surveillance month.
4. Report the matched-row count, Pearson and Spearman correlations, and the
   fraction of matched rows carrying a reporting-change note for every lag.
5. Repeat the comparison after excluding flagged reporting-change periods and
   by observation type. Treat differences as sensitivity analyses, not proof
   that reporting changes caused a result.
6. Compare against seasonal and conventional-climate baselines before
   describing any incremental association.

The correlation output is exploratory. A lag peak is not evidence of a causal
pathway, and absence of association can reflect surveillance coverage,
diagnostic practice, mobility, vector behavior, reporting delay, or mismatch
between the modeled species and the observed indicator.

## Current status

The repository contains the tidy input schema, lag-testing code, and source
leads. No disease or vector comparison result is claimed until a public,
source-linked monthly series has been supplied and its reporting process has
been reviewed.
