#!/usr/bin/env python3
"""Test lags between regional suitability and a tidy surveillance series.

This script is deliberately outcome-agnostic. It accepts a documented public
surveillance indicator (for example a monthly count, rate, or trap index),
keeps source and reporting-change fields beside the value, and reports simple
lag correlations as exploratory diagnostics. It does not produce a disease
forecast and does not turn suitability into infection or transmission risk.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MONTH_COLUMNS = [f"m{month:02d}" for month in range(1, 13)]
GEOGRAPHY_SPEC = (
    ("North Korea", ("North Korea",)),
    ("South Korea", ("South Korea",)),
    ("Korean Peninsula", ("North Korea", "South Korea")),
    ("Japan", ("Japan",)),
    ("Korea-Japan", ("North Korea", "South Korea", "Japan")),
)
REQUIRED_COLUMNS = {
    "source_id",
    "geography",
    "suitability_species",
    "year",
    "month",
    "indicator",
    "value",
    "unit",
    "denominator",
    "n_sites",
    "n_traps",
    "n_tested",
    "case_definition",
    "reporting_change_note",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--surveillance",
        type=Path,
        default=PROJECT_ROOT / "inputs" / "surveillance_monthly.csv",
    )
    parser.add_argument(
        "--suitability",
        type=Path,
        default=PROJECT_ROOT
        / "outputs"
        / "korea_japan"
        / "tables"
        / "korea_japan_cell_year_season.csv.gz",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "outputs" / "surveillance_lags",
    )
    parser.add_argument("--max-lag", type=int, default=6)
    return parser.parse_args()


def read_surveillance(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, keep_default_na=False)
    missing = REQUIRED_COLUMNS - set(frame.columns)
    if missing:
        raise ValueError(f"Surveillance table is missing columns: {sorted(missing)}")
    frame = frame.copy()
    frame["year"] = pd.to_numeric(frame["year"], errors="coerce")
    frame["month"] = pd.to_numeric(frame["month"], errors="coerce")
    frame["value"] = pd.to_numeric(frame["value"], errors="coerce")
    for column in ("denominator", "n_sites", "n_traps", "n_tested"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if frame[["year", "month", "value"]].isna().any().any():
        raise ValueError("Surveillance year, month, and value must be numeric")
    frame["year"] = frame["year"].astype(int)
    frame["month"] = frame["month"].astype(int)
    if not frame["year"].between(1975, 2024).all():
        raise ValueError("Surveillance data must fall within 1975–2024")
    if not frame["month"].between(1, 12).all():
        raise ValueError("Surveillance month must be between 1 and 12")
    if not np.isfinite(frame["value"]).all():
        raise ValueError("Surveillance values must be finite")
    frame["reporting_change_flag"] = frame["reporting_change_note"].astype(str).str.strip().ne("")
    frame["month_index"] = frame["year"] * 12 + frame["month"]
    return frame


def read_suitability(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(
        path,
        usecols=["species", "country", "cell_id", "area_weight", "year", *MONTH_COLUMNS],
    )
    frame["year"] = pd.to_numeric(frame["year"], errors="raise").astype(int)
    frame["area_weight"] = pd.to_numeric(frame["area_weight"], errors="raise")
    if frame.duplicated(["species", "cell_id", "year"]).any():
        raise ValueError("Suitability cell-year table has duplicate species-cell-year rows")
    return frame


def regional_suitability(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for species in sorted(frame["species"].unique()):
        species_data = frame[frame["species"].eq(species)]
        for geography, countries in GEOGRAPHY_SPEC:
            subset = species_data[species_data["country"].isin(countries)]
            for year, year_data in subset.groupby("year", sort=True):
                weights = year_data.get("area_weight")
                if weights is None:
                    weights = np.ones(len(year_data), dtype=float)
                else:
                    weights = weights.to_numpy(dtype=float)
                row: dict[str, object] = {
                    "geography": geography,
                    "suitability_species": species,
                    "year": int(year),
                }
                for month_number, column in enumerate(MONTH_COLUMNS, start=1):
                    values = year_data[column].to_numpy(dtype=float)
                    valid = np.isfinite(values) & (values >= 0) & (values <= 1)
                    if valid.any() and weights[valid].sum() > 0:
                        row[f"suitability_m{month_number:02d}"] = float(
                            np.average(values[valid], weights=weights[valid])
                        )
                    else:
                        row[f"suitability_m{month_number:02d}"] = math.nan
                rows.append(row)
    return pd.DataFrame(rows)


def long_suitability(regional: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for _, row in regional.iterrows():
        for month in range(1, 13):
            rows.append(
                {
                    "geography": row["geography"],
                    "suitability_species": row["suitability_species"],
                    "year": int(row["year"]),
                    "month": month,
                    "suitability": row[f"suitability_m{month:02d}"],
                    "month_index": int(row["year"]) * 12 + month,
                }
            )
    return pd.DataFrame(rows)


def lag_rows(surveillance: pd.DataFrame, suitability: pd.DataFrame, max_lag: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    suit = long_suitability(suitability)
    correlation_rows: list[dict[str, object]] = []
    coverage_rows: list[dict[str, object]] = []
    for (source_id, geography, species, indicator), outcome in surveillance.groupby(
        ["source_id", "geography", "suitability_species", "indicator"], sort=True
    ):
        for lag in range(-max_lag, max_lag + 1):
            candidate = outcome[["year", "month", "value", "reporting_change_flag"]].copy()
            candidate["month_index"] = candidate["year"] * 12 + candidate["month"]
            candidate["suitability_month_index"] = candidate["month_index"] - lag
            matched = candidate.merge(
                suit[
                    (suit["geography"].eq(geography))
                    & (suit["suitability_species"].eq(species))
                ][["month_index", "suitability"]],
                left_on="suitability_month_index",
                right_on="month_index",
                how="left",
                suffixes=("", "_suitability"),
            )
            valid = matched.dropna(subset=["value", "suitability"])
            n_flagged = int(valid["reporting_change_flag"].sum())
            coverage_rows.append(
                {
                    "source_id": source_id,
                    "geography": geography,
                    "suitability_species": species,
                    "indicator": indicator,
                    "lag_months": lag,
                    "n_surveillance_rows": int(len(candidate)),
                    "n_matched_rows": int(len(valid)),
                    "n_reporting_change_flagged_matched_rows": n_flagged,
                    "reporting_change_flag_fraction": (
                        float(n_flagged / len(valid)) if len(valid) else math.nan
                    ),
                }
            )
            for method in ("pearson", "spearman"):
                correlation = math.nan
                if len(valid) >= 3 and valid["value"].nunique() > 1 and valid["suitability"].nunique() > 1:
                    correlation = float(valid["value"].corr(valid["suitability"], method=method))
                correlation_rows.append(
                    {
                        "source_id": source_id,
                        "geography": geography,
                        "suitability_species": species,
                        "indicator": indicator,
                        "lag_months": lag,
                        "lag_definition": "positive lag means suitability leads the surveillance month",
                        "method": method,
                        "correlation": correlation,
                        "n_matched_rows": int(len(valid)),
                        "n_reporting_change_flagged_matched_rows": n_flagged,
                    }
                )
    return pd.DataFrame(correlation_rows), pd.DataFrame(coverage_rows)


def main() -> None:
    args = parse_args()
    if not args.surveillance.exists():
        raise FileNotFoundError(
            f"Missing surveillance table: {args.surveillance}. "
            "Populate inputs/surveillance_monthly.template.csv and save it as surveillance_monthly.csv."
        )
    if args.max_lag < 0 or args.max_lag > 24:
        raise ValueError("--max-lag must be between 0 and 24 months")
    surveillance = read_surveillance(args.surveillance)
    suitability = read_suitability(args.suitability)
    regional = regional_suitability(suitability)
    correlations, coverage = lag_rows(surveillance, regional, args.max_lag)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    regional.to_csv(args.output_dir / "surveillance_suitability_monthly.csv", index=False, float_format="%.6f")
    correlations.to_csv(args.output_dir / "surveillance_lag_correlations.csv", index=False, float_format="%.6f")
    coverage.to_csv(args.output_dir / "surveillance_lag_coverage.csv", index=False, float_format="%.6f")
    print(
        {
            "surveillance_rows": len(surveillance),
            "regional_suitability_rows": len(regional),
            "lag_rows": len(correlations),
        }
    )


if __name__ == "__main__":
    main()
