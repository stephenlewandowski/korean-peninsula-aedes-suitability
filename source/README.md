# Source retrieval record

The analysis uses the current repository-linked data release identified in the 2026-08-16 Climademic reference:

- Dataset record: <https://zenodo.org/records/21924442>
- Model repository: <https://github.com/ClimSocAna/climademic_suitability_model>
- Data specification: `Data_Specification.pdf`
- Boundary source: <https://github.com/nvkelso/natural-earth-vector/blob/master/geojson/ne_10m_admin_0_countries.geojson>

The Zenodo release was retrieved on 2026-08-19. The record reports version 2.0, CC BY 4.0, and open access. The two ZIP archives are intentionally not committed to the project package because they are large derived inputs. Retrieve them with:

```bash
curl -L --fail https://zenodo.org/api/records/21924442/files/aegypti.zip/content -o source/aegypti.zip
curl -L --fail https://zenodo.org/api/records/21924442/files/albopictus.zip/content -o source/albopictus.zip
curl -L --fail https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_admin_0_countries.geojson -o source/ne_10m_admin_0_countries.geojson
```

Record-level MD5 checksums reported by Zenodo:

| File | Size | MD5 |
|---|---:|---|
| `Data_Specification.pdf` | 179,909 bytes | `ddc2fc0c80a62538d9ecb6f19d90a756` |
| `aegypti.zip` | 33,795,708 bytes | `42104d7f387f2798580370dcd7680706` |
| `albopictus.zip` | 34,653,850 bytes | `85d7515d965a524b7bfc978fddd707c8` |

The run's SHA-256 values and the exact scope and transformation choices are in `metadata/korea_analysis_run_metadata.json`.

## Follow-on application sources

The Korea–Japan seasonal extension uses the same Climademic Aedes archives and
Natural Earth boundary, but includes Japan as a public regional comparison.
Its source hashes and aggregation definitions are in
`metadata/korea_japan_run_metadata.json`.

The population-exposure application is prepared for the [LandScan Mosaic
Annual Global Ambient Population Time Series, Version 1.0](https://impact.ornl.gov/en/datasets/landscan-mosaic-annual-global-ambient-population-time-series-vers/)
and its [Earth Engine community catalog entry](https://gee-community-catalog.org/projects/landcast/).
The intended Earth Engine collection is
`projects/sat-io/open-datasets/ORNL/LANDSCAN_MOSAIC_TIMESERIES`, using the
`ambient` band for 1975–2024. The project does not commit those large rasters.
Run `scripts/landscan_gee_export.js` only after replacing its placeholder with
the public 0.25-degree cell-grid asset, then inspect the resulting CSV with
`scripts/prepare_population_exposure.py`.

The [KDCA malaria vector surveillance report](https://www.kdca.go.kr/bbs/chungcheong/142/293598/download.do)
and [Goyang PLOS One study](https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0244479)
are registered leads for a separate ROK Anopheles/malaria validation branch.
They are not direct validation of the Aedes suitability output. See
`reports/surveillance_comparison_protocol.md` for observation-type, lag, and
reporting-change rules.
