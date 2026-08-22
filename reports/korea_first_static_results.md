# Korea-first static results

This brief reports the scoped rerun for North Korea, South Korea, and the
combined Korean Peninsula. It uses the v2.0 Aedes rasters, the 0.5 suitability
threshold, cosine-latitude weights, and the three comparison periods in
`outputs/korea_focus/`.

## Early-to-recent change

Values are area-weighted means; changes are 2015–2024 minus 1975–1984. Onset
and end are calendar months, not exact dates. Span is last suitable month minus
first suitable month plus one.

| Geography | Species | Suitable months early | Suitable months recent | Change | Onset change | End change | Span change |
|---|---|---:|---:|---:|---:|---:|---:|
| Korean Peninsula | *Ae. aegypti* | 2.67 | 3.24 | +0.57 | −0.19 | +0.20 | +0.59 |
| Korean Peninsula | *Ae. albopictus* | 4.21 | 4.71 | +0.50 | −0.28 | +0.23 | +0.51 |
| North Korea | *Ae. aegypti* | 2.12 | 2.63 | +0.51 | −0.09 | +0.18 | +0.53 |
| North Korea | *Ae. albopictus* | 3.65 | 4.15 | +0.50 | −0.31 | +0.21 | +0.51 |
| South Korea | *Ae. aegypti* | 3.40 | 4.04 | +0.65 | −0.35 | +0.25 | +0.65 |
| South Korea | *Ae. albopictus* | 4.95 | 5.46 | +0.51 | −0.24 | +0.27 | +0.50 |

These are changes in modeled environmental suitability only. They are not
observations of mosquitoes, disease incidence, individual risk, or transmission
probability. North Korea values carry an explicit modeled-extrapolation flag.

## Coverage and uncertainty

The scoped extraction contains 215 North Korea cells and 155 South Korea cells
(370 total), with 37,000 species-cell-year rows and 2,960 species-cell-period
rows. The source values selected for the three periods have zero missing cell-
month observations under the current missingness rule. That complete coverage
does not create model uncertainty intervals: the source release does not supply
a per-cell uncertainty layer. Quantiles, spread, and valid counts remain
descriptive diagnostics.

## Reproduce

```bash
python3 scripts/analyze_korea_japan.py --scope korea
python3 scripts/validate_korea_japan.py --scope korea
```
