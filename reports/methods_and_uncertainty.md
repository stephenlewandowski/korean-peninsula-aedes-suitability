# Methods, missingness, and uncertainty record

## Data extraction

The analysis uses the authors' current Zenodo record 21924442, version 2.0. Each species archive contains 50 GeoTIFF files, one for each year from 1975 through 2024. Each GeoTIFF contains 12 monthly layers in January–December order. The source specification identifies EPSG:4326, 0.25° grid spacing, a global extent of longitude -180° to +180° and latitude +83.75° to -56°, valid values from 0 to 1, and -1.0 as the no-data value.

The code reads the raster arrays directly from the ZIP archives, verifies the 50-year inventory and common raster shape, and extracts a regional window covering approximately 123.0–132.5°E and 32.0–44.0°N. The target geography is defined by Natural Earth 10m administrative country polygons for North Korea and South Korea. A source grid cell is included when its center point falls within one of those polygons. This keeps the analysis at the source grid resolution and avoids implying sub-grid precision.

The run selected 370 cells: 215 in North Korea and 155 in South Korea. The combined peninsula geography is the union of the two country masks. Coastal cells are not clipped by fractional polygon intersection; this is a known edge approximation and is recorded in `metadata/korea_analysis_run_metadata.json`.

## Aggregation

For each country and for the combined peninsula, the monthly regional mean is a cosine(latitude)-weighted mean of valid grid-cell values. The weight approximates the different surface areas of equal-degree cells at different latitudes. The tables also retain an unweighted mean, median, 25th percentile, 75th percentile, and sample standard deviation so that spatial/temporal dispersion and aggregation sensitivity remain visible.

The primary suitable-month count is calculated in two stages:

1. For each cell and year, classify a month as suitable when the model score is `>= 0.5`.
2. Count suitable months in that year. For the primary season-length summary, use only cell-years with all 12 months valid; retain the observed-month count and coverage diagnostics separately.

This is a count of suitable calendar months. It does not require the suitable months to form one uninterrupted sequence and therefore should not be described as a precise onset date, end date, or transmission duration.

The comparison periods are 1975–1984, 1995–2004, and 2015–2024. The full cell-year extract retains the intervening years and labels them `intermediate`; they are not silently discarded from the raw extraction, but they are outside the three-period comparison tables.

## Missingness

No imputation is performed. Values equal to -1.0, NaN, or outside the documented [0, 1] range are treated as missing. Missingness is reported by species, geography, period, and month in `outputs/tables/korea_missingness_summary.csv`; valid and missing counts are also included in the monthly suitability table.

In the v2.0 run, the selected target cells had complete monthly coverage for the three comparison decades: missing fraction 0.0 and complete 12-month cell-year fraction 1.0. This result is local to the selected region and release. It does not mean that the global source has no missing values, nor does it remove uncertainty created by model extrapolation or sparse observations.

## Uncertainty and interpretation

The source describes the output as modelled habitat suitability probabilities, while the paper explains that the underlying one-class SVM decision scores are mapped to probability-like outputs. The product therefore treats the values as model-derived suitability scores and preserves the authors' 0.5 decision boundary for the binary suitable-month count. It does not create a confidence interval or claim calibrated probability of mosquito presence.

The source release does not provide a per-cell model-uncertainty layer. Quartiles, standard deviations, valid counts, and missingness in this product are descriptive variability indicators. They should not be read as statistical confidence intervals. Important uncertainty sources include:

- model dependence on climate, land-use, population, and mosquito-occurrence inputs;
- occurrence-reporting and surveillance bias, including uneven coverage across countries and years;
- the distinction between environmental suitability, vector presence, abundance, infection, and transmission;
- spatial averaging and the 0.25° grid, especially at coastlines and the inter-Korean boundary;
- temporal autocorrelation and the non-independence of nearby cells and adjacent years;
- the preprint status of the accompanying scientific paper; and
- possible conflation of environmental change with dispersal, reporting, or model-update effects.

The DPRK portion is a modelled regional result, not direct DPRK surveillance. The product should not be used as an installation-level, military-site, clinical, or operational early-warning map. Any follow-on validation should use independent Korean surveillance data with spatial and temporal holdouts and should keep suitability separate from disease outcomes.
