# ROK *Anopheles sinensis* feasibility schema audit

## Audit conclusion

The repository is currently an Aedes suitability and population-exposure
project. Its modeled suitability table contains `aegypti` and `albopictus`
only. The ROK observation template and `scripts/audit_rok_aedes.py` are also
explicitly Aedes-specific. They should not be reused by changing a species
label to `Anopheles sinensis`.

The repository has enough structure for a small, separate ROK feasibility
exercise, but it does not yet contain a validated Anopheles model input. The
notebook added with this audit uses the public Goyang, Korea supporting data
from Jang and Chun (2020) as a source-linked feasibility input. It treats the
study-labeled weekly average abundance as an observational response and keeps
the study's spatial, temporal, taxonomic, and sampling limitations visible.

## Current repository schema

| Layer | Current schema/status | Implication |
| --- | --- | --- |
| Modeled suitability | `outputs/korea_focus/tables/korea_focus_cell_year_season.csv.gz`; cell-year-season records for `aegypti` and `albopictus` | Aedes-only; not an Anopheles response or suitability layer |
| Aedes observation template | `inputs/aedes_observations.template.csv`; 18 fields including observation type, coordinates, dates, value, effort, taxonomic basis, license, and reporting note | Good provenance pattern, but the current validator rejects Anopheles species |
| Aedes observation audit | `scripts/audit_rok_aedes.py`; canonical country is `South Korea`; allowed species are `Aedes aegypti` and `Aedes albopictus` | Must remain separate from an Anopheles feasibility schema |
| Population exposure | `cell_id,year,ambient_population` | Modeled ambient-population context; not a mosquito observation or disease outcome |
| Anopheles data | No committed Anopheles observation table, model output, or validated species-specific grid layer | Source-gated; no peninsula-wide Anopheles result is authorized |

## Feasibility source

The notebook downloads the supporting workbooks through the article DOI links
when they are absent from the local `tmp/` directory:

- Jang JY, Chun BC. *Association of Anopheles sinensis average abundance and
  climate factors: Use of mosquito surveillance data in Goyang, Korea.* PLOS
  ONE. 2020;15(12):e0244479.
- S1: weekly study-labeled mosquito average abundance and climate variables.
- S2: geographic coordinates for the 12 trap sites.
- License reported by the supporting-data record: CC BY 4.0.

The study describes 2008–2012 surveillance in Goyang, 12 permanent sites, and
9,512 female mosquitoes. The S1 workbook normalizes to 105 weekly records: 21
weeks per year for 2008–2012. This is a local seasonal time series, not a
country-wide surveillance panel.

## Notebook checks

`notebooks/rok_anopheles_sinensis_feasibility.ipynb` performs these checks:

1. Audits the current repository species, geography, period, and template
   fields.
2. Downloads and parses S1/S2 without committing the raw workbooks.
3. Confirms the expected 105 weekly records, five years, 21 weeks per year,
   12 trap coordinates, finite non-negative response values, and broad ROK
   coordinate bounds.
4. Produces seasonal and annual descriptive plots.
5. Uses 2008–2011 for training and 2012 as a temporal holdout for a seasonal
   baseline and a small climate-feature ridge model.
6. Reports that the result is feasibility evidence only; it is not a validated
   species-distribution model, abundance forecast, malaria model, or DPRK
   projection.

## Required next data gate

Before fitting a peninsula-wide Anopheles model, assemble a reviewed ROK table
with species-confirmed observations, trap/site identifiers, coordinates,
collection dates, sampling effort, taxonomic basis, and source licenses. The
next validation design should include site-blocked spatial holdouts and
year-blocked temporal holdouts. Only after those checks should the project
consider whether the Aedes covariates and grid can support a separate
Anopheles model branch.
