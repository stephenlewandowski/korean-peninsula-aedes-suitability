# ROK *Anopheles sinensis* validation gate

## Gate decision

**ASSEMBLY CHECKPOINT PASSED; PREDICTIVE GATE NOT PASSED.** The repository now
contains a ROK-only molecular/PCR evidence table with 488 detection-positive
rows, 156 sites, 85 spatial blocks, and reproducible site/year holdout
partitions. It still lacks reviewed non-detections and harmonized effort
denominators, so no Anopheles model, ROK suitability map, DPRK extrapolation,
malaria-incidence estimate, or transmission forecast is authorized by this
gate.

The available Goyang source was used only for a bounded temporal feasibility
run. Its result is not a pass of the requested scientific gate.

## Executed checks

| Requirement | Status | Evidence | Consequence |
| --- | --- | --- | --- |
| ROK-only geography | PASS | All 488 direct rows are `country=South Korea`; source-registry and aggregate rows are ROK-scoped | Geography scope is acceptable for ROK evidence assembly |
| Molecular evidence | PARTIAL PASS | 327 rows have explicit row-level PCR/ITS2 evidence; 25 source-table rows have a blank per-row method cell; 136 public DNA-layer rows retain a protocol-pending or source-record flag | Do not silently label every public DNA record as PCR-confirmed |
| Site-level geometry | PASS for occurrence structure | 156 coordinate-defined sites and 85 spatial blocks; no required site/coordinate/year fields are missing | A leakage-safe partition can be constructed |
| Site-level response | **FAIL for predictive modeling** | All direct rows are detection-positive; no reviewed non-detection rows or harmonized effort denominator is present | Occurrence evidence must not be converted to zeros or pooled rates |
| Site-blocked spatial validation | STRUCTURAL PASS | Five complete-site folds have zero site overlap; a five-fold 0.1-degree block sensitivity split also has zero block overlap | Partition design is valid; predictive metrics are not eligible |
| Year-blocked temporal validation | STRUCTURAL PASS | Eleven direct observation years have leave-one-year-out partitions with zero year overlap | Partition design is valid; predictive metrics are not eligible |

## Temporal holdout result

The holdout was deliberately small and transparent: 2012 was held out, and
the models used only the 2008–2011 records for training.

| Model | MAE | RMSE | R² |
| --- | ---: | ---: | ---: |
| Training-seasonal mean | 3.271825 | 5.447827 | 0.425574 |
| Log1p ridge climate smoke test | 3.641597 | 5.693826 | 0.372525 |

These are predictive diagnostics for a Goyang network-average time series,
not validation metrics for a species-distribution model. They remain a
historical feasibility result and are separate from the new PCR/molecular
evidence table.

## Why the gate stops here

The Goyang supporting workbook remains useful for a bounded seasonal
feasibility exercise, but it is network-averaged and morphology-based. The new
table resolves the former species/site evidence gap by assembling public
molecular records, PCR/ITS2 supplementary records, and explicitly separated
2020/2021 aggregates. It does not resolve the response-denominator gap.

The exact table, source registry, fold manifest, fold summary, and structural
audit are documented in
`reports/rok_anopheles_sinensis_longitudinal_validation.md`.

## Required input to reopen the gate

The remaining gate input is a reviewed sampling-event table with at least
these fields:

```text
record_id,source_id,observation_type,species,country,geography,site_id,
longitude,latitude,collection_date,year,month,value,unit,sampling_effort,
taxonomic_basis,license,reporting_note
```

Minimum acceptance conditions:

1. `country` is `South Korea` for every record.
2. `species` is exactly `Anopheles sinensis` for the target subset.
3. `taxonomic_basis` records PCR, sequencing, or another reviewed species-
   confirmation method; morphology-only records remain flagged and excluded
   from the confirmed subset.
4. `site_id`, coordinates, collection date/year, response value, and effort
   are present.
5. Repeated observations at multiple sites and years have harmonized or
   explicitly stratified sampling protocols and units.
6. Absence/non-detection records have a documented sampling effort. Presence-
   only records must not be converted into zeros.
7. Spatial validation holds out complete sites or site blocks, with no records
   from a held-out site in training.
8. Temporal validation holds out complete years, with no records from a
   held-out year in training. Report each held-out year separately when the
   number of years permits it.

The current table meets conditions 1–4 and the structural parts of 7–8, but
not condition 6. Only after the remaining conditions pass should the project
fit a separate ROK *Anopheles* model. Any DPRK result would remain a model
extrapolation, not an observation validation result.

## Source references

- Jang JY, Chun BC (2020), Goyang source and supporting data:
  <https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0244479>
- Kim HC et al. (2007), ITS2/PCR-confirmed 2005 Korean surveillance:
  <https://doi.org/10.1111/j.1748-5967.2007.00049.x>
- Rueda LM et al. (2006), Korean distribution and larval habitats:
  <https://bioone.org/journals/journal-of-vector-ecology/volume-31/issue-1/1081-1710%282006%2931%5B198%3ADALHCO%5D2.0.CO%3B2/Distribution-and-larval-habitat-characteristics-of-span-classgenus-speciesAnopheles-span/10.3376/1081-1710%282006%2931%5B198%3ADALHCO%5D2.0.CO%3B2.full>
- Lee SY et al. (2022), PCR-identified Gyeonggi 2020 species diversity:
  <https://research.knu.ac.kr/en/publications/species-diversity-of-anopheles-mosquitoes-and-plasmodium-vivax-in/>
- Kang S et al. (2012), molecular An. sinensis complex/kdr survey:
  <https://doi.org/10.1186/1475-2875-11-151>
- Jeon J et al. (2025), multiplex-PCR-confirmed ROK Anopheles collections:
  <https://journals.plos.org/plosntds/article?id=10.1371%2Fjournal.pntd.0012748>
- Hong H et al. (2023), Ganghwa/Gimpo PCR and sequencing records:
  <https://doi.org/10.1186/s12936-023-04821-x>
- Eom TH et al. (2025), Ganghwa 2024 PCR/ITS2 records:
  <https://doi.org/10.1038/s41598-025-29307-5>
- Public MosquitoMap2 molecular layer used for historical occurrence rows:
  <https://services2.arcgis.com/HRY6x8qt5qjGnAA9/arcgis/rest/services/MosquitoMap2/FeatureServer/0>
- KDCA (2025), ROK 2024 malaria-vector surveillance and trap-index methods:
  <https://neweng-phwr.inforang.com/journal/view.html?uid=956&vmd=Full>
