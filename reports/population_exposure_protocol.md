# Population-exposure application protocol

## Purpose

This Korea-first application asks how many people live in North Korea and South
Korea cells where modeled suitability increased or the modeled suitable season
became longer. It is an exposure description, not a disease-incidence,
infection, individual-risk, or transmission estimate. Japan is maintained as a
separate comparator and is not included in this population join.

## Population source and extraction

The intended source is the LandScan Mosaic Annual Global Ambient Population
Time Series, Version 1.0, published by Oak Ridge National Laboratory:

- [official dataset landing page](https://impact.ornl.gov/en/datasets/landscan-mosaic-annual-global-ambient-population-time-series-vers/)
- [dataset DOI](https://doi.org/10.48690/lsm/zew2-1n91)
- [LandScan portal](https://landscan.ornl.gov/)
- [Earth Engine community catalog entry](https://gee-community-catalog.org/projects/landcast/)
- Earth Engine collection: `projects/sat-io/open-datasets/ORNL/LANDSCAN_MOSAIC_TIMESERIES`

The official record describes one COG GeoTIFF per year on a globally aligned
3-arc-second WGS84 grid for 1975–2024. The intended band is `ambient`, which
the community catalog describes as the number of people per grid cell. The
2024 layer is the benchmark; earlier years are reconstructed through the
LandCast approach. These source facts do not remove uncertainty from the
historical reconstruction.

`scripts/landscan_gee_export.js` is a starting-point Korea-only export. It
requires a public, non-installation-specific FeatureCollection of the same
0.25-degree analysis-cell polygons used by
`analyze_korea_japan.py --scope korea`; `scripts/build_cell_grid_geojson.py
--scope korea` creates that polygon grid from the committed Korea-first
cell-year extract. The export sums fine-grid values inside each analysis cell
and writes `cell_id`, `year`, and `ambient_population`. It does not export
installation-level locations or clip the cell footprint to an administrative
border.

## Aggregation

For cell `i`, year `t`, and geography `g`, let `p(i,t)` be the ambient
population exported for the cell and let `s(i,t)` be the suitability-derived
cell metric. The period population is the mean of `p(i,t)` over the ten years;
the population total is the sum of those cell means in the geography. The
population-weighted suitability metric is:

\[
  S^P_{g,t} = \frac{\sum_{i \in g} \bar p_i S_i}{\sum_{i \in g} \bar p_i}
\]

The change table uses the recent-period mean ambient population to count people
living in cells with a positive early-to-recent change in suitable-month count,
suitable-season span, or longest contiguous run. Cells with missing population
or incomplete suitability are reported in coverage fields rather than silently
imputed.

## Missingness and uncertainty

The preparation script rejects duplicate cell-year rows, nonnumeric years,
negative population, non-finite values, and cells outside the selected public
analysis grid. It reports expected and observed cell-year rows by country and
period. `--require-complete` can be used for a strict Korea run after the
export is checked.

LandScan historical layers are scenario-based reconstructions anchored to a
benchmark, so reconstructed population, built-surface assumptions,
interpolation, input data, and normalization each contribute uncertainty. The
current prototype does not have a cell-level uncertainty band for population;
population-weighted values should therefore be reported with coverage and
source limitations, not as exact counts of people at risk.

## Current status

The repository contains the extraction code, template, and provenance contract.
No Korea population exposure result is claimed until a LandScan export has
been aligned, checked, and saved as `inputs/landscan_population_by_cell_year.csv`.
