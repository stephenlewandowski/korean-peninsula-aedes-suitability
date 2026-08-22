# Archived Korea–Japan seasonal suitability brief

> This is a retained comparison archive. The active Korea-first product is
> `outputs/korea_focus/`; the Japan-only comparator is IDEA-0007. Do not treat
> this combined table as the primary scope for new population, surveillance,
> or validation work.

## Scope

This follow-on extracts the public 0.25-degree Climademic Aedes rasters for
North Korea, South Korea, Japan, and combined regional summaries. It compares
1975–1984, 1995–2004, and 2015–2024 for *Aedes aegypti* and *Aedes
albopictus*. The analysis is regional and non-installation-specific.

The primary seasonal threshold is suitability `>= 0.5`. “Suitable months” is
the count of suitable calendar months. “Onset” is the first suitable calendar
month and “end” is the last; both are averaged across complete cell-years.
“First-to-last span” is `end - onset + 1` and can exceed the count when suitable
months are not contiguous. The longest contiguous run is reported separately
and does not wrap December to January.

## Early-to-recent comparison

Values below are area-weighted means from
`outputs/korea_japan/tables/korea_japan_seasonal_change_early_to_recent.csv`.
Changes are recent minus early; negative onset change means an earlier calendar
month, while positive end change means a later calendar month.

| Geography | Species | Suitable months early | Suitable months recent | Change | Onset change (months) | End change (months) | Span change (months) | Longest-run change (months) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Korean Peninsula | *Ae. aegypti* | 2.67 | 3.24 | +0.57 | -0.19 | +0.20 | +0.59 | +0.55 |
| Korean Peninsula | *Ae. albopictus* | 4.21 | 4.71 | +0.50 | -0.28 | +0.23 | +0.51 | +0.49 |
| Japan | *Ae. aegypti* | 2.80 | 3.41 | +0.61 | -0.20 | +0.21 | +0.65 | +0.56 |
| Japan | *Ae. albopictus* | 4.63 | 5.15 | +0.52 | -0.32 | +0.20 | +0.55 | +0.48 |
| Korea–Japan | *Ae. aegypti* | 2.75 | 3.34 | +0.59 | -0.20 | +0.21 | +0.63 | +0.55 |
| Korea–Japan | *Ae. albopictus* | 4.47 | 4.99 | +0.51 | -0.31 | +0.22 | +0.53 | +0.48 |

These are changes in modeled environmental suitability under the supplied
model, threshold, boundary mask, and aggregation choices. They are not
observations of mosquitoes, infection, disease incidence, human exposure, or
transmission. North Korea rows carry a modeled-extrapolation flag because no
direct DPRK occurrence or surveillance records are included.

## Reproducibility

```bash
python3 scripts/analyze_korea_japan.py
python3 scripts/validate_korea_japan.py
```

The extraction and figure code is in
`scripts/analyze_korea_japan.py`; the output contract is checked by
`scripts/validate_korea_japan.py`. Missing values are not imputed. Quantiles,
spread, and valid counts are descriptive variability indicators; the source
release does not supply a per-cell model-uncertainty raster for this product.
