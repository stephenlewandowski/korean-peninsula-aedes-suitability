# Input tables

The project keeps large external raster inputs out of the repository. The
template `landscan_population_by_cell_year.template.csv` defines the tidy
population table consumed by `scripts/prepare_population_exposure.py`:

```text
cell_id,year,ambient_population
```

`cell_id` must match the public 0.25-degree suitability grid, `year` must be
between 1975 and 2024, and `ambient_population` must be a non-negative number
of people for that analysis cell and year. The source is the LandScan Mosaic
annual ambient-population time series. `scripts/build_cell_grid_geojson.py`
writes the matching public polygon grid, and
`scripts/landscan_gee_export.js` provides a reviewed Earth Engine export
starting point; upload that grid to Earth Engine and replace the placeholder
cell-grid asset before running it.

No population exposure result is claimed until the export has passed duplicate,
unit, coverage, and spatial-alignment checks. Ambient population is used only as
an exposure denominator/weight. It is not disease incidence, infection,
individual risk, or transmission probability.

## Republic of Korea Aedes observations

`aedes_observations.template.csv` defines the separate ROK validation input for
public occurrence and trap observations. Use one row per observation or
observation-period record and retain the source identifier, observation type,
coordinates, collection date or month, sampling effort, taxonomic basis,
license, and reporting note. `occurrence`, `trap_presence`, and
`trap_abundance` rows are intentionally kept distinct; trap abundance is not
silently converted into presence or merged with opportunistic occurrences.

Build the source-screened occurrence import with:

```bash
python3 scripts/build_rok_aedes_observations.py
```

The builder records the GBIF query, source dataset metadata, per-record
licenses, occurrence identifiers, exact grid-join status, and an SHA-256 hash
in `metadata/rok_aedes_source_registry.json`. It excludes year-only records
instead of fabricating a month and leaves `sampling_effort` blank for
occurrence records whose source does not report a standardized denominator.

Run the schema/readiness audit with:

```bash
python3 scripts/audit_rok_aedes.py \
  --observations inputs/aedes_observations.csv \
  --output-dir outputs/rok_aedes_validation
```

The current audit is a source-readiness result, not a fitted model or
validation metric. Occurrence rows are not converted into trap abundance or
effort-standardized rates.
