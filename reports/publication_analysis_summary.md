# Publication analysis summary and bounded impact statements

## Scope and quality status

This summary supports the static GitHub Pages publication layer. It draws only
from committed suitability, population-exposure, ROK occurrence, and ROK
trap-index products. The population audit status is `PASS`; the ROK Aedes audit
status is `ready_for_model_review`; and the publication-product audit status is
`PASS`.

The analysis covers 1975–2024 on 370 source-grid cells: 215 selected North
Korea cells and 155 selected South Korea cells. North Korea results remain
modeled extrapolation because the reviewed observation inputs contain no direct
DPRK records.

## Headline findings

### Modeled suitability

Between 1975–1984 and 2015–2024, the area-weighted Korean Peninsula mean
suitable-month count changed from 2.67 to 3.24 months for *Aedes aegypti*
(+0.57) and from 4.21 to 4.71 months for *Aedes albopictus* (+0.50). South
Korea changes were +0.65 and +0.51 months, respectively; North Korea modeled
changes were +0.51 and +0.50 months.

The peninsula-wide monthly profiles show the most visible early-to-recent
increases around May–June and September. These are changes in area-weighted
modeled environmental suitability. They do not establish an observed change in
mosquito onset, end, abundance, biting activity, infection, or transmission.

### Population exposure

The LandScan join has complete cell-period coverage, finite weighted metrics,
bounded shares, and reconciled totals. In the recent period, 95.6% of peninsula
ambient population was in cells with increasing *Ae. aegypti* suitable-month
count and 98.8% was in cells with increasing *Ae. albopictus* suitable-month
count. The corresponding population-weighted suitable-month changes were
+0.46 and +0.36 months.

These figures describe population exposure to modeled environmental
suitability. They are not counts or shares of people infected, exposed to a
mosquito, at individual risk, or expected to become a disease case. Historical
LandScan layers are reconstructions and this application has no cell-level
population uncertainty band.

### Reviewed ROK evidence

The occurrence input contains 54 reviewed presence-only records from
2007–2024. Sampling effort remains unreported for those records, so they do not
provide standardized abundance, non-detection, or effort-denominator evidence.

The separate trap-index input contains six retained *Ae. albopictus* site rows
from Kim et al. (2018). Each row pools the April–November 2013 and
April–November 2014 sampling windows and preserves 32 trap-nights and 448
trap-hours. Total retained effort is 192 trap-nights and 2,688 trap-hours. The
values are rounded source-reported female trap indices; monthly values and raw
specimen counts were not reconstructed.

## Bounded impact statements

### Surveillance timing

The seasonal-profile products can help researchers identify calendar months
where additional independent monitoring would most directly test the modeled
change signal. This supports formulation of a monitoring design; it does not
set an operational surveillance start date or a disease-alert threshold.

### Regional prioritization

The population-overlap maps show broad public grid cells where modeled change
and ambient population coincide. They can help prioritize regional validation,
adaptation research, and data-quality investment while preserving the 0.25°
resolution. They do not identify neighborhoods, facilities, individuals, or
expected disease burden.

### Evidence-gap targeting

The explicit separation of occurrence and effort-aware trap-index rows makes
the next evidence need concrete: reviewed longitudinal event-level records with
effort, collection periods, and non-detections where available. Direct DPRK
observations are required before any empirical DPRK validation claim.

### Reproducibility and public communication

The project website turns versioned analysis tables into a coherent set of
responsive maps, figures, downloads, methods, and limitations. A publication
audit reconciles headline values to source tables, validates all figure pairs,
checks local links and alt text, records checksums, and confirms that pooled
trap rows were not expanded into monthly raw counts.

## Remaining scientific blockers

- No direct DPRK occurrence or effort-aware surveillance input.
- No reviewed event-level longitudinal Aedes sampling table with non-detections
  and sampling denominators suitable for formal model validation.
- No per-cell uncertainty layer in the suitability release.
- No cell-level uncertainty band for the LandScan historical reconstruction.
- No reviewed monthly surveillance, driver, or outcome table meeting the
  lag-analysis, calibration, holdout, and early-warning protocols.

Until those gaps are closed, the publication must remain a static
environmental-suitability and population-exposure product—not a disease-risk,
incidence, transmission, or operational early-warning system.
