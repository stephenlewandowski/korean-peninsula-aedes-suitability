#!/usr/bin/env python3
"""Relate monthly climate/urban drivers to regional suitability descriptively.

The script is an exploratory companion to the suitability extraction. It
reports pairwise correlations and a condition number for the supplied driver
matrix; it does not claim causal effects or reproduce the Climademic model's
internal feature attribution. Land-use and population variables must already
be aligned to the public analysis geography and documented with their own
source and resolution.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DRIVER_COLUMNS = (
    "temperature_c",
    "dew_point_c",
    "built_fraction",
    "urban_population",
    "population_growth_rate",
)
MONTH_COLUMNS = [f"m{month:02d}" for month in range(1, 13)]
GEOGRAPHY_SPEC = (
    ("North Korea", ("North Korea",)),
    ("South Korea", ("South Korea",)),
    ("Korean Peninsula", ("North Korea", "South Korea")),
    ("Japan", ("Japan",)),
    ("Korea-Japan", ("North Korea", "South Korea", "Japan")),
)
REQUIRED_DRIVER_COLUMNS = {
    "source_id",
    "geography",
    "year",
    "month",
    *DRIVER_COLUMNS,
    "source_resolution",
    "processing_note",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--drivers",
        type=Path,
        default=PROJECT_ROOT / "inputs" / "drivers_monthly.csv",
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
        default=PROJECT_ROOT / "outputs" / "driver_analysis",
    )
    return parser.parse_args()


def read_drivers(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, keep_default_na=False)
    missing = REQUIRED_DRIVER_COLUMNS - set(frame.columns)
    if missing:
        raise ValueError(f"Driver table is missing columns: {sorted(missing)}")
    frame = frame.copy()
    frame["year"] = pd.to_numeric(frame["year"], errors="coerce")
    frame["month"] = pd.to_numeric(frame["month"], errors="coerce")
    for column in DRIVER_COLUMNS:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if frame[["year", "month"]].isna().any().any():
        raise ValueError("Driver year and month must be numeric")
    frame["year"] = frame["year"].astype(int)
    frame["month"] = frame["month"].astype(int)
    if not frame["year"].between(1975, 2024).all() or not frame["month"].between(1, 12).all():
        raise ValueError("Driver rows must fall within 1975–2024 and months 1–12")
    return frame


def read_suitability(path: Path) -> pd.DataFrame:
    return pd.read_csv(
        path,
        usecols=["species", "country", "year", "area_weight", *MONTH_COLUMNS],
    )


def regional_suitability(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for species in sorted(frame["species"].unique()):
        species_data = frame[frame["species"].eq(species)]
        for geography, countries in GEOGRAPHY_SPEC:
            subset = species_data[species_data["country"].isin(countries)]
            for year, year_data in subset.groupby("year", sort=True):
                weights = year_data["area_weight"].to_numpy(dtype=float)
                row: dict[str, object] = {
                    "geography": geography,
                    "suitability_species": species,
                    "year": int(year),
                }
                for month, column in enumerate(MONTH_COLUMNS, start=1):
                    values = year_data[column].to_numpy(dtype=float)
                    valid = np.isfinite(values) & (values >= 0) & (values <= 1)
                    row[f"month_{month:02d}"] = (
                        float(np.average(values[valid], weights=weights[valid]))
                        if valid.any() and weights[valid].sum() > 0
                        else math.nan
                    )
                rows.append(row)
    long = pd.DataFrame(rows).melt(
        id_vars=["geography", "suitability_species", "year"],
        value_vars=[f"month_{month:02d}" for month in range(1, 13)],
        var_name="month_label",
        value_name="suitability",
    )
    long["month"] = long["month_label"].str[-2:].astype(int)
    return long.drop(columns="month_label")


def correlation_rows(merged: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for (geography, species), group in merged.groupby(
        ["geography", "suitability_species"], sort=True
    ):
        for variable in DRIVER_COLUMNS:
            subset = group[["suitability", variable]].dropna()
            rows.append(
                {
                    "geography": geography,
                    "suitability_species": species,
                    "driver": variable,
                    "n_months": int(len(subset)),
                    "pearson_r": (
                        float(subset["suitability"].corr(subset[variable], method="pearson"))
                        if len(subset) >= 3 and subset[variable].nunique() > 1
                        else math.nan
                    ),
                    "spearman_r": (
                        float(subset["suitability"].corr(subset[variable], method="spearman"))
                        if len(subset) >= 3 and subset[variable].nunique() > 1
                        else math.nan
                    ),
                    "interpretation": "Descriptive association; not a causal or model-attribution estimate",
                }
            )
    return pd.DataFrame(rows)


def collinearity_rows(drivers: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for geography, group in drivers.groupby("geography", sort=True):
        complete = group[list(DRIVER_COLUMNS)].dropna()
        matrix = complete.to_numpy(dtype=float)
        condition_number = math.nan
        if len(matrix) >= 3 and matrix.shape[1] >= 2:
            centered = matrix - matrix.mean(axis=0)
            scale = centered.std(axis=0)
            usable = scale > 0
            if usable.sum() >= 2:
                condition_number = float(np.linalg.cond(centered[:, usable] / scale[usable]))
        corr = complete.corr(method="spearman") if len(complete) >= 3 else pd.DataFrame()
        for left_index, left in enumerate(DRIVER_COLUMNS):
            for right in DRIVER_COLUMNS[left_index + 1 :]:
                value = math.nan
                if not corr.empty and left in corr and right in corr and pd.notna(corr.loc[left, right]):
                    value = float(corr.loc[left, right])
                rows.append(
                    {
                        "geography": geography,
                        "driver_left": left,
                        "driver_right": right,
                        "n_complete_rows": int(len(complete)),
                        "spearman_r": value,
                        "driver_matrix_condition_number": condition_number,
                        "interpretation": "Inspect correlated predictors before causal or explainability claims",
                    }
                )
    return pd.DataFrame(rows)


def main() -> None:
    args = parse_args()
    if not args.drivers.exists():
        raise FileNotFoundError(
            f"Missing driver table: {args.drivers}. Populate inputs/drivers_monthly.template.csv first."
        )
    drivers = read_drivers(args.drivers)
    suitability = regional_suitability(read_suitability(args.suitability))
    merged = suitability.merge(
        drivers,
        on=["geography", "year", "month"],
        how="inner",
        validate="many_to_one",
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    merged.to_csv(args.output_dir / "suitability_driver_monthly_join.csv", index=False, float_format="%.6f")
    correlation_rows(merged).to_csv(
        args.output_dir / "suitability_driver_correlations.csv", index=False, float_format="%.6f"
    )
    collinearity_rows(drivers).to_csv(
        args.output_dir / "driver_collinearity_diagnostics.csv", index=False, float_format="%.6f"
    )
    print({"driver_rows": len(drivers), "joined_rows": len(merged)})


if __name__ == "__main__":
    main()
