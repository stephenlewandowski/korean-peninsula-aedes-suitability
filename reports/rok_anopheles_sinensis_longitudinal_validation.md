# ROK *Anopheles sinensis* PCR and molecular longitudinal validation table

## Decision

**Evidence-table assembly: complete. Predictive validation gate: not passed.**

The assembled table is appropriate for source reconciliation, taxonomic
evidence review, leakage-safe holdout construction, and a future ROK-only
feasibility model. It is not yet a harmonized presence/absence or
effort-standardized abundance table, so predictive scores are intentionally
not reported.

The table is restricted to the Republic of Korea. It does not create DPRK
observations, malaria incidence, infection risk, vector abundance, or a
transmission forecast.

## Research basis

The source review prioritized studies that used PCR, ITS2-based molecular
identification, molecular sequencing, or a public molecular occurrence record.
Morphology-only observations were not merged into the confirmed table.

| Source | Field period | Molecular evidence | Extracted or retained evidence | Status |
| --- | --- | --- | --- | --- |
| Kim et al. (2007) | 2005 | ITS2 within nuclear rDNA; PCR confirmation | 88 public molecular records; publication aggregate: 3,194 *An. sinensis* among 4,534 *Anopheles* from 95 collections | Individual records partial; aggregate retained in registry |
| Rueda et al. (2006) | 1998–2004 | Molecular occurrence layer linked to the study | 45 public DNA records across 35 coordinate-defined sites | Protocol detail not preserved in the public layer |
| USFK installation survey | 2005 | Public layer reports `IdentificationMethod=DNA` | 9 public molecular records | Protocol and original denominator require review |
| Klein et al. field collection | 2006 | Public layer reports `IdentificationMethod=DNA` | 82 public molecular records | Protocol detail requires source review |
| Lee et al. (2022) | May–early November 2020 | Explicit PCR species identification | Published aggregate: 165 *An. sinensis* among 1,622 assayed; 1,864 *Anopheles* identified to species across eight sites | Study aggregate only; no site rows inferred |
| Jeon et al. (2025) | April–October 2021 | Multiplex PCR; ITS2 sequencing for selected specimens | Eight published site-period counts totaling 122 *An. sinensis* among 489 *Anopheles* | Site-period aggregate; not converted to rates |
| Hong et al. (2023) | 2022–2023 | Supplementary individual records report multiplex PCR, ITS2, and/or COI | 118 individual records from two Ganghwa/Gimpo sites | Included as specimen-level detections |
| Eom et al. (2025) | July–mid-September 2024 | Supplementary individual records report multiplex PCR or ITS2 | 146 *An. sinensis* rows from three Ganghwa sites | Included as specimen-level detections; main-text 124-mosquito kdr subset kept distinct |
| Kang et al. (2012) | Year not stated in reviewed summary | Multiplex species assay; VGSC PCR/sequencing | 665 *An. sinensis* among 755 complex specimens at 22 locations | Aggregate source-registry context only |
| Foley et al. (2009) | 1998–2006 | Literature-linked molecular occurrence records | 152 unique sites before 5-km thinning; 80 retained for ENM | Analysis-reference context, not an abundance panel |

Sources: [Kim et al.](https://doi.org/10.1111/j.1748-5967.2007.00049.x),
[Rueda et al.](https://bioone.org/journals/journal-of-vector-ecology/volume-31/issue-1/1081-1710%282006%2931%5B198%3ADALHCO%5D2.0.CO%3B2/Distribution-and-larval-habitat-characteristics-of-span-classgenus-speciesAnopheles-span/10.3376/1081-1710%282006%2931%5B198%3ADALHCO%5D2.0.CO%3B2.full),
[Lee et al.](https://research.knu.ac.kr/en/publications/species-diversity-of-anopheles-mosquitoes-and-plasmodium-vivax-in/),
[Jeon et al.](https://journals.plos.org/plosntds/article?id=10.1371/journal.pntd.0012748),
[Hong et al.](https://doi.org/10.1186/s12936-023-04821-x),
[Eom et al.](https://doi.org/10.1038/s41598-025-29307-5),
[Kang et al.](https://doi.org/10.1186/1475-2875-11-151), and
[Foley et al.](https://academic.oup.com/jme/article/46/3/680/861860).

## Table products

### Individual molecular observation table

`inputs/rok_anopheles_sinensis_pcr_observations.csv` contains:

- 488 detection-positive molecular occurrence/specimen rows;
- 156 coordinate-defined site IDs;
- 85 conservative 0.1° spatial blocks;
- direct observations in 11 years: 1998–2006 with gaps, then 2022–2024;
- 327 rows with explicit row-level source PCR/ITS2 evidence;
- 25 supplementary species rows where the source table's per-row method cell
  is blank, retained with an explicit method-not-printed flag;
- 136 public DNA-layer rows whose specimen-level protocol is not retained in
  the public layer and is flagged rather than silently upgraded to PCR;
- zero inferred absences or non-detections; and
- zero duplicated `record_id` values.

The field `pcr_confirmation_status` is the controlling evidence flag. It
distinguishes `verified_PCR_or_ITS2_source_table`,
`verified_species_source_table_method_not_printed`,
`source_confirmed_molecular_ITS2`, `molecular_DNA_source_record`, and
`molecular_DNA_layer_record_protocol_pending`.

### Published aggregate table

`inputs/rok_anopheles_sinensis_pcr_site_period_counts.csv` retains the 2020
study aggregate and the eight 2021 site-period counts. These rows are not
pooled with individual records because their denominators and sampling units
are not equivalent.

### Longitudinal summary table

`inputs/rok_anopheles_sinensis_longitudinal_validation.csv` summarizes each
source-year and labels its validation role. It contains 14 source-year rows:
11 direct observation strata plus the 2020 and 2021 aggregate context rows.

### Provenance

`metadata/rok_anopheles_pcr_source_registry.csv` records the study-level
method, field period, scope, source URL, extraction status, and interpretation
boundary. The 2024 source is distributed under CC BY-NC-ND in the article
record; derivative-data redistribution should be reviewed before committing
the raw table to a public release. Installation-level or otherwise sensitive
site coordinates should also be aggregated or redacted before publication.

## Validation partition design

The audit uses only the 488 direct individual molecular rows. Published 2020
and 2021 aggregates are excluded from fold assignment because they do not have
the same record-level geometry and response unit.

| Axis | Partition | Result |
| --- | --- | --- |
| Primary spatial | Five complete-site folds using `site_id` | 156 sites; train/test site overlap = 0 |
| Spatial sensitivity | Five complete 0.1° block folds using `spatial_block_id` | 85 blocks; train/test block overlap = 0 |
| Temporal | Leave-one-year-out by direct observation year | 11 holdout years; train/test year overlap = 0 |

The fold assignments are reproducible in
`inputs/rok_anopheles_sinensis_validation_fold_manifest.csv`; fold sizes and
eligibility are in
`inputs/rok_anopheles_sinensis_validation_fold_summary.csv`.

The current 370-cell Korea suitability grid receives an exact polygon join for
238 of the 488 rows. The remaining 250 rows retain valid coordinates but do
not intersect the supplied public grid. No nearest-cell assignment or
boundary imputation was made. This is a grid-coverage limitation, not a reason
to delete the ROK observations.

The exact-join decision is recorded in
`inputs/rok_anopheles_sinensis_grid_join_audit.csv` and
`metadata/rok_anopheles_grid_join_audit.json`: include the 238 exact joins in
grid-linked analysis and exclude the 250 non-intersecting records from that
cohort while retaining them in the evidence table.

## Why predictive metrics are not reported

The molecular source table is a detection-positive evidence panel. It contains
no reviewed non-detection/absence rows and no harmonized effort denominator.
Trap descriptions such as “biweekly Mosquito Magnet,” “five adult traps,” or
“10-dip larval sampling” are preserved as provenance text, but they are not
interchangeable response denominators across studies, sites, stages, and
years.

Therefore:

1. the site and year partitions are valid structural holdouts;
2. presence-only discovery records must not be scored as if they were
   absences;
3. specimen counts from different protocols must not be pooled as a common
   abundance rate; and
4. no AUC, sensitivity, specificity, RMSE, calibration, or suitability-model
   performance claim is made from this table.

The next scientific input is a reviewed sampling-event table containing both
detections and documented non-detections, with site, year/date, life stage,
collection method, and harmonized or explicitly stratified effort. The 2020
and 2021 study teams' underlying site-event denominators would be especially
valuable. Until then, this table supports a transparent feasibility gate, not
a finished *Anopheles* model.

The event-table contract and blocking audit are documented in
`inputs/rok_anopheles_sinensis_sampling_events.template.csv`,
`metadata/rok_anopheles_sampling_event_audit.json`, and
`reports/rok_anopheles_sampling_event_gate.md`.

## Reproducible commands

From the repository root:

```bash
python scripts/build_rok_anopheles_sinensis_validation_table.py \
  --output-root . \
  --grid outputs/korea_focus/korea_focus_cell_grid.geojson

python scripts/audit_rok_anopheles_sinensis_validation_table.py \
  --output-root .
```

The source builder uses the public MosquitoMap2 feature layer and the two
published supplementary tables:

- [MosquitoMap2 public feature layer](https://services2.arcgis.com/HRY6x8qt5qjGnAA9/arcgis/rest/services/MosquitoMap2/FeatureServer/0)
- [Hong et al. supplementary table](https://media.springernature.com/original/springer-static/esm/art%3A10.1186%2Fs12936-023-04821-x/MediaObjects/12936_2023_4821_MOESM1_ESM.docx)
- [Eom et al. supplementary table](https://media.springernature.com/original/springer-static/esm/art%3A10.1038%2Fs41598-025-29307-5/MediaObjects/41598_2025_29307_MOESM1_ESM.docx)
