#!/usr/bin/env python3
"""Validate the expected Korea-only Climademic output contract."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TABLE_DIR = PROJECT_ROOT / "outputs" / "tables"
MAP_DIR = PROJECT_ROOT / "outputs" / "maps"


def main() -> None:
    metadata_path = PROJECT_ROOT / "metadata" / "korea_analysis_run_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["analysis_scope"]["countries"] == ["North Korea", "South Korea"]
    assert metadata["analysis_scope"]["species"] == ["aegypti", "albopictus"]
    assert metadata["model_and_aggregation"]["suitability_threshold"] == 0.5
    assert metadata["grid"]["target_cell_counts"] == {
        "North Korea": 215,
        "South Korea": 155,
        "Korean Peninsula": 370,
    }

    monthly = pd.read_csv(TABLE_DIR / "korea_regional_monthly_suitability.csv")
    season = pd.read_csv(TABLE_DIR / "korea_regional_suitable_months.csv")
    missing = pd.read_csv(TABLE_DIR / "korea_missingness_summary.csv")

    assert monthly.shape[0] == 216
    assert season.shape[0] == 18
    assert set(monthly["geography"]) == {"North Korea", "South Korea", "Korean Peninsula"}
    assert set(monthly["species"]) == {"aegypti", "albopictus"}
    assert set(monthly["period"]) == {"1975-1984", "1995-2004", "2015-2024"}
    assert monthly["month_number"].between(1, 12).all()
    assert monthly["mean_suitability"].between(0, 1).all()
    assert season["mean_suitable_months"].between(0, 12).all()
    assert missing["missing_fraction"].eq(0).all()

    cell_year = pd.read_csv(TABLE_DIR / "korea_cell_year_monthly.csv.gz")
    cell_decadal = pd.read_csv(TABLE_DIR / "korea_cell_decadal_summary.csv.gz")
    assert cell_year.shape[0] == 37000
    assert cell_decadal.shape[0] == 2960
    assert cell_year["n_valid_months"].between(0, 12).all()
    assert cell_year["suitable_months_observed"].between(0, 12).all()
    assert cell_year["m01"].dropna().between(0, 1).all()

    expected_maps = (
        "korea_suitable_months_decades.png",
        "korea_mean_suitability_decades.png",
        "korea_suitable_months_change_early_to_recent.png",
        "korea_monthly_suitability_heatmap.png",
    )
    for name in expected_maps:
        path = MAP_DIR / name
        assert path.exists() and path.stat().st_size > 10_000, path

    print("Korea Climademic output validation passed")


if __name__ == "__main__":
    main()
