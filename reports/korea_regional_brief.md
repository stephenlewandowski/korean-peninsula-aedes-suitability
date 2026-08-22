# Korean Peninsula Climademic regional brief

## Scope

This brief uses Climademic Suitability Model version 2.0 for 1975–2024 and restricts all results to North Korea and South Korea. It includes *Aedes aegypti* and *Aedes albopictus* and excludes Japan. Primary regional means are cosine(latitude)-weighted across valid 0.25° grid-cell observations.

## Suitable-month count

Suitable-month count is the number of months in a year with model suitability at or above 0.5. The primary mean is calculated from complete 12-month cell-years. The source paper describes 0.5 as the decision boundary; the count is therefore a transparent classification summary, not a new biological threshold.

| Geography | Species | 1975–1984 | 1995–2004 | 2015–2024 | Recent minus early |
|---|---|---:|---:|---:|---:|
| Korean Peninsula | *Ae. aegypti* | 2.67 | 2.90 | 3.24 | +0.57 |
| Korean Peninsula | *Ae. albopictus* | 4.21 | 4.46 | 4.71 | +0.50 |
| North Korea | *Ae. aegypti* | 2.12 | 2.35 | 2.63 | +0.51 |
| North Korea | *Ae. albopictus* | 3.65 | 3.94 | 4.15 | +0.50 |
| South Korea | *Ae. aegypti* | 3.40 | 3.64 | 4.04 | +0.65 |
| South Korea | *Ae. albopictus* | 4.95 | 5.14 | 5.46 | +0.51 |

The regional spread is material: the 25th–75th percentile of cell-year suitable-month counts is 2–4 months for *Ae. aegypti* and 4–5 months for *Ae. albopictus* in the recent decade. These distributions describe spatial and interannual variation among selected cells; they are not model confidence intervals.

## Monthly suitability: combined peninsula

Values below are area-weighted mean suitability scores. The complete monthly table, including medians, quartiles, shares of suitable cell area, valid counts, and missingness, is in `outputs/tables/korea_regional_monthly_suitability.csv`.

| Month | *Ae. aegypti* early | *Ae. aegypti* recent | *Ae. albopictus* early | *Ae. albopictus* recent |
|---|---:|---:|---:|---:|
| January | 0.001 | 0.001 | 0.001 | 0.001 |
| February | 0.001 | 0.001 | 0.001 | 0.002 |
| March | 0.001 | 0.002 | 0.008 | 0.024 |
| April | 0.029 | 0.046 | 0.080 | 0.110 |
| May | 0.129 | 0.192 | 0.330 | 0.429 |
| June | 0.437 | 0.529 | 0.666 | 0.734 |
| July | 0.611 | 0.681 | 0.759 | 0.791 |
| August | 0.617 | 0.661 | 0.756 | 0.772 |
| September | 0.340 | 0.466 | 0.561 | 0.671 |
| October | 0.068 | 0.089 | 0.173 | 0.229 |
| November | 0.004 | 0.007 | 0.030 | 0.042 |
| December | 0.001 | 0.001 | 0.002 | 0.002 |

The strongest recent-period increases occur in the shoulder months, especially May, June, and September. The interpretation is a shift in the modelled monthly suitability profile, not proof that a vector population or transmission season has expanded by the same amount.

## Static visual products

`outputs/maps/korea_suitable_months_decades.png` shows the spatial distribution of mean suitable-month count for the three comparison decades. `outputs/maps/korea_suitable_months_change_early_to_recent.png` shows the recent-minus-early change for each species. `outputs/maps/korea_monthly_suitability_heatmap.png` shows the regional monthly profiles, and `korea_mean_suitability_decades.png` shows mean annual suitability.
