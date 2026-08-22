#!/usr/bin/env python3
"""Join LandScan ambient-population exports to a scoped suitability grid.

The script intentionally consumes a tidy, already-aggregated export rather than
silently downloading or resampling a population raster. The expected export is
one row per analysis cell and year, with the number of ambient people in that
cell. It is therefore possible to audit the LandScan-to-analysis-grid step
before any population-weighted result is reported.

The resulting quantities are population exposure indicators: for example, the
ambient population living in cells whose modeled suitable-month count
increased. They are not disease incidence, individual risk, infections, or
transmission estimates.
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PERIODS = {
    "1975-1984": range(1975, 1985),
    "1995-2004": range(1995, 2005),
    "2015-2024": range(2015, 2025),
}
PERIOD_ORDER = tuple(PERIODS)
SCOPE_CONFIG = {
    "korea": {
        "slug": "korea_focus",
        "countries": ("North Korea", "South Korea"),
        "geographies": (
            ("North Korea", ("North Korea",)),
            ("South Korea", ("South Korea",)),
            ("Korean Peninsula", ("North Korea", "South Korea")),
        ),
    },
    "japan": {
        "slug": "japan",
        "countries": ("Japan",),
        "geographies": (("Japan", ("Japan",)),),
    },
    "korea-japan": {
        "slug": "korea_japan",
        "countries": ("North Korea", "South Korea", "Japan"),
        "geographies": (
            ("North Korea", ("North Korea",)),
            ("South Korea", ("South Korea",)),
            ("Korean Peninsula", ("North Korea", "South Korea")),
            ("Japan", ("Japan",)),
            ("Korea-Japan", ("North Korea", "South Korea", "Japan")),
        ),
    },
}
TARGET_COUNTRIES: tuple[str, ...] = SCOPE_CONFIG["korea"]["countries"]
GEOGRAPHY_SPEC: tuple[tuple[str, tuple[str, ...]], ...] = SCOPE_CONFIG["korea"]["geographies"]
REQUIRED_POPULATION_COLUMNS = {"cell_id", "year", "ambient_population"}
REQUIRED_SUITABILITY_COLUMNS = {
    "species",
    "country",
    "cell_id",
    "year",
    "period",
    "suitable_month_count",
    "suitable_span_months",
    "longest_contiguous_run",
    "n_valid_months",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scope",
        choices=tuple(SCOPE_CONFIG),
        default="korea",
        help="Country scope; defaults to the Korea-first population application.",
    )
    parser.add_argument(
        "--population",
        type=Path,
        default=None,
        help="Tidy LandScan export with one row per analysis cell and year.",
    )
    parser.add_argument(
        "--suitability",
        type=Path,
        default=None,
        help="Suitability table; defaults to outputs/<scope slug>/tables/.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory; defaults to outputs/<scope slug>_population/.",
    )
    parser.add_argument(
        "--require-complete",
        action="store_true",
        help="Fail unless every target cell has a population value in every target year.",
    )
    return parser.parse_args()


def configure_scope(scope: str) -> None:
    """Set the explicit countries and aggregation geographies for a run."""
    global TARGET_COUNTRIES, GEOGRAPHY_SPEC
    if scope not in SCOPE_CONFIG:
        raise ValueError(f"Unknown population scope: {scope}")
    config = SCOPE_CONFIG[scope]
    TARGET_COUNTRIES = config["countries"]
    GEOGRAPHY_SPEC = config["geographies"]


def period_for_year(year: int) -> str | None:
    for period, years in PERIODS.items():
        if year in years:
            return period
    return None


def weighted_mean(values: Iterable[float], weights: Iterable[float]) -> float:
    value_array = np.asarray(list(values), dtype=float)
    weight_array = np.asarray(list(weights), dtype=float)
    valid = np.isfinite(value_array) & np.isfinite(weight_array) & (weight_array >= 0)
    if not valid.any() or float(weight_array[valid].sum()) <= 0:
        return math.nan
    return float(np.average(value_array[valid], weights=weight_array[valid]))


def read_population(path: Path) -> pd.DataFrame:
    population = pd.read_csv(path)
    missing = REQUIRED_POPULATION_COLUMNS - set(population.columns)
    if missing:
        raise ValueError(f"Population export is missing columns: {sorted(missing)}")
    population = population[["cell_id", "year", "ambient_population"]].copy()
    population["cell_id"] = population["cell_id"].astype(str)
    population["year"] = pd.to_numeric(population["year"], errors="coerce")
    population["ambient_population"] = pd.to_numeric(
        population["ambient_population"], errors="coerce"
    )
    if population[["year", "ambient_population"]].isna().any().any():
        raise ValueError("Population export contains non-numeric year or population values")
    population["year"] = population["year"].astype(int)
    if not population["year"].between(1975, 2024).all():
        raise ValueError("Population export contains years outside 1975–2024")
    if not np.isfinite(population["ambient_population"]).all():
        raise ValueError("Population export contains non-finite ambient population values")
    if (population["ambient_population"] < 0).any():
        raise ValueError("Ambient population must be non-negative")
    duplicates = population.duplicated(["cell_id", "year"])
    if duplicates.any():
        sample = population.loc[duplicates, ["cell_id", "year"]].head().to_dict("records")
        raise ValueError(f"Population export has duplicate cell-year rows: {sample}")
    population["period"] = population["year"].map(period_for_year)
    population = population[population["period"].notna()].copy()
    return population


def read_suitability(path: Path) -> pd.DataFrame:
    suitability = pd.read_csv(path)
    missing = REQUIRED_SUITABILITY_COLUMNS - set(suitability.columns)
    if missing:
        raise ValueError(f"Suitability table is missing columns: {sorted(missing)}")
    suitability = suitability[
        [
            "species",
            "country",
            "cell_id",
            "year",
            "period",
            "suitable_month_count",
            "suitable_span_months",
            "longest_contiguous_run",
            "n_valid_months",
        ]
    ].copy()
    suitability["cell_id"] = suitability["cell_id"].astype(str)
    suitability["year"] = pd.to_numeric(suitability["year"], errors="raise").astype(int)
    expected = {"1975-1984", "1995-2004", "2015-2024"}
    if set(suitability["period"]) != expected:
        raise ValueError("Suitability table does not contain exactly the three target periods")
    if suitability.duplicated(["species", "cell_id", "year"]).any():
        raise ValueError("Suitability table has duplicate species-cell-year rows")
    return suitability


def filter_suitability(suitability: pd.DataFrame) -> pd.DataFrame:
    """Restrict a source table to the explicitly selected country scope."""
    unexpected = sorted(set(suitability["country"]) - set(TARGET_COUNTRIES))
    if unexpected:
        raise ValueError(
            "Suitability table contains countries outside the selected population scope "
            f"{list(TARGET_COUNTRIES)}: {unexpected[:5]}"
        )
    if set(suitability["country"]) != set(TARGET_COUNTRIES):
        missing = sorted(set(TARGET_COUNTRIES) - set(suitability["country"]))
        raise ValueError(f"Suitability table is missing scoped countries: {missing}")
    return suitability.copy()


def build_cell_period_table(
    suitability: pd.DataFrame, population: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    cell_lookup = suitability[["country", "cell_id"]].drop_duplicates()
    if cell_lookup["cell_id"].duplicated().any():
        raise ValueError("A cell_id maps to more than one country in the suitability table")
    unknown_cells = sorted(set(population["cell_id"]) - set(cell_lookup["cell_id"]))
    if unknown_cells:
        raise ValueError(
            "Population export contains cells outside the public scoped analysis grid; "
            f"examples: {unknown_cells[:5]}"
        )
    if "country" in population.columns:
        population = population.drop(columns="country")
    population = population.merge(cell_lookup, on="cell_id", how="left", validate="many_to_one")
    population_period = (
        population.groupby(["country", "cell_id", "period"], as_index=False)
        .agg(
            population_mean_ambient=("ambient_population", "mean"),
            population_min_ambient=("ambient_population", "min"),
            population_max_ambient=("ambient_population", "max"),
            population_n_years=("year", "nunique"),
        )
    )
    suitability_period = (
        suitability.groupby(["species", "country", "cell_id", "period"], as_index=False)
        .agg(
            suitability_n_years=("year", "nunique"),
            suitability_n_valid_months=("n_valid_months", "mean"),
            suitable_month_count=("suitable_month_count", "mean"),
            suitable_span_months=("suitable_span_months", "mean"),
            longest_contiguous_run=("longest_contiguous_run", "mean"),
        )
    )
    joined = suitability_period.merge(
        population_period,
        on=["country", "cell_id", "period"],
        how="left",
        validate="many_to_one",
    )
    return joined, population_period


def period_summary_rows(joined: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for species in sorted(joined["species"].unique()):
        for geography, countries in GEOGRAPHY_SPEC:
            geography_data = joined[
                joined["species"].eq(species) & joined["country"].isin(countries)
            ]
            for period in PERIOD_ORDER:
                subset = geography_data[geography_data["period"].eq(period)]
                population_valid = subset["population_mean_ambient"].notna()
                suitability_valid = subset["suitable_month_count"].notna()
                joint_valid = population_valid & suitability_valid
                valid = subset.loc[joint_valid]
                weights = valid["population_mean_ambient"].to_numpy(dtype=float)
                rows.append(
                    {
                        "geography": geography,
                        "species": species,
                        "period": period,
                        "mean_annual_ambient_population_observed_cells": float(
                            subset.loc[population_valid, "population_mean_ambient"].sum()
                        ),
                        "population_weighted_mean_suitable_months": weighted_mean(
                            valid["suitable_month_count"], weights
                        ),
                        "population_weighted_mean_suitable_span_months": weighted_mean(
                            valid["suitable_span_months"], weights
                        ),
                        "population_weighted_mean_longest_contiguous_run": weighted_mean(
                            valid["longest_contiguous_run"], weights
                        ),
                        "n_cells_total": int(subset["cell_id"].nunique()),
                        "n_cells_with_population": int(subset.loc[population_valid, "cell_id"].nunique()),
                        "n_cells_with_joint_data": int(valid["cell_id"].nunique()),
                        "population_cell_coverage_fraction": (
                            float(subset.loc[population_valid, "cell_id"].nunique() / subset["cell_id"].nunique())
                            if len(subset)
                            else math.nan
                        ),
                        "joint_cell_coverage_fraction": (
                            float(valid["cell_id"].nunique() / subset["cell_id"].nunique())
                            if len(subset)
                            else math.nan
                        ),
                        "interpretation": "Population exposure indicator; not disease incidence or individual risk",
                    }
                )
    return pd.DataFrame(rows)


def change_summary_rows(joined: pd.DataFrame) -> pd.DataFrame:
    keys = ["species", "country", "cell_id"]
    periods = ["1975-1984", "2015-2024"]
    comparison = joined[joined["period"].isin(periods)].pivot_table(
        index=keys,
        columns="period",
        values=[
            "population_mean_ambient",
            "suitable_month_count",
            "suitable_span_months",
            "longest_contiguous_run",
        ],
        aggfunc="first",
    )
    comparison = comparison.dropna(
        subset=[
            ("population_mean_ambient", "2015-2024"),
            ("suitable_month_count", "1975-1984"),
            ("suitable_month_count", "2015-2024"),
            ("suitable_span_months", "1975-1984"),
            ("suitable_span_months", "2015-2024"),
        ]
    ).reset_index()
    comparison["suitable_month_count_delta_recent_minus_early"] = (
        comparison[("suitable_month_count", "2015-2024")]
        - comparison[("suitable_month_count", "1975-1984")]
    )
    comparison["suitable_span_months_delta_recent_minus_early"] = (
        comparison[("suitable_span_months", "2015-2024")]
        - comparison[("suitable_span_months", "1975-1984")]
    )
    comparison["longest_run_delta_recent_minus_early"] = (
        comparison[("longest_contiguous_run", "2015-2024")]
        - comparison[("longest_contiguous_run", "1975-1984")]
    )
    rows: list[dict[str, object]] = []
    for species in sorted(comparison["species"].unique()):
        for geography, countries in GEOGRAPHY_SPEC:
            subset = comparison[
                comparison["species"].eq(species) & comparison["country"].isin(countries)
            ].copy()
            recent_population = subset[("population_mean_ambient", "2015-2024")].to_numpy(dtype=float)
            total_population = float(recent_population.sum())
            month_delta = subset["suitable_month_count_delta_recent_minus_early"].to_numpy(dtype=float)
            span_delta = subset["suitable_span_months_delta_recent_minus_early"].to_numpy(dtype=float)
            run_delta = subset["longest_run_delta_recent_minus_early"].to_numpy(dtype=float)
            rows.append(
                {
                    "geography": geography,
                    "species": species,
                    "recent_mean_annual_ambient_population_observed_cells": total_population,
                    "population_in_cells_with_increasing_suitable_month_count": float(
                        recent_population[month_delta > 0].sum()
                    ),
                    "share_recent_population_in_cells_with_increasing_suitable_month_count": (
                        float(recent_population[month_delta > 0].sum() / total_population)
                        if total_population > 0
                        else math.nan
                    ),
                    "population_in_cells_with_longer_suitable_span": float(
                        recent_population[span_delta > 0].sum()
                    ),
                    "share_recent_population_in_cells_with_longer_suitable_span": (
                        float(recent_population[span_delta > 0].sum() / total_population)
                        if total_population > 0
                        else math.nan
                    ),
                    "population_in_cells_with_longer_contiguous_run": float(
                        recent_population[run_delta > 0].sum()
                    ),
                    "population_weighted_suitable_month_count_delta": weighted_mean(
                        month_delta, recent_population
                    ),
                    "population_weighted_suitable_span_delta": weighted_mean(
                        span_delta, recent_population
                    ),
                    "population_weighted_longest_run_delta": weighted_mean(
                        run_delta, recent_population
                    ),
                    "n_cells_paired": int(len(subset)),
                    "interpretation": "Population exposure indicator; not disease incidence or individual risk",
                }
            )
    return pd.DataFrame(rows)


def missingness_rows(population_period: pd.DataFrame, suitability: pd.DataFrame) -> pd.DataFrame:
    cell_counts = suitability[["country", "cell_id"]].drop_duplicates().groupby("country").size()
    rows: list[dict[str, object]] = []
    for country, expected_cells in cell_counts.items():
        country_data = population_period[population_period["country"].eq(country)]
        for period in PERIOD_ORDER:
            observed = country_data[country_data["period"].eq(period)]
            expected_rows = int(expected_cells) * 10
            observed_rows = int(observed["population_n_years"].sum())
            rows.append(
                {
                    "country": country,
                    "period": period,
                    "expected_cells": int(expected_cells),
                    "expected_cell_year_rows": expected_rows,
                    "observed_cell_year_rows": observed_rows,
                    "missing_cell_year_rows": expected_rows - observed_rows,
                    "missing_fraction": (
                        float((expected_rows - observed_rows) / expected_rows)
                        if expected_rows
                        else math.nan
                    ),
                }
            )
    return pd.DataFrame(rows)


def write_csv(frame: pd.DataFrame, path: Path, gzip: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, compression="gzip" if gzip else None, float_format="%.6f")


def main() -> None:
    args = parse_args()
    configure_scope(args.scope)
    slug = SCOPE_CONFIG[args.scope]["slug"]
    population_path = args.population or PROJECT_ROOT / "inputs" / "landscan_population_by_cell_year.csv"
    suitability_path = args.suitability or (
        PROJECT_ROOT / "outputs" / slug / "tables" / f"{slug}_cell_year_season.csv.gz"
    )
    output_dir = args.output_dir or PROJECT_ROOT / "outputs" / f"{slug}_population"
    if not population_path.exists():
        raise FileNotFoundError(
            f"Missing LandScan export: {population_path}. "
            "Create it from scripts/landscan_gee_export.js before running this analysis."
        )
    population = read_population(population_path)
    suitability = filter_suitability(read_suitability(suitability_path))
    joined, population_period = build_cell_period_table(suitability, population)
    if args.require_complete:
        expected = suitability[["country", "cell_id", "period"]].drop_duplicates().shape[0]
        complete = int(joined["population_mean_ambient"].notna().sum())
        if complete != expected:
            raise ValueError(f"Population coverage is incomplete: {complete}/{expected} cell-period rows")

    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(joined, output_dir / "population_cell_period.csv.gz", gzip=True)
    write_csv(period_summary_rows(joined), output_dir / "population_exposure_by_period.csv")
    write_csv(change_summary_rows(joined), output_dir / "population_exposure_change_early_to_recent.csv")
    write_csv(
        missingness_rows(population_period, suitability),
        output_dir / "population_missingness.csv",
    )
    metadata = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "input_population": str(population_path),
        "population_source": {
            "dataset": "LandScan Mosaic Annual Global Ambient Population Time Series, Version 1.0",
            "official_dataset_page": "https://impact.ornl.gov/en/datasets/landscan-mosaic-annual-global-ambient-population-time-series-vers/",
            "collection": "projects/sat-io/open-datasets/ORNL/LANDSCAN_MOSAIC_TIMESERIES",
            "years": [1975, 2024],
            "expected_measure": "ambient population, number of people per analysis cell",
        },
        "analysis_scope": {
            "scope": args.scope,
            "countries": list(TARGET_COUNTRIES),
            "geographies": [name for name, _ in GEOGRAPHY_SPEC],
            "periods": list(PERIOD_ORDER),
            "interpretation": "Population exposure indicators are distinct from disease incidence, infection, individual risk, and transmission.",
        },
        "input_rows": int(len(population)),
        "suitability_input": str(suitability_path),
        "suitability_rows": int(len(suitability)),
        "joined_rows": int(len(joined)),
        "require_complete": bool(args.require_complete),
    }
    (output_dir / "population_exposure_run_metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"population_rows": len(population), "joined_rows": len(joined)}))


if __name__ == "__main__":
    main()
