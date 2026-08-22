# Korea-first follow-on application source record

This record supports the Korea-first population, ROK validation, driver,
surveillance, early-warning, and teaching extensions. Japan is maintained as
IDEA-0007 and Anopheles as IDEA-0008. It does not turn a source lead into a
completed analysis result.

## Population exposure

- Oak Ridge National Laboratory, *LandScan Mosaic Annual Global Ambient
  Population Time Series, Version 1.0*: [official landing page](https://impact.ornl.gov/en/datasets/landscan-mosaic-annual-global-ambient-population-time-series-vers/),
  [DOI](https://doi.org/10.48690/lsm/zew2-1n91), and [LandScan portal](https://landscan.ornl.gov/).
- Community catalog documentation: [LandCast Mosaic project](https://gee-community-catalog.org/projects/landcast/).
  The catalog identifies the Earth Engine collection as
  `projects/sat-io/open-datasets/ORNL/LANDSCAN_MOSAIC_TIMESERIES`, the `ambient`
  band, one annual image for 1975–2024, and methodological assumptions that
  must accompany interpretation.
- Methodology leads supplied for follow-up: [preprint DOI
  10.31223/X5MV3R](https://doi.org/10.31223/X5MV3R), [LandCast Mosaic report DOI
  10.2172/3015559](https://doi.org/10.2172/3015559), and [benchmark-method paper
  DOI 10.1038/s41598-025-28125-z](https://doi.org/10.1038/s41598-025-28125-z).

## Korean surveillance leads

- KDCA, *Malaria Vector Surveillance in 2024*: [official report PDF](https://www.kdca.go.kr/bbs/chungcheong/142/293598/download.do).
  This is a Republic of Korea malaria-vector surveillance lead, not direct DPRK
  coverage and not an Aedes/dengue outcome.
- Jang and Chun, *Association of Anopheles sinensis average abundance and
  climate factors: Use of mosquito surveillance data in Goyang, Korea*:
  [PLOS One article](https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0244479).
  Use as a separate ROK Anopheles feasibility/validation lead; retain the study's
  observation and identification limitations.

## Core modeled-suitability sources

The Aedes rasters and model context remain registered in `data/sources.csv` as
SRC-0010 through SRC-0013. The scoped script uses the same Zenodo release,
Natural Earth boundary, 0.25-degree grid, missingness rule, and threshold as
the initial Korea-only application. The active population and validation work
is Korea-only.
