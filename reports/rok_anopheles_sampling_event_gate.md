# ROK *Anopheles sinensis* sampling-event gate

## Current status

**BLOCKED pending a reviewed event-level table.** The PCR/molecular evidence
table contains detections and provenance, but it does not contain a complete
set of sampling events with documented non-detections and harmonized effort.

The required input is intentionally represented by the header-only template:

`inputs/rok_anopheles_sinensis_sampling_events.template.csv`

Required fields are:

```text
sampling_event_id, source_id, site_id, site_name, country,
longitude, latitude, collection_date, year, month, collection_method,
life_stage, sampling_effort, effort_unit, total_anopheles,
target_detected, target_count, taxonomic_basis, molecular_method,
non_detection_basis, license, source_url, review_status, notes
```

## Rules

- A missing record is not a non-detection.
- A non-detection requires a documented sampling event, target taxon, method,
  effort, and reviewable source.
- Opportunistic molecular occurrence records remain separate from
  trap-abundance events.
- Counts from different methods or life stages must not be pooled without an
  explicit observation model or source-stratified analysis.
- The event table must retain the taxonomic basis, molecular method, license,
  and source provenance.

## Required source-recovery work

The highest-value recovery targets are the underlying site-event tables for the
2020 Gyeonggi PCR study and the 2021 eight-site multiplex-PCR study. The
published aggregates establish detections, but they do not provide enough
event-level denominators for predictive validation.

Until those records are recovered and reviewed, the project should not report
model AUC, sensitivity, specificity, calibration, RMSE, abundance-rate error,
or an Anopheles suitability model.

Run the audit after populating a reviewed file at:

```text
inputs/rok_anopheles_sinensis_sampling_events.csv
```

```bash
python scripts/audit_rok_anopheles_sinensis_sampling_events.py \
  --events inputs/rok_anopheles_sinensis_sampling_events.csv \
  --output-root .
```
