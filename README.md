# Climademic Suitability Model: Korean Peninsula Aedes product

This is the Korea-first static application of the Climademic Suitability Model.
It uses the current author-linked Zenodo release (record 21924442, version 2.0)
and restricts the primary product to North Korea and South Korea. Japan is now
maintained as the separate IDEA-0007 comparator; Anopheles/malaria work is the
separate IDEA-0008 feasibility project.

**Status:** audited static analysis package with a GitHub Pages-ready publication site; not an operational disease-risk product.
**Visibility:** `public_candidate`; merging the Pages workflow to `main` makes the static website deployable through GitHub Actions.
**Data currency:** source release and boundary files retrieved 2026-08-19; analysis covers 1975–2024.

The product covers 1975–2024 on the source 0.25° grid for *Aedes aegypti* and *Aedes albopictus*. It provides:

- area-weighted monthly suitability tables for North Korea, South Korea, and the combined Korean Peninsula;
- suitable-month counts for each species and comparison period;
- early (1975–1984), middle (1995–2004), and recent (2015–2024) comparisons;
- cell-year and cell-decade extracts for reproducibility;
- missingness and aggregation diagnostics; and
- static maps of mean annual suitability, suitable-month count, and early-to-recent change.

The application deliberately remains static. The tables, publication figures,
and responsive project website provide the defined geography and period
comparisons without a time slider or location selector that could imply
unsupported sub-grid precision.

## Project website

The GitHub Pages source is in `docs/`. It presents the audited suitability,
population-exposure, occurrence, and pooled trap-index products as separate
evidence classes, with downloadable SVG/PNG figures and compact CSV/JSON
summaries. The deployment workflow is `.github/workflows/pages.yml` and runs
when the website is changed on `main` or when manually dispatched.

Build and audit the publication products with:

```bash
python scripts/build_publication_products.py
python scripts/audit_publication_products.py
```

For a local preview:

```bash
python -m http.server 8000 --directory docs
```

## Korea-first sequence

The active work sequence is:

1. keep the Korean Peninsula product primary and label North Korea cells as
   modeled extrapolation;
2. complete the Korea-only LandScan population-exposure join, with no result
   claimed until the public export passes alignment and missingness checks;
3. add ROK Aedes observations as a separate validation input with spatial and
   temporal holdouts;
4. analyze heat, humidity, land use, and population drivers descriptively,
   retaining correlated-predictor diagnostics; and
5. compare surveillance and test early-warning value only after their data,
   lag, out-of-sample, calibration, uncertainty, and decision-threshold gates
   are met.

The current branch closes the LandScan population-exposure gate, adds reviewed
ROK occurrence and effort-aware pooled trap-index inputs, prepares separate
model-input matrices, and publishes audited figures and summaries. It still
does not fabricate surveillance, driver, early-warning, Anopheles event-level,
non-detection, or effort-denominator results when those inputs are absent.

## Initial Korea-only result

Across the combined Korean Peninsula, the area-weighted mean suitable-month count increased from 2.67 to 3.24 months per year for *Ae. aegypti* (+0.57 months) and from 4.21 to 4.71 months per year for *Ae. albopictus* (+0.50 months) between the early and recent comparison decades. These are changes in modelled environmental suitability, not observations of mosquito presence or measures of disease transmission.

The selected 370 grid cells comprise 215 North Korea cells and 155 South Korea cells. No missing or undefined suitability values were encountered within the selected target cells for the three comparison decades in the v2.0 source release. The source-wide missing-value rule (-1.0) is still retained in the extraction and documented in the methods report.

## Japan comparator (separate project)

`scripts/analyze_korea_japan.py` is now a scoped implementation. Its Korea
scope writes the primary product here; its Japan scope writes the separate
`projects/IDEA-0007-climademic-japan/` comparator. The historical combined
Korea–Japan output is retained as an archive for provenance and is not the
primary interpretation.

For the Korea-first run:

```bash
python3 scripts/analyze_korea_japan.py --scope korea
python3 scripts/validate_korea_japan.py --scope korea
```

The scoped output includes monthly suitability, season onset/end, suitable-
month count, first-to-last span, longest contiguous run, cell-year extracts,
missingness, and early-to-recent static figures for 1975–1984, 1995–2004, and
2015–2024.

“Onset” and “end” are first and last suitable calendar months; they are not
exact dates. A first-to-last span can exceed the number of suitable months when
there are gaps.

To run the Japan comparator separately:

```bash
python3 scripts/analyze_korea_japan.py --scope japan \
  --output-dir ../IDEA-0007-climademic-japan/outputs/japan \
  --metadata-dir ../IDEA-0007-climademic-japan/metadata
```

Both products remain static. They do not add a slider or location selector
because the defined geography and period comparisons are already represented
by bounded tables and side-by-side maps.

## Key files

### Analysis

- `scripts/analyze_korea.py` — extraction, aggregation, diagnostics, and map rendering.
- `scripts/analyze_korea_japan.py` — explicit Korea, Japan, or archived combined extraction, season metrics, tables, and static figures.
- `scripts/validate_korea_japan.py` — scoped output-contract validation.
- `scripts/audit_rok_aedes.py` — ROK Aedes observation schema and readiness audit.
- `scripts/prepare_rok_aedes_model_input.py` — separate occurrence and pooled effort-aware trap-index design matrices.
- `scripts/build_publication_products.py` — reproducible website maps, figures, and downloadable summaries.
- `scripts/audit_publication_products.py` — independent reconciliation, asset, link, claim, and deployment audit.
- `scripts/build_cell_grid_geojson.py` — scoped public polygon grid for external joins.
- `reports/korea_regional_brief.md` — concise results brief with tables.
- `reports/korea_first_static_results.md` — Korea-first scoped result table and coverage note.
- `reports/korea_japan_seasonal_brief.md` — Korea–Japan seasonal comparison and interpretation boundary.
- `reports/methods_and_uncertainty.md` — extraction, aggregation, missingness, and uncertainty record.
- `reports/population_exposure_protocol.md` — LandScan extraction and population-weighting contract.
- `reports/surveillance_comparison_protocol.md` — lag, observation-type, and reporting-change protocol.
- `reports/driver_analysis_protocol.md` — heat, humidity, land-use, population, and collinearity protocol.
- `reports/early_warning_protocol.md` — non-operational out-of-sample evaluation gate.
- `reports/rok_aedes_validation_protocol.md` — ROK observation separation and holdout gate.
- `reports/publication_analysis_summary.md` — public-facing findings, bounded impact statements, and remaining evidence gaps.
- `teaching/IDEA-0006-climademic-model-interpretation.md` — reproducible senior-level teaching case.
- `metadata/korea_analysis_run_metadata.json` — source hashes, scope, grid, and method parameters.
- `metadata/korea_japan_run_metadata.json` — Korea–Japan source hashes, scope, and method parameters.
- `metadata/korea_focus_run_metadata.json` — Korea-first scoped source hashes, grid, and method parameters.
- `metadata/application_sources_2026-08-20.md` — source-linked follow-on application record.
- `metadata/SOURCE_MANIFEST.md` — source inventory and provenance.

### Tables

- `outputs/tables/korea_regional_monthly_suitability.csv`
- `outputs/tables/korea_regional_suitable_months.csv`
- `outputs/tables/korea_monthly_change_early_to_recent.csv`
- `outputs/tables/korea_suitable_months_change_early_to_recent.csv`
- `outputs/tables/korea_missingness_summary.csv`
- `outputs/tables/korea_cell_year_monthly.csv.gz`
- `outputs/tables/korea_cell_decadal_summary.csv.gz`

### Static maps

- `outputs/maps/korea_suitable_months_decades.png`
- `outputs/maps/korea_mean_suitability_decades.png`
- `outputs/maps/korea_suitable_months_change_early_to_recent.png`
- `outputs/maps/korea_monthly_suitability_heatmap.png`

The GitHub Pages publication gallery is under `docs/assets/figures/` and adds:

- `suitability-change-map.svg` / `.png`
- `seasonal-profile-shift.svg` / `.png`
- `population-exposure-map.svg` / `.png`
- `population-exposure-summary.svg` / `.png`
- `rok-aedes-evidence-map.svg` / `.png`
- `pooled-trap-indices.svg` / `.png`

The Korea–Japan outputs are under `outputs/korea_japan/`, including:

- `tables/korea_japan_monthly_suitability.csv`
- `tables/korea_japan_seasonal_summary.csv`
- `tables/korea_japan_seasonal_change_early_to_recent.csv`
- `tables/korea_japan_monthly_change_early_to_recent.csv`
- `tables/korea_japan_missingness.csv`
- `tables/korea_japan_cell_year_season.csv.gz`
- `tables/korea_japan_cell_decadal_season.csv.gz`
- `maps/korea_japan_monthly_heatmap.png`
- `maps/korea_japan_suitable_months_change.png`
- `maps/korea_japan_suitable_span_change.png`

The Korea-first scoped outputs are under `outputs/korea_focus/`, using the same
table and map names with the `korea_focus_` prefix. A public cell grid for the
population export is written as `outputs/korea_focus/korea_focus_cell_grid.geojson`.

## Additional data applications

The repository now includes completed population-exposure and ROK Aedes
data-readiness products alongside still source-gated follow-on analyses:

- `scripts/prepare_population_exposure.py --scope korea` joins the reviewed
  LandScan ambient-population export to the Korea-only public grid. The strict
  run and independent audit pass with complete coverage and reconciliation.
  Results remain population-exposure indicators, not disease incidence or
  individual risk.
- `scripts/audit_rok_aedes.py` passes for 54 reviewed presence-only occurrence
  records and six separate effort-aware trap-index rows. The trap rows are
  pooled across April–November 2013 and 2014, retain 32 trap-nights and 448
  trap-hours per site, and are not monthly raw counts.
- `scripts/analyze_surveillance_lags.py` compares a tidy public monthly vector
  or disease indicator with suitability at explicit leads/lags while retaining
  reporting-change notes. The KDCA and Goyang leads are Anopheles/malaria
  surveillance and must not be treated as direct Aedes validation.
- `scripts/analyze_driver_correlations.py` evaluates descriptive associations
  for temperature, dew point, built fraction, urban population, and growth;
  it reports collinearity diagnostics and does not claim causality or reproduce
  model explainability.
- `scripts/evaluate_early_warning.py` compares seasonal, climate-only, and
  climate-plus-suitability models with temporal holdouts, calibration,
  bootstrap intervals, uncertainty bounds when available, and a provisional
  threshold explicitly marked non-operational.

The remaining source-gated scripts stop with a clear missing-input message
until their input templates are populated and reviewed. This keeps unverified
surveillance, driver, early-warning, or Anopheles event-level data from being
presented as completed results.

## Re-run

From this project directory, place the v2.0 source archives and the Natural Earth boundary file in `source/`, install the packages in `requirements.txt`, and run:

```bash
python3 scripts/analyze_korea.py
python3 scripts/analyze_korea_japan.py --scope korea
```

The included run used the public archives documented in `source/README.md`. The raw archives are not treated as project source code and should be retrieved from the cited record rather than committed to a source repository. Optional dependencies for the early-warning evaluator are listed in `requirements-extensions.txt`.

## Interpretation boundary

The Climademic output is a model-derived environmental suitability score. It
should not be presented as confirmed vector presence, abundance, infection
prevalence, human exposure, or disease transmission risk. The Korea and Japan
products are separate public grid analyses; they are not installation-level,
military-site, or operational early-warning products. Any DPRK interpretation
without direct DPRK observations is modeled extrapolation.

## Human review boundary

The repository owner authorized continued development, commits, publication
figures, impact statements, and a GitHub Pages-ready website. Merging to the
default branch can trigger deployment through the committed workflow. The
owner remains responsible for final release labeling, source verification,
AI disclosure, and any formal `PUB-####` record. The website does not convert
the products into operational disease-risk guidance.
