#!/usr/bin/env python3
"""Build a Korea-only Climademic Suitability Model summary.

The script reads the two public v2.0 GeoTIFF archives, clips grid cells by
North Korea and South Korea country polygons using cell-center inclusion, and
produces reproducible monthly, season-length, missingness, change, and map
outputs.  It intentionally does not infer disease risk or mosquito abundance.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import re
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

# tifffile is kept in a project-local vendor directory so the analysis can be
# reproduced without requiring rasterio/GDAL.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENDOR_DIR = PROJECT_ROOT / "vendor"
if VENDOR_DIR.exists():
    sys.path.insert(0, str(VENDOR_DIR))

import tifffile  # noqa: E402

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.path import Path as MplPath  # noqa: E402


MONTHS = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]
MONTH_CODES = [f"m{i:02d}" for i in range(1, 13)]
SPECIES = ("aegypti", "albopictus")
GEOGRAPHIES = ("North Korea", "South Korea", "Korean Peninsula")
COUNTRIES = ("North Korea", "South Korea")
PERIODS = {
    "1975-1984": tuple(range(1975, 1985)),
    "1995-2004": tuple(range(1995, 2005)),
    "2015-2024": tuple(range(2015, 2025)),
}
PERIOD_ORDER = tuple(PERIODS)
COUNTRY_TO_CODE = {"North Korea": "PRK", "South Korea": "KOR"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
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
        default=PROJECT_ROOT / "outputs",
    )
    parser.add_argument("--threshold", type=float, default=0.5)
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_year(name: str) -> int:
    match = re.search(r"_(\d{4})_monthly_suitability\.tif$", name)
    if not match:
        raise ValueError(f"Could not parse year from archive member: {name}")
    return int(match.group(1))


def load_geometries(path: Path) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    with path.open(encoding="utf-8") as handle:
        document = json.load(handle)
    target = {}
    context = {}
    for feature in document["features"]:
        name = feature["properties"].get("ADMIN")
        if name in (*COUNTRIES, "China", "Japan", "Russia"):
            context[name] = feature
        if name in COUNTRIES:
            target[name] = feature
    missing = set(COUNTRIES) - set(target)
    if missing:
        raise ValueError(f"Boundary source is missing target countries: {sorted(missing)}")
    return target, context


def geometry_polygons(geometry: dict[str, Any]) -> Iterable[list[list[float]]]:
    if geometry["type"] == "Polygon":
        yield geometry["coordinates"]
    elif geometry["type"] == "MultiPolygon":
        yield from geometry["coordinates"]
    else:
        raise ValueError(f"Unsupported geometry type: {geometry['type']}")


def geometry_mask(geometry: dict[str, Any], points: np.ndarray) -> np.ndarray:
    """Return a point-in-polygon mask, respecting polygon holes."""
    output = np.zeros(points.shape[0], dtype=bool)
    for rings in geometry_polygons(geometry):
        polygon_mask = MplPath(np.asarray(rings[0], dtype=float)).contains_points(points)
        for hole in rings[1:]:
            polygon_mask &= ~MplPath(np.asarray(hole, dtype=float)).contains_points(points)
        output |= polygon_mask
    return output


def read_raster_from_zip(archive: zipfile.ZipFile, member: str) -> np.ndarray:
    with archive.open(member) as handle:
        data = handle.read()
    raster = np.asarray(tifffile.imread(io.BytesIO(data)))
    if raster.ndim != 3:
        raise ValueError(f"Expected a 12-band raster, got shape {raster.shape} for {member}")
    if raster.shape[-1] == 12:
        return raster
    if raster.shape[0] == 12:
        return np.moveaxis(raster, 0, -1)
    raise ValueError(f"Could not identify 12 monthly bands in {member}: {raster.shape}")


def build_grid(
    sample_raster: np.ndarray,
    target_features: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    height, width = sample_raster.shape[:2]
    longitudes = -180.0 + 0.125 + 0.25 * np.arange(width)
    latitudes = 83.75 - 0.125 - 0.25 * np.arange(height)

    # A regional window reduces memory and makes the center-in-polygon rule
    # explicit. It is intentionally wider than the target polygons.
    region_longitude = (123.0, 132.5)
    region_latitude = (32.0, 44.0)
    row_indices = np.where((latitudes >= region_latitude[0]) & (latitudes <= region_latitude[1]))[0]
    col_indices = np.where(
        (longitudes >= region_longitude[0]) & (longitudes <= region_longitude[1])
    )[0]
    grid_lon, grid_lat = np.meshgrid(longitudes[col_indices], latitudes[row_indices])
    points = np.column_stack((grid_lon.ravel(), grid_lat.ravel()))

    masks: dict[str, np.ndarray] = {}
    for name, feature in target_features.items():
        masks[name] = geometry_mask(feature["geometry"], points).reshape(grid_lon.shape)
    masks["Korean Peninsula"] = masks["North Korea"] | masks["South Korea"]

    country_grid = np.full(grid_lon.shape, "", dtype=object)
    country_grid[masks["North Korea"]] = "North Korea"
    country_grid[masks["South Korea"]] = "South Korea"
    target_mask = masks["Korean Peninsula"]
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


def period_for_year(year: int) -> str:
    for label, years in PERIODS.items():
        if year in years:
            return label
    # The complete source time series is retained in the cell-year extract,
    # while the regional comparison tables use only the three defined periods.
    return "intermediate"


def safe_mean(values: np.ndarray) -> float:
    return float(np.mean(values)) if values.size else math.nan


def safe_sd(values: np.ndarray) -> float:
    return float(np.std(values, ddof=1)) if values.size > 1 else math.nan


def safe_quantile(values: np.ndarray, quantile: float) -> float:
    return float(np.quantile(values, quantile)) if values.size else math.nan


def weighted_mean(values: np.ndarray, weights: np.ndarray) -> float:
    if values.size == 0:
        return math.nan
    return float(np.average(values, weights=weights))


def weighted_share(values: np.ndarray, weights: np.ndarray, threshold: float) -> float:
    if values.size == 0:
        return math.nan
    return float(np.average(values >= threshold, weights=weights))


def valid_values(values: np.ndarray) -> np.ndarray:
    return np.isfinite(values) & (values >= 0.0) & (values <= 1.0)


def monthly_summary_rows(
    cell_df: pd.DataFrame,
    threshold: float,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for species in SPECIES:
        for geography in GEOGRAPHIES:
            source = cell_df[cell_df["species"].eq(species)]
            if geography != "Korean Peninsula":
                source = source[source["country"].eq(geography)]
            for period in PERIOD_ORDER:
                subset = source[source["period"].eq(period)]
                total_cell_years = len(subset)
                total_cells = subset["cell_id"].nunique()
                for month_index, month in enumerate(MONTHS):
                    column = MONTH_CODES[month_index]
                    raw = subset[column].to_numpy(dtype=float)
                    ok = np.isfinite(raw)
                    values = raw[ok]
                    weights = subset.loc[ok, "area_weight"].to_numpy(dtype=float)
                    n_valid = int(ok.sum())
                    rows.append(
                        {
                            "geography": geography,
                            "species": species,
                            "period": period,
                            "month_number": month_index + 1,
                            "month": month,
                            "mean_suitability": weighted_mean(values, weights),
                            "mean_suitability_unweighted": safe_mean(values),
                            "median_suitability": safe_quantile(values, 0.50),
                            "p25_suitability": safe_quantile(values, 0.25),
                            "p75_suitability": safe_quantile(values, 0.75),
                            "spatial_temporal_sd": safe_sd(values),
                            "share_suitable_area": weighted_share(values, weights, threshold),
                            "share_suitable_cells": safe_mean(values >= threshold),
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


def season_summary_rows(
    cell_df: pd.DataFrame,
    threshold: float,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for species in SPECIES:
        for geography in GEOGRAPHIES:
            source = cell_df[cell_df["species"].eq(species)]
            if geography != "Korean Peninsula":
                source = source[source["country"].eq(geography)]
            for period in PERIOD_ORDER:
                subset = source[source["period"].eq(period)]
                observed = subset["suitable_months_observed"].to_numpy(dtype=float)
                complete = subset["suitable_month_count"].notna().to_numpy()
                season = subset.loc[complete, "suitable_month_count"].to_numpy(dtype=float)
                weights = subset.loc[complete, "area_weight"].to_numpy(dtype=float)
                total_cell_years = len(subset)
                complete_cell_years = int(complete.sum())
                rows.append(
                    {
                        "geography": geography,
                        "species": species,
                        "period": period,
                        "mean_suitable_months": weighted_mean(season, weights),
                        "mean_suitable_months_unweighted": safe_mean(season),
                        "median_suitable_months": safe_quantile(season, 0.50),
                        "p25_suitable_months": safe_quantile(season, 0.25),
                        "p75_suitable_months": safe_quantile(season, 0.75),
                        "suitable_months_sd": safe_sd(season),
                        "mean_suitable_months_observed": safe_mean(observed),
                        "mean_valid_months": safe_mean(subset["n_valid_months"].to_numpy(dtype=float)),
                        "n_total_cells": subset["cell_id"].nunique(),
                        "n_total_cell_years": total_cell_years,
                        "n_complete_cell_years": complete_cell_years,
                        "complete_cell_year_fraction": (
                            complete_cell_years / total_cell_years if total_cell_years else math.nan
                        ),
                        "threshold": threshold,
                    }
                )
    return rows


def build_change_table(
    monthly_df: pd.DataFrame,
    season_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    monthly = monthly_df[monthly_df["period"].isin(("1975-1984", "2015-2024"))].copy()
    monthly_pivot = monthly.pivot_table(
        index=["geography", "species", "month_number", "month"],
        columns="period",
        values=["mean_suitability", "mean_suitability_unweighted", "share_suitable_area"],
        aggfunc="first",
    ).reset_index()
    monthly_pivot.columns = [
        "_".join([str(part) for part in col if str(part) != ""]).strip("_")
        if isinstance(col, tuple)
        else str(col)
        for col in monthly_pivot.columns
    ]
    for metric in ("mean_suitability", "mean_suitability_unweighted", "share_suitable_area"):
        monthly_pivot[f"{metric}_delta_recent_minus_early"] = (
            monthly_pivot[f"{metric}_2015-2024"] - monthly_pivot[f"{metric}_1975-1984"]
        )

    season = season_df[season_df["period"].isin(("1975-1984", "2015-2024"))].copy()
    season_pivot = season.pivot_table(
        index=["geography", "species"],
        columns="period",
        values=["mean_suitable_months", "mean_suitable_months_unweighted"],
        aggfunc="first",
    ).reset_index()
    season_pivot.columns = [
        "_".join([str(part) for part in col if str(part) != ""]).strip("_")
        if isinstance(col, tuple)
        else str(col)
        for col in season_pivot.columns
    ]
    for metric in ("mean_suitable_months", "mean_suitable_months_unweighted"):
        season_pivot[f"{metric}_delta_recent_minus_early"] = (
            season_pivot[f"{metric}_2015-2024"] - season_pivot[f"{metric}_1975-1984"]
        )
    return monthly_pivot, season_pivot


def build_cell_decadal_summary(cell_df: pd.DataFrame) -> pd.DataFrame:
    output: list[dict[str, Any]] = []
    group_columns = ["species", "country", "cell_id", "row_global", "col_global", "longitude", "latitude", "area_weight", "period"]
    for keys, subset in cell_df.groupby(group_columns, sort=False, dropna=False):
        species, country, cell_id, row_global, col_global, longitude, latitude, area_weight, period = keys
        record: dict[str, Any] = {
            "species": species,
            "country": country,
            "cell_id": cell_id,
            "row_global": int(row_global),
            "col_global": int(col_global),
            "longitude": float(longitude),
            "latitude": float(latitude),
            "area_weight": float(area_weight),
            "period": period,
            "n_years": int(subset["year"].nunique()),
            "complete_year_fraction": float(subset["suitable_month_count"].notna().mean()),
            "valid_month_fraction": float(subset["n_valid_months"].sum() / (len(subset) * 12)),
            "mean_suitable_months": float(subset["suitable_month_count"].mean()),
            "mean_suitable_months_observed": float(subset["suitable_months_observed"].mean()),
            "mean_annual_suitability": float(subset["annual_mean_suitability"].mean()),
        }
        for month_code in MONTH_CODES:
            record[f"mean_{month_code}"] = float(subset[month_code].mean())
        output.append(record)
    return pd.DataFrame(output)


def geometry_rings(feature: dict[str, Any]) -> Iterable[np.ndarray]:
    for rings in geometry_polygons(feature["geometry"]):
        for ring in rings:
            yield np.asarray(ring, dtype=float)


def draw_context_boundaries(ax: Any, context: dict[str, dict[str, Any]]) -> None:
    for name, feature in context.items():
        color = "#2b6f9e" if name in COUNTRIES else "#777777"
        width = 0.85 if name in COUNTRIES else 0.45
        for ring in geometry_rings(feature):
            ax.plot(ring[:, 0], ring[:, 1], color=color, linewidth=width, zorder=4)


def map_extent(grid: dict[str, Any]) -> tuple[float, float, float, float]:
    target = grid["target_mask"]
    lons = grid["grid_lon"][target]
    lats = grid["grid_lat"][target]
    return (
        float(lons.min() - 0.5),
        float(lons.max() + 0.5),
        float(lats.min() - 0.5),
        float(lats.max() + 0.5),
    )


def render_raster_map(
    cell_summary: pd.DataFrame,
    grid: dict[str, Any],
    context: dict[str, dict[str, Any]],
    output_path: Path,
    value_column: str,
    cmap: str,
    vmin: float,
    vmax: float,
    colorbar_label: str,
    title_prefix: str,
    periods: tuple[str, ...] = PERIOD_ORDER,
    change_mode: bool = False,
) -> None:
    nrows = 1 if change_mode else 2
    ncols = 2 if change_mode else len(periods)
    fig, axes = plt.subplots(
        nrows=nrows,
        ncols=ncols,
        figsize=(4.55 * ncols, 5.7 * nrows),
        squeeze=False,
        constrained_layout=True,
    )
    extent = map_extent(grid)
    row0 = int(grid["row_indices"][0])
    col0 = int(grid["col_indices"][0])
    shape = grid["grid_lon"].shape

    if change_mode:
        plot_jobs = [(0, index, species, periods[0]) for index, species in enumerate(SPECIES)]
    else:
        plot_jobs = [
            (row_index, col_index, species, period)
            for row_index, species in enumerate(SPECIES)
            for col_index, period in enumerate(periods)
        ]

    for plot_row, plot_col, species, period in plot_jobs:
        species_data = cell_summary[cell_summary["species"].eq(species)]
        ax = axes[plot_row, plot_col]
        image = np.full(shape, np.nan, dtype=float)
        subset = species_data[species_data["period"].eq(period)]
        if change_mode:
            early = species_data[species_data["period"].eq("1975-1984")].set_index("cell_id")
            recent = species_data[species_data["period"].eq("2015-2024")].set_index("cell_id")
            subset = recent.join(early[[value_column]], lsuffix="_recent", rsuffix="_early").reset_index()
            subset["map_value"] = subset[f"{value_column}_recent"] - subset[f"{value_column}_early"]
        else:
            subset = subset.copy()
            subset["map_value"] = subset[value_column]
        if not subset.empty:
            rr = subset["row_global"].to_numpy(dtype=int) - row0
            cc = subset["col_global"].to_numpy(dtype=int) - col0
            image[rr, cc] = subset["map_value"].to_numpy(dtype=float)
        im = ax.imshow(
            image,
            origin="upper",
            extent=(
                grid["longitudes"][grid["col_indices"][0]] - 0.125,
                grid["longitudes"][grid["col_indices"][-1]] + 0.125,
                grid["latitudes"][grid["row_indices"][-1]] - 0.125,
                grid["latitudes"][grid["row_indices"][0]] + 0.125,
            ),
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
        if change_mode:
            ax.set_title(
                "Aedes " + species + "\n2015–2024 minus 1975–1984",
                fontsize=10,
            )
        else:
            ax.set_title(period, fontsize=10)
        if (change_mode and plot_col == 0) or (not change_mode and plot_col == 0):
            ax.set_ylabel("Aedes " + ("aegypti" if species == "aegypti" else "albopictus"), fontsize=10)
        ax.set_xlabel("Longitude")
        ax.tick_params(labelsize=8)
        if (not change_mode and plot_row == 0) or change_mode:
            ax.text(126.55, 42.1, "North Korea", fontsize=7, color="#2b6f9e", zorder=5)
            ax.text(127.55, 35.15, "South Korea", fontsize=7, color="#2b6f9e", zorder=5)
        if change_mode or (not change_mode and plot_col == len(periods) - 1):
            fig.colorbar(im, ax=ax, shrink=0.82, pad=0.02, label=colorbar_label)

    fig.suptitle(title_prefix, fontsize=13)
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def render_monthly_heatmap(
    monthly_df: pd.DataFrame,
    output_path: Path,
) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.5), constrained_layout=True)
    month_labels = [m[:3] for m in MONTHS]
    for ax, species in zip(axes, SPECIES):
        subset = monthly_df[
            monthly_df["geography"].eq("Korean Peninsula") & monthly_df["species"].eq(species)
        ]
        matrix = subset.pivot(index="period", columns="month_number", values="mean_suitability")
        matrix = matrix.reindex(index=PERIOD_ORDER, columns=range(1, 13))
        image = ax.imshow(matrix.to_numpy(dtype=float), vmin=0, vmax=1, cmap="viridis", aspect="auto")
        ax.set_xticks(range(12), month_labels)
        ax.set_yticks(range(3), PERIOD_ORDER)
        ax.set_title("Aedes " + species)
        ax.set_xlabel("Month")
        for y in range(matrix.shape[0]):
            for x in range(matrix.shape[1]):
                value = matrix.iloc[y, x]
                if np.isfinite(value):
                    ax.text(x, y, f"{value:.2f}", ha="center", va="center", fontsize=7, color="white")
        fig.colorbar(image, ax=ax, shrink=0.8, label="Area-weighted mean suitability")
    fig.suptitle("Korean Peninsula monthly suitability by comparison period", fontsize=13)
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def write_csv(df: pd.DataFrame, path: Path, gzip: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, compression="gzip" if gzip else None, float_format="%.6f")


def create_metadata(
    args: argparse.Namespace,
    grid: dict[str, Any],
    cell_df: pd.DataFrame,
    source_paths: dict[str, Path],
) -> dict[str, Any]:
    return {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "analysis_scope": {
            "countries": list(COUNTRIES),
            "geographies": list(GEOGRAPHIES),
            "species": list(SPECIES),
            "years": [1975, 2024],
            "periods": {key: list(value) for key, value in PERIODS.items()},
        },
        "source": {
            "zenodo_record": "https://zenodo.org/records/21924442",
            "zenodo_version": "2.0",
            "dataset_title": "Global habitat suitability dataset for Aedes aegypti and Aedes albopictus derived using the Climademic Suitability Model",
            "aegypti_zip_sha256": sha256_file(source_paths["aegypti"]),
            "albopictus_zip_sha256": sha256_file(source_paths["albopictus"]),
            "data_specification_sha256": sha256_file(source_paths["specification"]),
            "model_repository": "https://github.com/ClimSocAna/climademic_suitability_model",
            "boundary_source": "https://github.com/nvkelso/natural-earth-vector/blob/master/geojson/ne_10m_admin_0_countries.geojson",
            "boundary_sha256": sha256_file(source_paths["boundary"]),
        },
        "model_and_aggregation": {
            "input_crs": "EPSG:4326",
            "input_resolution_degrees": 0.25,
            "probability_range": [0.0, 1.0],
            "nodata_value": -1.0,
            "suitability_threshold": args.threshold,
            "threshold_basis": "The authors describe 0.5 as the decision boundary; this analysis uses score >= 0.5 for suitable-month counts.",
            "cell_inclusion": "A grid cell is included when its center falls inside the Natural Earth 10m country polygon; boundary-edge partial-cell area is not clipped.",
            "regional_mean": "Primary means are cosine(latitude)-weighted across valid cell-year observations; unweighted means are retained for aggregation sensitivity.",
            "season_length": "Number of calendar months in a year with suitability >= threshold. Primary means use only complete 12-month cell-years; observed-month counts are retained for missingness diagnostics.",
            "missingness": "No imputation is performed. Values outside [0, 1], NaN, and -1 are treated as missing.",
            "uncertainty": "The source provides probability-like model scores but no per-cell uncertainty layer. Quantiles, standard deviations, valid counts, and missingness are descriptive variability indicators, not model confidence intervals.",
        },
        "grid": {
            "source_raster_shape": [grid["height"], grid["width"], 12],
            "regional_window": {
                "longitude": [123.0, 132.5],
                "latitude": [32.0, 44.0],
            },
            "target_cell_counts": {
                name: int(grid["masks"][name].sum()) for name in GEOGRAPHIES
            },
        },
        "output_row_counts": {
            "cell_year_monthly": int(len(cell_df)),
        },
    }


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir
    table_dir = output_dir / "tables"
    map_dir = output_dir / "maps"
    metadata_dir = PROJECT_ROOT / "metadata"
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

    target_features, context_features = load_geometries(args.boundary)
    first_member: str
    with zipfile.ZipFile(args.aegypti_zip) as archive:
        first_member = sorted(name for name in archive.namelist() if name.endswith(".tif"))[0]
        sample = read_raster_from_zip(archive, first_member)
    grid = build_grid(sample, target_features)

    cell_rows: list[dict[str, Any]] = []
    for species, archive_path in (("aegypti", args.aegypti_zip), ("albopictus", args.albopictus_zip)):
        with zipfile.ZipFile(archive_path) as archive:
            members = sorted(
                (name for name in archive.namelist() if name.endswith(".tif")),
                key=parse_year,
            )
            years = [parse_year(name) for name in members]
            expected_years = list(range(1975, 2025))
            if years != expected_years:
                raise ValueError(f"Unexpected year inventory for {species}: {years}")
            for member in members:
                year = parse_year(member)
                period = period_for_year(year)
                raster = read_raster_from_zip(archive, member)
                if raster.shape[:2] != (grid["height"], grid["width"]):
                    raise ValueError(f"Grid shape changed in {member}: {raster.shape}")
                regional = raster[
                    grid["row_indices"][:, None],
                    grid["col_indices"][None, :],
                    :,
                ]
                target_indices = np.flatnonzero(grid["target_mask"].ravel())
                flat = regional.reshape(-1, 12)[target_indices].astype(float)
                valid = valid_values(flat)
                clean = flat.copy()
                clean[~valid] = np.nan
                row_grid, col_grid = np.indices(grid["grid_lon"].shape)
                flat_row_global = (row_grid.ravel() + int(grid["row_indices"][0]))[target_indices]
                flat_col_global = (col_grid.ravel() + int(grid["col_indices"][0]))[target_indices]
                flat_lon = grid["grid_lon"].ravel()[target_indices]
                flat_lat = grid["grid_lat"].ravel()[target_indices]
                flat_weight = grid["area_weight"].ravel()[target_indices]
                flat_country = grid["country_grid"].ravel()[target_indices]
                valid_months = valid.sum(axis=1).astype(int)
                suitable_observed = (valid & (flat >= args.threshold)).sum(axis=1).astype(int)
                suitable_complete = np.where(valid_months == 12, suitable_observed, np.nan)
                annual_mean = np.nanmean(clean, axis=1)
                for index in range(flat.shape[0]):
                    record: dict[str, Any] = {
                        "species": species,
                        "country": str(flat_country[index]),
                        "cell_id": f"r{flat_row_global[index]:03d}c{flat_col_global[index]:04d}",
                        "row_global": int(flat_row_global[index]),
                        "col_global": int(flat_col_global[index]),
                        "longitude": float(flat_lon[index]),
                        "latitude": float(flat_lat[index]),
                        "area_weight": float(flat_weight[index]),
                        "year": year,
                        "period": period,
                        "n_valid_months": int(valid_months[index]),
                        "coverage_fraction": float(valid_months[index] / 12.0),
                        "suitable_months_observed": int(suitable_observed[index]),
                        "suitable_month_count": float(suitable_complete[index]) if np.isfinite(suitable_complete[index]) else math.nan,
                        "annual_mean_suitability": float(annual_mean[index]),
                    }
                    for month_index, code in enumerate(MONTH_CODES):
                        record[code] = float(clean[index, month_index]) if np.isfinite(clean[index, month_index]) else math.nan
                    cell_rows.append(record)

    cell_df = pd.DataFrame(cell_rows)
    cell_df = cell_df.sort_values(["species", "country", "cell_id", "year"]).reset_index(drop=True)
    monthly_df = pd.DataFrame(monthly_summary_rows(cell_df, args.threshold))
    season_df = pd.DataFrame(season_summary_rows(cell_df, args.threshold))
    monthly_change_df, season_change_df = build_change_table(monthly_df, season_df)
    cell_decadal_df = build_cell_decadal_summary(cell_df)

    write_csv(cell_df, table_dir / "korea_cell_year_monthly.csv.gz", gzip=True)
    write_csv(cell_decadal_df, table_dir / "korea_cell_decadal_summary.csv.gz", gzip=True)
    write_csv(monthly_df, table_dir / "korea_regional_monthly_suitability.csv")
    write_csv(season_df, table_dir / "korea_regional_suitable_months.csv")
    write_csv(monthly_change_df, table_dir / "korea_monthly_change_early_to_recent.csv")
    write_csv(season_change_df, table_dir / "korea_suitable_months_change_early_to_recent.csv")
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
        table_dir / "korea_missingness_summary.csv",
    )

    render_raster_map(
        cell_decadal_df,
        grid,
        context_features,
        map_dir / "korea_suitable_months_decades.png",
        value_column="mean_suitable_months",
        cmap="YlGnBu",
        vmin=0,
        vmax=12,
        colorbar_label="Mean suitable months per year",
        title_prefix="Climademic Aedes suitable-month count: Korean Peninsula",
    )
    render_raster_map(
        cell_decadal_df,
        grid,
        context_features,
        map_dir / "korea_mean_suitability_decades.png",
        value_column="mean_annual_suitability",
        cmap="viridis",
        vmin=0,
        vmax=1,
        colorbar_label="Mean annual suitability",
        title_prefix="Climademic Aedes mean annual suitability: Korean Peninsula",
    )
    render_raster_map(
        cell_decadal_df,
        grid,
        context_features,
        map_dir / "korea_suitable_months_change_early_to_recent.png",
        value_column="mean_suitable_months",
        cmap="RdBu_r",
        vmin=-6,
        vmax=6,
        colorbar_label="Change in suitable months",
        title_prefix="Change in suitable-month count: recent minus early decade",
        periods=("change",),
        change_mode=True,
    )
    render_monthly_heatmap(monthly_df, map_dir / "korea_monthly_suitability_heatmap.png")

    metadata = create_metadata(args, grid, cell_df, source_paths)
    metadata["source"]["retrieval_date"] = "2026-08-19"
    metadata["source"]["current_zenodo_record_version"] = "2.0"
    metadata["source"]["analysis_reference_file"] = "Climademic-Suitability-Model-Aedes-Reference-2026-08-16.md"
    commit_metadata_path = metadata_dir / "github_main_commit.json"
    if commit_metadata_path.exists():
        with commit_metadata_path.open(encoding="utf-8") as handle:
            commit_metadata = json.load(handle)
        metadata["source"]["model_repository_commit"] = commit_metadata.get("sha")
    record_metadata_path = metadata_dir / "zenodo_record_21924442.json"
    if record_metadata_path.exists():
        with record_metadata_path.open(encoding="utf-8") as handle:
            record_metadata = json.load(handle)
        metadata["source"]["zenodo_file_inventory"] = [
            {
                "key": item.get("key"),
                "size": item.get("size"),
                "checksum": item.get("checksum"),
            }
            for item in record_metadata.get("files", [])
        ]
    with (metadata_dir / "korea_analysis_run_metadata.json").open("w", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2)

    print(json.dumps({
        "cell_year_rows": len(cell_df),
        "cell_decadal_rows": len(cell_decadal_df),
        "monthly_rows": len(monthly_df),
        "season_rows": len(season_df),
        "target_cells": metadata["grid"]["target_cell_counts"],
        "outputs": [str(path.relative_to(PROJECT_ROOT)) for path in sorted(output_dir.rglob("*")) if path.is_file()],
    }, indent=2))


if __name__ == "__main__":
    main()
