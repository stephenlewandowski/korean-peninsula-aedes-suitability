# Heat, humidity, land-use, and population-driver protocol

## Question

Assess whether temperature, dew point, land use, and population growth are
associated with changing suitability in the public regional grid, while
recognizing that correlated predictors and the model's explainability results
can support different interpretations.

## Input design

`inputs/drivers_monthly.csv` follows the template with one row per geography,
month, and year. It stores:

- air temperature in degrees Celsius;
- dew point in degrees Celsius as a humidity-related variable;
- `built_fraction` as a documented land-use or built-surface measure;
- annual or monthly `urban_population`; and
- a documented `population_growth_rate`.

Every variable needs a source ID, resolution, processing note, and temporal
support. Annual land-use variables may be repeated across months only when that
choice is recorded. Population variables should not be mixed with the
LandScan exposure table without documenting whether they are the same source
and whether they represent ambient or resident population.

## Analysis

`scripts/analyze_driver_correlations.py` aligns the drivers to the same public
geographies and area-weighted suitability series, then writes pairwise Pearson
and Spearman associations plus a driver-matrix condition-number diagnostic.
The outputs are descriptive and should be stratified or sensitivity-tested by
period, geography, and species before interpretation.

Temperature and dew point are expected to be correlated; built fraction,
urban population, and population growth may share temporal trends. A strong
pairwise association can therefore be unstable under alternative covariate
sets. The condition number is a screening diagnostic, not a formal causal
identification test.

## Explainability boundary

The Climademic paper's explainability results, if used, must be cited and
quoted as model-specific attribution evidence. They should not be replaced by
the correlations in this repository. A model feature-importance result does
not establish a causal effect, and a regional driver correlation does not
reconstruct the paper's internal attribution. Any comparison must state which
predictors, training data, and spatial/temporal support differ.

No causal claim, mediation claim, or urbanization effect is authorized by the
current prototype.
