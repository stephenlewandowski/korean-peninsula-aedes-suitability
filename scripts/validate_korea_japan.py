#!/usr/bin/env python3
"""Validate a scoped seasonal suitability output contract."""

from __future__ import annotations

import json
import argparse
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_SPECIES = {"aegypti", "albopictus"}
EXPECTED_PERIODS = {"1975-1984", "1995-2004", "2015-2024"}
SCOPE_SLUGS = {"korea": "korea_focus", "japan": "japan", "korea-japan": "korea_japan"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scope",
        choices=tuple(SCOPE_SLUGS),
        default="korea-japan",
        help="Scope to validate; defaults to the historical combined archive.",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=PROJECT_ROOT,
        help="Project root containing outputs/ and metadata/.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    slug = SCOPE_SLUGS[args.scope]
    project_root = args.project_root
    table_dir = project_root / "outputs" / slug / "tables"
    map_dir = project_root / "outputs" / slug / "maps"
    metadata_path = project_root / "metadata" / f"{slug}_run_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    expected_countries = metadata["analysis_scope"]["countries"]
    expected_geographies = set(metadata["analysis_scope"]["geographies"])
    assert metadata["analysis_scope"]["species"] == ["aegypti", "albopictus"]
    assert metadata["model_and_aggregation"]["suitability_threshold"] == 0.5
    expected_cells = metadata["grid"]["all_target_cells"]
    assert set(metadata["grid"]["target_cell_counts"]) == set(expected_countries)

    monthly = pd.read_csv(table_dir / f"{slug}_monthly_suitability.csv")
    season = pd.read_csv(table_dir / f"{slug}_seasonal_summary.csv")
    change = pd.read_csv(table_dir / f"{slug}_seasonal_change_early_to_recent.csv")
    missing = pd.read_csv(table_dir / f"{slug}_missingness.csv")
    cell_year = pd.read_csv(table_dir / f"{slug}_cell_year_season.csv.gz")
    cell_decadal = pd.read_csv(table_dir / f"{slug}_cell_decadal_season.csv.gz")

    geography_count = len(expected_geographies)
    assert monthly.shape[0] == 2 * geography_count * 3 * 12
    assert season.shape[0] == 2 * geography_count * 3
    assert change.shape[0] == 2 * geography_count
    assert missing.shape[0] == 2 * geography_count * 3 * 12
    assert cell_year.shape[0] == 2 * expected_cells * 50
    assert cell_decadal.shape[0] == 2 * expected_cells * 4

    for frame in (monthly, season, missing):
        assert set(frame["geography"]) == expected_geographies
        assert set(frame["species"]) == EXPECTED_SPECIES
        assert set(frame["period"]) == EXPECTED_PERIODS
    assert monthly["month_number"].between(1, 12).all()
    assert monthly["mean_suitability"].dropna().between(0, 1).all()
    assert monthly["share_suitable_area"].dropna().between(0, 1).all()
    assert season["mean_suitable_months"].dropna().between(0, 12).all()
    assert season["mean_suitable_span_months"].dropna().between(0, 12).all()
    assert season["mean_first_suitable_month"].dropna().between(1, 12).all()
    assert season["mean_last_suitable_month"].dropna().between(1, 12).all()
    assert missing["missing_fraction"].between(0, 1).all()
    assert missing["missing_fraction"].eq(0).all()

    assert cell_year["year"].between(1975, 2024).all()
    assert cell_year["n_valid_months"].between(0, 12).all()
    assert cell_year["suitable_months_observed"].between(0, 12).all()
    assert cell_year["suitable_month_count"].dropna().between(0, 12).all()
    assert cell_year["suitable_span_months"].dropna().between(0, 12).all()
    assert cell_year[["species", "country", "cell_id", "year"]].duplicated().sum() == 0
    expected_statuses = {"modeled_regional_suitability_not_observed_presence"}
    if "North Korea" in expected_countries:
        expected_statuses.add("modeled_extrapolation_no_direct_dprk_observations")
    assert set(cell_year["observation_status"]) == expected_statuses
    assert cell_year.loc[cell_year["country"].eq("North Korea"), "dprk_extrapolation_flag"].eq(True).all()
    assert cell_year.loc[~cell_year["country"].eq("North Korea"), "dprk_extrapolation_flag"].eq(False).all()
    assert cell_year["uncertainty_status"].eq(
        "descriptive_spread_only_no_per_cell_model_uncertainty"
    ).all()
    assert set(cell_decadal["period"]) == EXPECTED_PERIODS | {"intermediate"}
    assert cell_decadal.loc[cell_decadal["period"].isin(EXPECTED_PERIODS), "n_years"].eq(10).all()
    assert cell_decadal.loc[cell_decadal["period"].eq("intermediate"), "n_years"].eq(20).all()

    expected_maps = (
        f"{slug}_suitable_months_change.png",
        f"{slug}_suitable_span_change.png",
        f"{slug}_monthly_heatmap.png",
    )
    for name in expected_maps:
        path = map_dir / name
        assert path.exists() and path.stat().st_size > 10_000, path

    print(f"{args.scope} Climademic output validation passed")


if __name__ == "__main__":
    main()
