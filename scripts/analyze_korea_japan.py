#!/usr/bin/env python3
"""Build a scoped regional seasonal suitability comparison.

This follow-on application uses the same v2.0 Climademic Aedes archives,
threshold, cell-center mask, missingness rule, and cosine-latitude weights as
``analyze_korea.py``. It adds Japan as a country-level regional comparison and
reports monthly suitability, suitable-month count, first and last suitable
month, the first-to-last span, and the longest contiguous suitable run.

The output remains a regional/grid product. First and last suitable month are
calendar-month summaries, not exact biological onset or end dates, and a
non-contiguous set of suitable months can have a span longer than its count.
The script does not estimate vector presence, abundance, infection, or disease
transmission risk.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Reuse the validated reader, geometry, cleaning, and summary primitives from
# the initial Korea-only application.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if (PROJECT_ROOT / "vendor").exists():
    sys.path.insert(0, str(PROJECT_ROOT / "vendor"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_korea as core  # noqa: E402


MONTHS = core.MONTHS
MONTH_CODES = core.MONTH_CODES
SPECIES = core.SPECIES
PERIODS = core.PERIODS
PERIOD_ORDER = core.PERIOD_ORDER

# The combined Korea–Japan run is retained for reproducibility, but new work
# can be run as a Korea-only or Japan-only product. The scope is deliberately
# explicit so a comparison geography is never inferred from a map title.
SCOPE_CONFIG = {
    "korea": {
        "label": "Korean Peninsula",
        "slug": "korea_focus",
        "countries": ("North Korea", "South Korea"),
        "geographies": (
            ("North Korea", ("North Korea",)),
            ("South Korea", ("South Korea",)),
            ("Korean Peninsula", ("North Korea", "South Korea")),
        ),
        "longitude": (123.0, 132.5),
        "latitude": (32.5, 43.5),
    },
    "japan": {
        "label": "Japan",
        "slug": "japan",
        "countries": ("Japan",),
        "geographies": (("Japan", ("Japan",)),),
        "longitude": (122.0, 154.5),
        "latitude": (23.5, 46.0),
    },
    "korea-japan": {
        "label": "Korea–Japan comparison archive",
        "slug": "korea_japan",
        "countries": ("North Korea", "South Korea", "Japan"),
        "geographies": (
            ("North Korea", ("North Korea",)),
            ("South Korea", ("South Korea",)),
            ("Korean Peninsula", ("North Korea", "South Korea")),
            ("Japan", ("Japan",)),
            ("Korea-Japan", ("North Korea", "South Korea", "Japan")),
        ),
        "longitude": (122.0, 154.5),
        "latitude": (23.5, 46.0),
    },
}

TARGET_COUNTRIES: tuple[str, ...] = SCOPE_CONFIG["korea-japan"]["countries"]
GEOGRAPHY_SPEC: tuple[tuple[str, tuple[str, ...]], ...] = SCOPE_CONFIG["korea-japan"]["geographies"]
GEOGRAPHY_ORDER = tuple(name for name, _ in GEOGRAPHY_SPEC)
REGION_LONGITUDE: tuple[float, float] = SCOPE_CONFIG["korea-japan"]["longitude"]
REGION_LATITUDE: tuple[float, float] = SCOPE_CONFIG["korea-japan"]["latitude"]
SCOPE_LABEL = SCOPE_CONFIG["korea-japan"]["label"]


def configure_scope(scope: str) -> None:
    """Set the explicit country/geography mask used by all downstream steps."""
    global TARGET_COUNTRIES, GEOGRAPHY_SPEC, GEOGRAPHY_ORDER
    global REGION_LONGITUDE, REGION_LATITUDE, SCOPE_LABEL
    if scope not in SCOPE_CONFIG:
        raise ValueError(f"Unknown analysis scope: {scope}")
    config = SCOPE_CONFIG[scope]
    TARGET_COUNTRIES = config["countries"]
    GEOGRAPHY_SPEC = config["geographies"]
    GEOGRAPHY_ORDER = tuple(name for name, _ in GEOGRAPHY_SPEC)
    REGION_LONGITUDE = config["longitude"]
    REGION_LATITUDE = config["latitude"]
    SCOPE_LABEL = config["label"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scope",
        choices=tuple(SCOPE_CONFIG),
        default="korea-japan",
        help="Explicit country scope; the combined archive remains the default for compatibility.",
    )
    parser.add_argument(
        "--aegypti-zip",
        type=Path,
        default=PROJECT_ROOT / "source" / "aegypti.zip",
    )
    parser.add_argument(
        "--albopictus-zip",
        type=Path,
        default=PROJECT_ROOT / "source" / "albopictus.zip",
    )
    parser.add_argument(
        "--boundary",
        type=Path,
        default=PROJECT_ROOT / "source" / "ne_10m_admin_0_countries.geojson",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory; defaults to outputs/<scope slug>.",
    )
    parser.add_argument(
        "--metadata-dir",
        type=Path,
        default=None,
        help="Metadata directory; defaults to this project's metadata directory.",
    )
    parser.add_argument("--threshold", type=float, default=0.5)
    return parser.parse_args()


def load_features(path: Path) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    with path.open(encoding="utf-8") as handle:
        document = json.load(handle)
    target: dict[str, dict[str, Any]] = {}
    context: dict[str, dict[str, Any]] = {}
    context_names = set(TARGET_COUNTRIES) | {"China", "Russia"}
    for feature in document["features"]:
        name = feature["properties"].get("ADMIN")
        if name in context_names:
            context[name] = feature
        if name in TARGET_COUNTRIES:
            target[name] = feature
    missing = set(TARGET_COUNTRIES) - set(target)
    if missing:
        raise ValueError(f"Boundary source is missing target countries: {sorted(missing)}")
    return target, context


def build_grid(sample_raster: np.ndarray, features: dict[str, dict[str, Any]]) -> dict[str, Any]:
    height, width = sample_raster.shape[:2]
    longitudes = -180.0 + 0.125 + 0.25 * np.arange(width)
    latitudes = 83.75 - 0.125 - 0.25 * np.arange(height)
    row_indices = np.where(
        (latitudes >= REGION_LATITUDE[0]) & (latitudes <= REGION_LATITUDE[1])
    )[0]
    col_indices = np.where(
        (longitudes >= REGION_LONGITUDE[0]) & (longitudes <= REGION_LONGITUDE[1])
    )[0]
    grid_lon, grid_lat = np.meshgrid(longitudes[col_indices], latitudes[row_indices])
    points = np.column_stack((grid_lon.ravel(), grid_lat.ravel()))

    masks: dict[str, np.ndarray] = {}
    for name, feature in features.items():
        masks[name] = core.geometry_mask(feature["geometry"], points).reshape(grid_lon.shape)
    target_mask = np.zeros(grid_lon.shape, dtype=bool)
    country_grid = np.full(grid_lon.shape, "", dtype=object)
    for country in TARGET_COUNTRIES:
        target_mask |= masks[country]
        country_grid[masks[country]] = country
    if np.any(country_grid[target_mask] == ""):
        raise ValueError("Target mask contains cells without a country assignment")

    return {
        "height": height,
        "width": width,
        "row_indices": row_indices,
        "col_indices": col_indices,
        "longitudes": longitudes,
        "latitudes": latitudes,
        "grid_lon": grid_lon,
        "grid_lat": grid_lat,
        "masks": masks,
        "country_grid": country_grid,
        "target_mask": target_mask,
        "area_weight": np.cos(np.deg2rad(grid_lat)),
    }


def longest_run(row: np.ndarray) -> int:
    best = 0
    current = 0
    for value in row:
        if bool(value):
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best


def season_metrics(clean: np.ndarray, threshold: float) -> dict[str, np.ndarray]:
    valid = np.isfinite(clean)
    suitable = valid & (clean >= threshold)
    n_valid = valid.sum(axis=1).astype(int)
    count = suitable.sum(axis=1).astype(int)
    has_suitable = count > 0
    first = np.full(clean.shape[0], np.nan, dtype=float)
    last = np.full(clean.shape[0], np.nan, dtype=float)
    first[has_suitable] = np.argmax(suitable[has_suitable], axis=1) + 1
    last[has_suitable] = 12 - np.argmax(suitable[has_suitable, ::-1], axis=1)
    span = np.where(has_suitable, last - first + 1, 0.0)
    longest = np.asarray([longest_run(row) for row in suitable], dtype=float)
    suitable_complete = np.where(n_valid == 12, count.astype(float), np.nan)
    return {
        "n_valid_months": n_valid,
        "coverage_fraction": n_valid / 12.0,
        "suitable_months_observed": count,
        "suitable_month_count": suitable_complete,
        "first_suitable_month": first,
        "last_suitable_month": last,
        "suitable_span_months": span,
        "longest_contiguous_run": longest,
    }


def select_geography(cell_df: pd.DataFrame, countries: tuple[str, ...]) -> pd.DataFrame:
    return cell_df[cell_df["country"].isin(countries)]


def monthly_summary_rows(cell_df: pd.DataFrame, threshold: float) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for species in SPECIES:
        species_data = cell_df[cell_df["species"].eq(species)]
        for geography, countries in GEOGRAPHY_SPEC:
            geography_data = select_geography(species_data, countries)
            for period in PERIOD_ORDER:
                subset = geography_data[geography_data["period"].eq(period)]
                total_cell_years = len(subset)
                total_cells = subset["cell_id"].nunique()
                for month_index, month in enumerate(MONTHS):
                    column = MONTH_CODES[month_index]
                    raw = subset[column].to_numpy(dtype=float)
                    valid = np.isfinite(raw)
                    values = raw[valid]
                    weights = subset.loc[valid, "area_weight"].to_numpy(dtype=float)
                    n_valid = int(valid.sum())
                    rows.append(
                        {
                            "geography": geography,
                            "species": species,
                            "period": period,
                            "includes_dprk_extrapolation": "North Korea" in countries,
                            "uncertainty_status": "descriptive_spread_only_no_per_cell_model_uncertainty",
                            "month_number": month_index + 1,
                            "month": month,
                            "mean_suitability": core.weighted_mean(values, weights),
                            "mean_suitability_unweighted": core.safe_mean(values),
                            "median_suitability": core.safe_quantile(values, 0.50),
                            "p25_suitability": core.safe_quantile(values, 0.25),
                            "p75_suitability": core.safe_quantile(values, 0.75),
                            "spatial_temporal_sd": core.safe_sd(values),
                            "share_suitable_area": core.weighted_share(values, weights, threshold),
                            "share_suitable_cells": core.safe_mean(values >= threshold),
                            "n_total_cells": total_cells,
                            "n_total_cell_years": total_cell_years,
                            "n_valid_cell_years": n_valid,
                            "n_missing_cell_years": total_cell_years - n_valid,
                            "missing_fraction": (
                                (total_cell_years - n_valid) / total_cell_years
                                if total_cell_years
                                else math.nan
                            ),
                        }
                    )
    return rows


def season_summary_rows(cell_df: pd.DataFrame, threshold: float) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    metrics = (
        "suitable_month_count",
        "suitable_span_months",
        "longest_contiguous_run",
    )
    for species in SPECIES:
        species_data = cell_df[cell_df["species"].eq(species)]
        for geography, countries in GEOGRAPHY_SPEC:
            geography_data = select_geography(species_data, countries)
            for period in PERIOD_ORDER:
                subset = geography_data[geography_data["period"].eq(period)]
                complete = subset["suitable_month_count"].notna()
                complete_data = subset.loc[complete]
                weights = complete_data["area_weight"].to_numpy(dtype=float)
                any_suitable = complete_data["suitable_month_count"].gt(0)
                any_data = complete_data.loc[any_suitable]
                any_weights = any_data["area_weight"].to_numpy(dtype=float)
                row: dict[str, Any] = {
                    "geography": geography,
                    "species": species,
                    "period": period,
                    "threshold": threshold,
                    "includes_dprk_extrapolation": "North Korea" in countries,
                    "uncertainty_status": "descriptive_spread_only_no_per_cell_model_uncertainty",
                    "mean_suitable_months": core.weighted_mean(
                        complete_data["suitable_month_count"].to_numpy(dtype=float), weights
                    ),
                    "mean_suitable_months_unweighted": core.safe_mean(
                        complete_data["suitable_month_count"].to_numpy(dtype=float)
                    ),
                    "median_suitable_months": core.safe_quantile(
                        complete_data["suitable_month_count"].to_numpy(dtype=float), 0.50
                    ),
                    "p25_suitable_months": core.safe_quantile(
                        complete_data["suitable_month_count"].to_numpy(dtype=float), 0.25
                    ),
                    "p75_suitable_months": core.safe_quantile(
                        complete_data["suitable_month_count"].to_numpy(dtype=float), 0.75
                    ),
                    "suitable_months_sd": core.safe_sd(
                        complete_data["suitable_month_count"].to_numpy(dtype=float)
                    ),
                    "mean_suitable_months_observed": core.safe_mean(
                        subset["suitable_months_observed"].to_numpy(dtype=float)
                    ),
                    "mean_valid_months": core.safe_mean(
                        subset["n_valid_months"].to_numpy(dtype=float)
                    ),
                    "mean_first_suitable_month": core.weighted_mean(
                        any_data["first_suitable_month"].to_numpy(dtype=float), any_weights
                    ),
                    "mean_last_suitable_month": core.weighted_mean(
                        any_data["last_suitable_month"].to_numpy(dtype=float), any_weights
                    ),
                    "mean_suitable_span_months": core.weighted_mean(
                        complete_data["suitable_span_months"].to_numpy(dtype=float), weights
                    ),
                    "mean_longest_contiguous_run": core.weighted_mean(
                        complete_data["longest_contiguous_run"].to_numpy(dtype=float), weights
                    ),
                    "share_complete_cell_years_with_any_suitable": (
                        float(any_suitable.mean()) if len(complete_data) else math.nan
                    ),
                    "share_suitable_area_with_any_suitable": core.weighted_mean(
                        any_data["suitable_month_count"].gt(0).to_numpy(dtype=float), any_weights
                    ),
                    "n_total_cells": subset["cell_id"].nunique(),
                    "n_total_cell_years": len(subset),
                    "n_complete_cell_years": int(complete.sum()),
                    "n_any_suitable_cell_years": int(any_suitable.sum()),
                    "n_no_suitable_cell_years": int((complete_data["suitable_month_count"] == 0).sum()),
                    "complete_cell_year_fraction": (
                        float(complete.mean()) if len(subset) else math.nan
                    ),
                }
                for metric in metrics:
                    row[f"unweighted_{metric}"] = core.safe_mean(
                        complete_data[metric].to_numpy(dtype=float)
                    )
                rows.append(row)
    return rows


def change_table(df: pd.DataFrame, index: list[str], metrics: list[str]) -> pd.DataFrame:
    subset = df[df["period"].isin(("1975-1984", "2015-2024"))]
    pivot = subset.pivot_table(index=index, columns="period", values=metrics, aggfunc="first")
    pivot = pivot.reset_index()
    pivot.columns = [
        "_".join(str(part) for part in column if str(part) != "").strip("_")
        if isinstance(column, tuple)
        else str(column)
        for column in pivot.columns
    ]
    for metric in metrics:
        pivot[f"{metric}_delta_recent_minus_early"] = (
            pivot[f"{metric}_2015-2024"] - pivot[f"{metric}_1975-1984"]
        )
    return pivot


def build_cell_decadal_summary(cell_df: pd.DataFrame) -> pd.DataFrame:
    group_columns = [
        "species",
        "country",
        "cell_id",
        "row_global",
        "col_global",
        "longitude",
        "latitude",
        "area_weight",
        "period",
    ]
    records: list[dict[str, Any]] = []
    for keys, subset in cell_df.groupby(group_columns, sort=False, dropna=False):
        species, country, cell_id, row, col, lon, lat, weight, period = keys
        records.append(
            {
                "species": species,
                "country": country,
                "cell_id": cell_id,
                "dprk_extrapolation_flag": country == "North Korea",
                "observation_status": (
                    "modeled_extrapolation_no_direct_dprk_observations"
                    if country == "North Korea"
                    else "modeled_regional_suitability_not_observed_presence"
                ),
                "uncertainty_status": "descriptive_spread_only_no_per_cell_model_uncertainty",
                "row_global": int(row),
                "col_global": int(col),
                "longitude": float(lon),
                "latitude": float(lat),
                "area_weight": float(weight),
                "period": period,
                "n_years": int(subset["year"].nunique()),
                "complete_year_fraction": float(subset["suitable_month_count"].notna().mean()),
                "valid_month_fraction": float(subset["n_valid_months"].sum() / (len(subset) * 12)),
                "mean_suitable_months": float(subset["suitable_month_count"].mean()),
                "mean_first_suitable_month": float(subset["first_suitable_month"].mean()),
                "mean_last_suitable_month": float(subset["last_suitable_month"].mean()),
                "mean_suitable_span_months": float(subset["suitable_span_months"].mean()),
                "mean_longest_contiguous_run": float(subset["longest_contiguous_run"].mean()),
                "mean_annual_suitability": float(subset["annual_mean_suitability"].mean()),
            }
        )
    return pd.DataFrame(records)


def draw_context_boundaries(ax: Any, context: dict[str, dict[str, Any]]) -> None:
    for name, feature in context.items():
        color = "#2b6f9e" if name in TARGET_COUNTRIES else "#777777"
        width = 0.85 if name in TARGET_COUNTRIES else 0.45
        for ring in core.geometry_rings(feature):
            ax.plot(ring[:, 0], ring[:, 1], color=color, linewidth=width, zorder=4)


def render_change_map(
    cell_summary: pd.DataFrame,
    grid: dict[str, Any],
    context: dict[str, dict[str, Any]],
    output_path: Path,
    value_column: str,
    cmap: str,
    vmin: float,
    vmax: float,
    label: str,
    title: str,
) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(13.2, 5.4), constrained_layout=True)
    row0 = int(grid["row_indices"][0])
    col0 = int(grid["col_indices"][0])
    shape = grid["grid_lon"].shape
    extent = (
        float(grid["grid_lon"][grid["target_mask"]].min() - 0.5),
        float(grid["grid_lon"][grid["target_mask"]].max() + 0.5),
        float(grid["grid_lat"][grid["target_mask"]].min() - 0.5),
        float(grid["grid_lat"][grid["target_mask"]].max() + 0.5),
    )
    image_extent = (
        grid["longitudes"][grid["col_indices"][0]] - 0.125,
        grid["longitudes"][grid["col_indices"][-1]] + 0.125,
        grid["latitudes"][grid["row_indices"][-1]] - 0.125,
        grid["latitudes"][grid["row_indices"][0]] + 0.125,
    )
    for index, species in enumerate(SPECIES):
        species_data = cell_summary[cell_summary["species"].eq(species)]
        early = species_data[species_data["period"].eq("1975-1984")].set_index("cell_id")
        recent = species_data[species_data["period"].eq("2015-2024")].set_index("cell_id")
        subset = recent.join(early[[value_column]], lsuffix="_recent", rsuffix="_early").reset_index()
        subset["map_value"] = subset[f"{value_column}_recent"] - subset[f"{value_column}_early"]
        image = np.full(shape, np.nan, dtype=float)
        rr = subset["row_global"].to_numpy(dtype=int) - row0
        cc = subset["col_global"].to_numpy(dtype=int) - col0
        image[rr, cc] = subset["map_value"].to_numpy(dtype=float)
        ax = axes[index]
        im = ax.imshow(
            image,
            origin="upper",
            extent=image_extent,
            cmap=cmap,
            vmin=vmin,
            vmax=vmax,
            interpolation="nearest",
            zorder=1,
        )
        draw_context_boundaries(ax, context)
        ax.set_xlim(extent[0], extent[1])
        ax.set_ylim(extent[2], extent[3])
        ax.set_aspect("equal", adjustable="box")
        ax.set_title(f"Aedes {species}\n2015–2024 minus 1975–1984", fontsize=10)
        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")
        ax.tick_params(labelsize=8)
        for country in TARGET_COUNTRIES:
            mask = grid["masks"][country]
            ax.text(
                float(grid["grid_lon"][mask].mean()),
                float(grid["grid_lat"][mask].mean()),
                country.replace("South ", "S. ").replace("North ", "N. "),
                fontsize=7,
                color="#2b6f9e",
                ha="center",
                zorder=5,
            )
        fig.colorbar(im, ax=ax, shrink=0.82, pad=0.02, label=label)
    fig.suptitle(title, fontsize=13)
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def render_monthly_heatmap(monthly_df: pd.DataFrame, output_path: Path) -> None:
    geographies = GEOGRAPHY_ORDER
    row_count = len(geographies) * 2
    fig, axes = plt.subplots(
        1,
        2,
        figsize=(13.5, max(7.0, 0.85 * row_count + 4.0)),
        constrained_layout=True,
    )
    month_labels = [month[:3] for month in MONTHS]
    row_labels = [f"{geography}\n{period}" for geography in geographies for period in ("1975–84", "2015–24")]
    for ax, species in zip(axes, SPECIES):
        matrices = []
        for geography in geographies:
            for period in ("1975-1984", "2015-2024"):
                subset = monthly_df[
                    monthly_df["geography"].eq(geography)
                    & monthly_df["species"].eq(species)
                    & monthly_df["period"].eq(period)
                ]
                matrices.append(
                    subset.set_index("month_number")["mean_suitability"].reindex(range(1, 13)).to_numpy()
                )
        matrix = np.vstack(matrices)
        image = ax.imshow(matrix, vmin=0, vmax=1, cmap="viridis", aspect="auto")
        ax.set_xticks(range(12), month_labels)
        ax.set_yticks(range(len(row_labels)), row_labels)
        ax.set_title(f"Aedes {species}")
        ax.set_xlabel("Month")
        for row in range(matrix.shape[0]):
            for column in range(matrix.shape[1]):
                value = matrix[row, column]
                if np.isfinite(value):
                    ax.text(column, row, f"{value:.2f}", ha="center", va="center", fontsize=6, color="white")
        fig.colorbar(image, ax=ax, shrink=0.72, label="Area-weighted mean suitability")
    fig.suptitle(
        f"{SCOPE_LABEL} monthly suitability: early and recent comparison periods",
        fontsize=13,
    )
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def create_metadata(
    args: argparse.Namespace,
    grid: dict[str, Any],
    cell_df: pd.DataFrame,
    source_paths: dict[str, Path],
) -> dict[str, Any]:
    return {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "analysis_scope": {
            "scope": args.scope,
            "label": SCOPE_LABEL,
            "countries": list(TARGET_COUNTRIES),
            "geographies": list(GEOGRAPHY_ORDER),
            "species": list(SPECIES),
            "years": [1975, 2024],
            "periods": {key: list(value) for key, value in PERIODS.items()},
            "region_window": {
                "longitude": list(REGION_LONGITUDE),
                "latitude": list(REGION_LATITUDE),
            },
        },
        "source": {
            "zenodo_record": "https://zenodo.org/records/21924442",
            "zenodo_version": "2.0",
            "aegypti_zip_sha256": core.sha256_file(source_paths["aegypti"]),
            "albopictus_zip_sha256": core.sha256_file(source_paths["albopictus"]),
            "data_specification_sha256": core.sha256_file(source_paths["specification"]),
            "boundary_source": "https://github.com/nvkelso/natural-earth-vector/blob/master/geojson/ne_10m_admin_0_countries.geojson",
            "boundary_sha256": core.sha256_file(source_paths["boundary"]),
            "retrieval_date": "2026-08-19",
            "analysis_reference_file": "Climademic-Suitability-Model-Aedes-Reference-2026-08-16.md",
        },
        "model_and_aggregation": {
            "input_crs": "EPSG:4326",
            "input_resolution_degrees": 0.25,
            "probability_range": [0.0, 1.0],
            "nodata_value": -1.0,
            "suitability_threshold": args.threshold,
            "cell_inclusion": "A grid cell is included when its center falls inside the Natural Earth 10m country polygon; boundary-edge partial-cell area is not clipped.",
            "regional_mean": "Monthly suitability and season metrics use cosine(latitude)-weighted valid grid-cell observations; unweighted summaries are retained.",
            "suitable_month_count": "Number of calendar months with suitability >= threshold.",
            "season_onset": "First calendar month with suitability >= threshold among complete cell-years with at least one suitable month.",
            "season_end": "Last calendar month with suitability >= threshold among complete cell-years with at least one suitable month.",
            "season_span": "Last suitable month minus first suitable month plus one; it can exceed suitable-month count when suitable months are non-contiguous.",
            "longest_contiguous_run": "Longest uninterrupted January–December run of suitable months; December-to-January wrap is not joined.",
            "missingness": "No imputation. Values outside [0, 1], NaN, and -1 are treated as missing.",
            "uncertainty": "No per-cell model uncertainty layer is supplied; quantiles, spread, valid counts, and missingness are descriptive variability indicators rather than confidence intervals.",
        },
        "interpretation_boundary": {
            "north_korea": "Modeled extrapolation flag; no direct DPRK occurrence or surveillance records are included.",
            "south_korea_and_japan": "Modeled regional suitability, not observed vector presence or abundance.",
            "all_geographies": "Do not interpret as infection, disease incidence, human exposure, transmission risk, installation risk, or operational early warning.",
        },
        "grid": {
            "source_raster_shape": [grid["height"], grid["width"], 12],
            "target_cell_counts": {
                country: int(grid["masks"][country].sum()) for country in TARGET_COUNTRIES
            },
            "all_target_cells": int(grid["target_mask"].sum()),
        },
        "output_row_counts": {"cell_year_season": int(len(cell_df))},
    }


def write_csv(df: pd.DataFrame, path: Path, gzip: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, compression="gzip" if gzip else None, float_format="%.6f")


def main() -> None:
    args = parse_args()
    configure_scope(args.scope)
    scope_slug = SCOPE_CONFIG[args.scope]["slug"]
    output_dir = args.output_dir or PROJECT_ROOT / "outputs" / scope_slug
    table_dir = output_dir / "tables"
    map_dir = output_dir / "maps"
    metadata_dir = args.metadata_dir or PROJECT_ROOT / "metadata"
    table_dir.mkdir(parents=True, exist_ok=True)
    map_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)

    source_paths = {
        "aegypti": args.aegypti_zip,
        "albopictus": args.albopictus_zip,
        "specification": PROJECT_ROOT / "source" / "Data_Specification.pdf",
        "boundary": args.boundary,
    }
    for label, path in source_paths.items():
        if not path.exists():
            raise FileNotFoundError(f"Missing {label} source: {path}")

    target_features, context_features = load_features(args.boundary)
    with zipfile.ZipFile(args.aegypti_zip) as archive:
        first_member = sorted(name for name in archive.namelist() if name.endswith(".tif"))[0]
        sample = core.read_raster_from_zip(archive, first_member)
    grid = build_grid(sample, target_features)
    row_grid, col_grid = np.indices(grid["grid_lon"].shape)
    target_indices = np.flatnonzero(grid["target_mask"].ravel())
    flat_row_global = (row_grid.ravel() + int(grid["row_indices"][0]))[target_indices]
    flat_col_global = (col_grid.ravel() + int(grid["col_indices"][0]))[target_indices]
    flat_lon = grid["grid_lon"].ravel()[target_indices]
    flat_lat = grid["grid_lat"].ravel()[target_indices]
    flat_weight = grid["area_weight"].ravel()[target_indices]
    flat_country = grid["country_grid"].ravel()[target_indices]

    cell_rows: list[dict[str, Any]] = []
    for species, archive_path in (("aegypti", args.aegypti_zip), ("albopictus", args.albopictus_zip)):
        with zipfile.ZipFile(archive_path) as archive:
            members = sorted(
                (name for name in archive.namelist() if name.endswith(".tif")),
                key=core.parse_year,
            )
            years = [core.parse_year(name) for name in members]
            expected_years = list(range(1975, 2025))
            if years != expected_years:
                raise ValueError(f"Unexpected year inventory for {species}: {years}")
            for member in members:
                year = core.parse_year(member)
                raster = core.read_raster_from_zip(archive, member)
                if raster.shape[:2] != (grid["height"], grid["width"]):
                    raise ValueError(f"Grid shape changed in {member}: {raster.shape}")
                regional = raster[
                    grid["row_indices"][:, None],
                    grid["col_indices"][None, :],
                    :,
                ]
                flat = regional.reshape(-1, 12)[target_indices].astype(float)
                valid = core.valid_values(flat)
                clean = flat.copy()
                clean[~valid] = np.nan
                metrics = season_metrics(clean, args.threshold)
                with np.errstate(all="ignore"):
                    annual_mean = np.nanmean(clean, axis=1)
                period = core.period_for_year(year)
                for index in range(flat.shape[0]):
                    record: dict[str, Any] = {
                        "species": species,
                        "country": str(flat_country[index]),
                        "dprk_extrapolation_flag": str(flat_country[index]) == "North Korea",
                        "observation_status": (
                            "modeled_extrapolation_no_direct_dprk_observations"
                            if str(flat_country[index]) == "North Korea"
                            else "modeled_regional_suitability_not_observed_presence"
                        ),
                        "uncertainty_status": "descriptive_spread_only_no_per_cell_model_uncertainty",
                        "cell_id": f"r{flat_row_global[index]:03d}c{flat_col_global[index]:04d}",
                        "row_global": int(flat_row_global[index]),
                        "col_global": int(flat_col_global[index]),
                        "longitude": float(flat_lon[index]),
                        "latitude": float(flat_lat[index]),
                        "area_weight": float(flat_weight[index]),
                        "year": year,
                        "period": period,
                        "annual_mean_suitability": float(annual_mean[index]),
                    }
                    for key, values in metrics.items():
                        value = values[index]
                        record[key] = float(value) if np.isfinite(value) else math.nan
                    for month_index, code in enumerate(MONTH_CODES):
                        value = clean[index, month_index]
                        record[code] = float(value) if np.isfinite(value) else math.nan
                    cell_rows.append(record)

    cell_df = pd.DataFrame(cell_rows).sort_values(
        ["species", "country", "cell_id", "year"]
    ).reset_index(drop=True)
    monthly_df = pd.DataFrame(monthly_summary_rows(cell_df, args.threshold))
    season_df = pd.DataFrame(season_summary_rows(cell_df, args.threshold))
    monthly_change_df = change_table(
        monthly_df,
        ["geography", "species", "month_number", "month"],
        ["mean_suitability", "mean_suitability_unweighted", "share_suitable_area"],
    )
    season_change_df = change_table(
        season_df,
        ["geography", "species"],
        [
            "mean_suitable_months",
            "mean_first_suitable_month",
            "mean_last_suitable_month",
            "mean_suitable_span_months",
            "mean_longest_contiguous_run",
        ],
    )
    cell_decadal_df = build_cell_decadal_summary(cell_df)

    write_csv(cell_df, table_dir / f"{scope_slug}_cell_year_season.csv.gz", gzip=True)
    write_csv(cell_decadal_df, table_dir / f"{scope_slug}_cell_decadal_season.csv.gz", gzip=True)
    write_csv(monthly_df, table_dir / f"{scope_slug}_monthly_suitability.csv")
    write_csv(season_df, table_dir / f"{scope_slug}_seasonal_summary.csv")
    write_csv(monthly_change_df, table_dir / f"{scope_slug}_monthly_change_early_to_recent.csv")
    write_csv(season_change_df, table_dir / f"{scope_slug}_seasonal_change_early_to_recent.csv")
    write_csv(
        monthly_df[
            [
                "geography",
                "species",
                "period",
                "month_number",
                "month",
                "n_total_cells",
                "n_total_cell_years",
                "n_valid_cell_years",
                "n_missing_cell_years",
                "missing_fraction",
            ]
        ],
        table_dir / f"{scope_slug}_missingness.csv",
    )

    render_change_map(
        cell_decadal_df,
        grid,
        context_features,
        map_dir / f"{scope_slug}_suitable_months_change.png",
        value_column="mean_suitable_months",
        cmap="RdBu_r",
        vmin=-6,
        vmax=6,
        label="Change in suitable months",
        title=f"{SCOPE_LABEL} change in suitable-month count: recent minus early decade",
    )
    render_change_map(
        cell_decadal_df,
        grid,
        context_features,
        map_dir / f"{scope_slug}_suitable_span_change.png",
        value_column="mean_suitable_span_months",
        cmap="PuOr",
        vmin=-6,
        vmax=6,
        label="Change in first-to-last span (months)",
        title=f"{SCOPE_LABEL} change in suitable-season span: recent minus early decade",
    )
    render_monthly_heatmap(monthly_df, map_dir / f"{scope_slug}_monthly_heatmap.png")

    metadata = create_metadata(args, grid, cell_df, source_paths)
    with (metadata_dir / f"{scope_slug}_run_metadata.json").open("w", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2)

    print(
        json.dumps(
            {
                "cell_year_rows": len(cell_df),
                "cell_decadal_rows": len(cell_decadal_df),
                "monthly_rows": len(monthly_df),
                "season_rows": len(season_df),
                "target_cell_counts": metadata["grid"]["target_cell_counts"],
                "outputs": [
                    str(path.relative_to(PROJECT_ROOT))
                    if path.is_relative_to(PROJECT_ROOT)
                    else str(path)
                    for path in sorted(output_dir.rglob("*"))
                    if path.is_file()
                ],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
