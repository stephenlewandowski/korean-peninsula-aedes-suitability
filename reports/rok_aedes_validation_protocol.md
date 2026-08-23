# Republic of Korea Aedes validation protocol

## Purpose

This is the next validation gate for the Korea-first Aedes product. It asks
whether public Republic of Korea observations are compatible with the spatial
and seasonal structure of the modeled suitability output. It does not treat
suitability as abundance, infection, or a disease forecast.

## Observation boundary

The validation table is restricted to canonical `South Korea` records. North
Korea cells in the suitability product remain modeled extrapolation cells and
are not used as observed validation data. Public occurrence records and trap
observations are retained as different observation types:

- occurrence records retain coordinates, date precision, taxonomic basis,
  license, and sampling notes;
- trap presence or abundance retains trap effort and the observation period;
- infection or disease-surveillance records are not accepted as Aedes
  validation without a separate outcome definition and observation model.

`scripts/audit_rok_aedes.py` checks this contract and reports coverage by
source, species, and observation type. An empty schema audit is included in the
repository; no performance result is claimed until a reviewed populated table
is added.

## Required validation design

The first feasibility analysis should use spatial and temporal holdouts, not a
random-only split. A defensible minimum is:

1. hold out geographically separated ROK cells or administrative groups;
2. hold out one or more complete years or seasons from the 2008–2012 feasibility
   surveillance window when the source supports that design;
3. report results separately for occurrence and trap observations rather than
   pooling them;
4. compare a seasonal baseline with suitability covariates and record the
   threshold used for any binary interpretation; and
5. report discrimination, calibration, sample size, spatial/temporal coverage,
   and missingness with uncertainty intervals where the sample supports them.

Morphological identification limits and opportunistic sampling must remain in
the interpretation. A positive association would support model comparison,
not prove vector presence outside observed cells or establish human risk.

## Current status

A source-field-reviewed import is now present at
`inputs/aedes_observations.csv`. It contains 54 dated, georeferenced,
presence-only *Aedes albopictus* records from four contributing GBIF datasets,
covering 2007–2024. Forty-four records have an exact join to the current public
Korea grid; ten retain valid coordinates but do not intersect that grid and
remain flagged for spatial review. No standardized sampling-effort denominator
is reported for these occurrence records, so `sampling_effort` is blank and no
trap-abundance rate is inferred.

The import is reproducible with
`scripts/build_rok_aedes_observations.py`; source dataset metadata, licenses,
occurrence identifiers, query policy, exclusions, and the output checksum are
recorded in `metadata/rok_aedes_source_registry.json`. The audit command is:

```bash
python scripts/audit_rok_aedes.py \
  --observations inputs/aedes_observations.csv \
  --output-dir outputs/rok_aedes_validation
```

The audit status is `ready_for_model_review`. This does not authorize model
fitting: a human scientific review of the source records and a separate
effort-aware validation design are still required. The undated South Korea
*Aedes aegypti* occurrence record was excluded because the required temporal
fields were absent. Anopheles event-level validation remains a separate,
blocked workstream.
