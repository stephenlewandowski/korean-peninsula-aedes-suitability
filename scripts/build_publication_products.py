#!/usr/bin/env python3
"""Build publication-ready figures and summary data for the project website.

The products preserve the repository's evidence boundaries:

* suitability is a model-derived environmental score;
* population results are exposure indicators, not disease-risk estimates;
* occurrence records are presence-only observations without effort;
* trap-abundance rows are pooled 2013-2014 indices with explicit effort.

All headline values are read from audited repository outputs.  The script does
not fit a new biological or disease model.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOCAL_VENDOR = PROJECT_ROOT / "vendor" / "python"
if LOCAL_VENDOR.exists():
    sys.path.insert(0, str(LOCAL_VENDOR))

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.collections import PatchCollection
from matplotlib.colors import Normalize, TwoSlopeNorm
from matplotlib.patches import Polygon


EARLY_PERIOD = "1975-1984"
MIDDLE_PERIOD = "1995-2004"
RECENT_PERIOD = "2015-2024"
SPECIES = ["aegypti", "albopictus"]
SPECIES_LABEL = {
    "aegypti": "Ae. aegypti",
    "albopictus": "Ae. albopictus",
}

COLORS = {
    "ink": "#17333b",
    "muted": "#5d7075",
    "grid": "#c9d4d2",
    "paper": "#fbfcf9",
    "panel": "#f2f5f1",
    "blue": "#1d6996",
    "teal": "#2a9d8f",
    "orange": "#e17c05",
    "red": "#c7452e",
    "purple": "#7b5ea7",
    "gold": "#d9a21b",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--docs-dir",
        type=Path,
        default=PROJECT_ROOT / "docs",
        help="GitHub Pages source directory.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "outputs" / "publication",
        help="Publication manifest and independent audit directory.",
    )
    return parser.parse_args()


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else PROJECT_ROOT / path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def configure_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.titlesize": 14,
            "axes.labelsize": 10,
            "axes.titleweight": "bold",
            "axes.edgecolor": COLORS["grid"],
            "axes.labelcolor": COLORS["ink"],
            "axes.facecolor": COLORS["paper"],
            "figure.facecolor": COLORS["paper"],
            "savefig.facecolor": COLORS["paper"],
            "text.color": COLORS["ink"],
            "xtick.color": COLORS["muted"],
            "ytick.color": COLORS["muted"],
            "grid.color": COLORS["grid"],
            "grid.linewidth": 0.7,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "svg.fonttype": "none",
        }
    )


def load_grid(path: Path) -> list[dict[str, Any]]:
    document = json.loads(path.read_text(encoding="utf-8"))
    features = document.get("features", [])
    if len(features) != 370:
        raise ValueError(f"Expected 370 Korea grid features; found {len(features)}")
    return features


def feature_ring(feature: dict[str, Any]) -> np.ndarray:
    geometry = feature["geometry"]
    if geometry["type"] != "Polygon":
        raise ValueError("Publication map expects Polygon grid features")
    return np.asarray(geometry["coordinates"][0], dtype=float)


def map_extent(features: list[dict[str, Any]]) -> tuple[float, float, float, float]:
    coordinates = np.concatenate([feature_ring(feature) for feature in features])
    return (
        float(coordinates[:, 0].min()),
        float(coordinates[:, 0].max()),
        float(coordinates[:, 1].min()),
        float(coordinates[:, 1].max()),
    )


def draw_grid_values(
    ax: plt.Axes,
    features: list[dict[str, Any]],
    values: dict[str, float],
    cmap: Any,
    norm: Any,
    edgecolor: str = "#ffffff",
    linewidth: float = 0.24,
) -> None:
    patches: list[Polygon] = []
    colors: list[float] = []
    for feature in features:
        cell_id = str(feature["properties"]["cell_id"])
        value = values.get(cell_id)
        if value is None or not math.isfinite(value):
            continue
        patches.append(Polygon(feature_ring(feature), closed=True))
        colors.append(value)
    collection = PatchCollection(
        patches,
        cmap=cmap,
        norm=norm,
        edgecolor=edgecolor,
        linewidth=linewidth,
        antialiased=True,
    )
    collection.set_array(np.asarray(colors))
    ax.add_collection(collection)


def draw_grid_background(
    ax: plt.Axes,
    features: list[dict[str, Any]],
    facecolor: str = "#edf2ef",
    edgecolor: str = "#c5d0ce",
    linewidth: float = 0.25,
) -> None:
    patches = [Polygon(feature_ring(feature), closed=True) for feature in features]
    collection = PatchCollection(
        patches,
        facecolor=facecolor,
        edgecolor=edgecolor,
        linewidth=linewidth,
        antialiased=True,
    )
    ax.add_collection(collection)


def finish_map_axis(ax: plt.Axes, features: list[dict[str, Any]], pad: float = 0.25) -> None:
    x_min, x_max, y_min, y_max = map_extent(features)
    ax.set_xlim(x_min - pad, x_max + pad)
    ax.set_ylim(y_min - pad, y_max + pad)
    ax.set_aspect(1 / math.cos(math.radians((y_min + y_max) / 2)))
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)


def add_country_labels(ax: plt.Axes) -> None:
    ax.text(
        126.0,
        41.1,
        "DPRK\nmodeled extrapolation",
        ha="center",
        va="center",
        fontsize=8,
        color=COLORS["muted"],
        linespacing=1.15,
    )
    ax.text(
        127.4,
        36.1,
        "ROK",
        ha="center",
        va="center",
        fontsize=9,
        color=COLORS["muted"],
    )


def add_figure_note(fig: plt.Figure, text: str) -> None:
    fig.text(
        0.01,
        -0.075,
        text,
        ha="left",
        va="bottom",
        fontsize=8,
        color=COLORS["muted"],
        wrap=True,
    )


def save_figure(fig: plt.Figure, output_stem: Path) -> list[Path]:
    output_stem.parent.mkdir(parents=True, exist_ok=True)
    svg_path = output_stem.with_suffix(".svg")
    png_path = output_stem.with_suffix(".png")
    metadata = {
        "Creator": "korean-peninsula-aedes-suitability/scripts/build_publication_products.py",
        "Date": "2026-08-23",
    }
    fig.savefig(svg_path, bbox_inches="tight", metadata=metadata)
    svg_text = svg_path.read_text(encoding="utf-8")
    svg_path.write_text(
        "\n".join(line.rstrip() for line in svg_text.splitlines()) + "\n",
        encoding="utf-8",
    )
    fig.savefig(
        png_path,
        dpi=180,
        bbox_inches="tight",
        metadata={"Software": metadata["Creator"], "Creation Time": metadata["Date"]},
    )
    plt.close(fig)
    return [svg_path, png_path]


def suitability_change_map(
    cell_period: pd.DataFrame,
    features: list[dict[str, Any]],
    output_stem: Path,
) -> list[Path]:
    values_by_species: dict[str, dict[str, float]] = {}
    all_values: list[float] = []
    for species in SPECIES:
        subset = cell_period[
            (cell_period["species"] == species)
            & (cell_period["period"].isin([EARLY_PERIOD, RECENT_PERIOD]))
        ]
        pivot = subset.pivot(index="cell_id", columns="period", values="mean_suitable_months")
        delta = pivot[RECENT_PERIOD] - pivot[EARLY_PERIOD]
        values_by_species[species] = delta.to_dict()
        all_values.extend(delta.tolist())
    max_abs = max(abs(float(np.nanmin(all_values))), abs(float(np.nanmax(all_values))))
    max_abs = max(max_abs, 0.1)
    norm = TwoSlopeNorm(vmin=-max_abs, vcenter=0, vmax=max_abs)
    cmap = matplotlib.colormaps["RdBu_r"]

    fig, axes = plt.subplots(1, 2, figsize=(10.8, 5.4), constrained_layout=True)
    fig.suptitle(
        "Modeled suitable-month change across the Korean Peninsula",
        fontsize=17,
        fontweight="bold",
        y=1.03,
    )
    for ax, species in zip(axes, SPECIES):
        draw_grid_values(ax, features, values_by_species[species], cmap, norm)
        finish_map_axis(ax, features)
        add_country_labels(ax)
        ax.set_title(f"{SPECIES_LABEL[species]} | {RECENT_PERIOD} minus {EARLY_PERIOD}")
    scalar = matplotlib.cm.ScalarMappable(norm=norm, cmap=cmap)
    colorbar = fig.colorbar(scalar, ax=axes, orientation="horizontal", shrink=0.56, pad=0.02)
    colorbar.set_label("Change in mean suitable months per year")
    add_figure_note(
        fig,
        "0.25° source grid; suitability threshold ≥0.5. DPRK cells are modeled extrapolation. "
        "Environmental suitability only—not observed presence, abundance, or disease risk.",
    )
    return save_figure(fig, output_stem)


def population_exposure_map(
    population_cell_period: pd.DataFrame,
    features: list[dict[str, Any]],
    output_stem: Path,
) -> list[Path]:
    values_by_species: dict[str, dict[str, float]] = {}
    populations: dict[str, float] = {}
    all_values: list[float] = []
    for species in SPECIES:
        subset = population_cell_period[
            (population_cell_period["species"] == species)
            & (population_cell_period["period"].isin([EARLY_PERIOD, RECENT_PERIOD]))
        ]
        metric = subset.pivot(index="cell_id", columns="period", values="suitable_month_count")
        delta = metric[RECENT_PERIOD] - metric[EARLY_PERIOD]
        values_by_species[species] = delta.to_dict()
        all_values.extend(delta.tolist())
        if not populations:
            recent = subset[subset["period"] == RECENT_PERIOD].set_index("cell_id")
            populations = recent["population_mean_ambient"].to_dict()
    max_abs = max(abs(float(np.nanmin(all_values))), abs(float(np.nanmax(all_values))))
    max_abs = max(max_abs, 0.1)
    norm = TwoSlopeNorm(vmin=-max_abs, vcenter=0, vmax=max_abs)
    cmap = matplotlib.colormaps["PuOr_r"]
    max_population = max(populations.values())

    fig, axes = plt.subplots(1, 2, figsize=(10.8, 5.6), constrained_layout=True)
    fig.suptitle(
        "Where modeled change overlaps recent ambient population",
        fontsize=17,
        fontweight="bold",
        y=1.03,
    )
    for ax, species in zip(axes, SPECIES):
        draw_grid_values(ax, features, values_by_species[species], cmap, norm)
        for feature in features:
            properties = feature["properties"]
            cell_id = str(properties["cell_id"])
            population = populations.get(cell_id, 0.0)
            if population <= 0:
                continue
            marker_size = 4 + 76 * math.sqrt(population / max_population)
            ax.scatter(
                float(properties["longitude"]),
                float(properties["latitude"]),
                s=marker_size,
                facecolor="none",
                edgecolor=COLORS["ink"],
                linewidth=0.35,
                alpha=0.42,
            )
        finish_map_axis(ax, features)
        add_country_labels(ax)
        ax.set_title(f"{SPECIES_LABEL[species]} | circle area ∝ recent population")
    scalar = matplotlib.cm.ScalarMappable(norm=norm, cmap=cmap)
    colorbar = fig.colorbar(scalar, ax=axes, orientation="horizontal", shrink=0.52, pad=0.02)
    colorbar.set_label("Early-to-recent change in suitable months")
    add_figure_note(
        fig,
        "Population is mean LandScan ambient population for 2015–2024. Circles show relative "
        "population magnitude, not cases or people at risk. Population exposure only—not disease incidence.",
    )
    return save_figure(fig, output_stem)


def seasonal_profile_figure(monthly: pd.DataFrame, output_stem: Path) -> list[Path]:
    months = list(range(1, 13))
    month_labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    fig, axes = plt.subplots(1, 2, figsize=(11.2, 4.5), sharey=True, constrained_layout=True)
    fig.suptitle(
        "The modeled seasonal profile shifted most in warm-season shoulder months",
        fontsize=17,
        fontweight="bold",
        y=1.04,
    )
    for ax, species in zip(axes, SPECIES):
        subset = monthly[
            (monthly["geography"] == "Korean Peninsula")
            & (monthly["species"] == species)
            & (monthly["period"].isin([EARLY_PERIOD, RECENT_PERIOD]))
        ]
        for period, color, linestyle in [
            (EARLY_PERIOD, COLORS["blue"], "--"),
            (RECENT_PERIOD, COLORS["orange"], "-"),
        ]:
            period_rows = subset[subset["period"] == period].sort_values("month_number")
            ax.plot(
                period_rows["month_number"],
                period_rows["mean_suitability"],
                color=color,
                linewidth=2.5,
                linestyle=linestyle,
                marker="o",
                markersize=4,
                label=period,
            )
        ax.axhline(0.5, color=COLORS["muted"], linewidth=1, linestyle=":")
        ax.text(12.05, 0.5, "0.5 threshold", fontsize=8, color=COLORS["muted"], va="center")
        ax.set_title(SPECIES_LABEL[species])
        ax.set_xlim(1, 12)
        ax.set_ylim(0, 0.86)
        ax.set_xticks(months, month_labels, rotation=45, ha="right")
        ax.set_xlabel("Calendar month")
        ax.grid(axis="y", alpha=0.7)
    axes[0].set_ylabel("Area-weighted mean suitability score")
    axes[1].legend(frameon=False, loc="upper right")
    add_figure_note(
        fig,
        "Combined Korean Peninsula, cosine-latitude weighted. The threshold summarizes modeled "
        "suitability and does not define observed mosquito or transmission season dates.",
    )
    return save_figure(fig, output_stem)


def population_exposure_summary_figure(
    change: pd.DataFrame,
    output_stem: Path,
) -> list[Path]:
    geographies = ["North Korea", "South Korea", "Korean Peninsula"]
    x = np.arange(len(geographies))
    width = 0.34
    fig, axes = plt.subplots(1, 2, figsize=(11.4, 4.7), constrained_layout=True)
    fig.suptitle(
        "Population exposure indicators increased across both national scopes",
        fontsize=17,
        fontweight="bold",
        y=1.04,
    )
    for index, species in enumerate(SPECIES):
        subset = change[change["species"] == species].set_index("geography").loc[geographies]
        shares = 100 * subset["share_recent_population_in_cells_with_increasing_suitable_month_count"]
        deltas = subset["population_weighted_suitable_month_count_delta"]
        offset = (index - 0.5) * width
        bars_share = axes[0].bar(
            x + offset,
            shares,
            width,
            color=COLORS["blue"] if species == "aegypti" else COLORS["orange"],
            label=SPECIES_LABEL[species],
        )
        bars_delta = axes[1].bar(
            x + offset,
            deltas,
            width,
            color=COLORS["blue"] if species == "aegypti" else COLORS["orange"],
            label=SPECIES_LABEL[species],
        )
        axes[0].bar_label(bars_share, labels=[f"{value:.1f}%" for value in shares], padding=3, fontsize=8)
        axes[1].bar_label(bars_delta, labels=[f"+{value:.2f}" for value in deltas], padding=3, fontsize=8)
    axes[0].set_title(
        "Recent population in cells with increasing\nsuitable-month count",
        fontsize=12,
    )
    axes[0].set_ylabel("Share of recent ambient population (%)")
    axes[0].set_ylim(0, 106)
    axes[1].set_title("Population-weighted suitable-month\nchange", fontsize=12)
    axes[1].set_ylabel("Recent minus early (months)")
    axes[1].set_ylim(0, 0.56)
    for ax in axes:
        ax.set_xticks(x, ["DPRK", "ROK", "Peninsula"])
        ax.grid(axis="y", alpha=0.7)
    axes[0].legend(frameon=False, loc="lower left")
    add_figure_note(
        fig,
        "Early: 1975–1984; recent: 2015–2024. Complete population and suitability coverage for 370 cells. "
        "Indicators describe population exposure to modeled suitability—not disease risk or incidence.",
    )
    return save_figure(fig, output_stem)


def evidence_map(
    observations: pd.DataFrame,
    traps: pd.DataFrame,
    features: list[dict[str, Any]],
    output_stem: Path,
) -> list[Path]:
    rok_features = [feature for feature in features if feature["properties"]["country"] == "South Korea"]
    fig = plt.figure(figsize=(10.8, 6.3), constrained_layout=True)
    grid = fig.add_gridspec(1, 2, width_ratios=[1.2, 1])
    ax = fig.add_subplot(grid[0, 0])
    inset = fig.add_subplot(grid[0, 1])
    fig.suptitle(
        "Reviewed ROK Aedes evidence remains observation-type specific",
        fontsize=17,
        fontweight="bold",
        y=1.03,
    )

    draw_grid_background(ax, rok_features)
    scatter = ax.scatter(
        observations["longitude"],
        observations["latitude"],
        c=observations["year"],
        cmap="viridis",
        norm=Normalize(observations["year"].min(), observations["year"].max()),
        s=34,
        edgecolor="#ffffff",
        linewidth=0.55,
        alpha=0.9,
        label=f"Occurrence ({len(observations)})",
        zorder=3,
    )
    ax.scatter(
        traps["longitude"],
        traps["latitude"],
        marker="*",
        s=130,
        color=COLORS["red"],
        edgecolor="#ffffff",
        linewidth=0.7,
        label=f"Pooled trap-index site ({len(traps)})",
        zorder=4,
    )
    finish_map_axis(ax, rok_features, pad=0.2)
    ax.set_title("ROK occurrence coverage and trap sites")
    ax.legend(frameon=False, loc="lower left", fontsize=8)
    colorbar = fig.colorbar(scatter, ax=ax, orientation="horizontal", shrink=0.72, pad=0.01)
    colorbar.set_label("Occurrence collection year")

    draw_grid_background(inset, rok_features)
    inset.scatter(
        traps["longitude"],
        traps["latitude"],
        marker="*",
        s=150,
        color=COLORS["red"],
        edgecolor="#ffffff",
        linewidth=0.7,
        zorder=4,
    )
    offsets = {
        "hapcheon_seosan_ri": (0.04, 0.04),
        "miryang_sannae_myeon": (0.04, -0.05),
        "busan_daejeo_1": (-0.04, 0.04),
        "busan_eulsukdo": (-0.04, -0.05),
        "busan_cheonghak": (0.04, 0.04),
        "busan_dongsam": (0.04, -0.06),
    }
    short_names = {
        "hapcheon_seosan_ri": "Hapcheon",
        "miryang_sannae_myeon": "Miryang",
        "busan_daejeo_1": "Daejeo-1",
        "busan_eulsukdo": "Eulsukdo",
        "busan_cheonghak": "Cheonghak",
        "busan_dongsam": "Dongsam",
    }
    for row in traps.itertuples(index=False):
        dx, dy = offsets[str(row.site_id)]
        inset.annotate(
            short_names[str(row.site_id)],
            (float(row.longitude), float(row.latitude)),
            xytext=(float(row.longitude) + dx, float(row.latitude) + dy),
            fontsize=8,
            color=COLORS["ink"],
            arrowprops={"arrowstyle": "-", "color": COLORS["muted"], "linewidth": 0.6},
        )
    inset.set_xlim(127.75, 129.35)
    inset.set_ylim(34.85, 35.85)
    inset.set_aspect(1 / math.cos(math.radians(35.35)))
    inset.set_xticks([])
    inset.set_yticks([])
    for spine in inset.spines.values():
        spine.set_visible(False)
    inset.set_title("Six pooled 2013–2014 trap-index sites")
    add_figure_note(
        fig,
        "Occurrences are presence-only and have no standardized effort denominator. Trap sites retain 32 trap-nights "
        "and 448 trap-hours per pooled row. No direct DPRK observations are included.",
    )
    return save_figure(fig, output_stem)


def pooled_trap_figure(traps: pd.DataFrame, output_stem: Path) -> list[Path]:
    ordered = traps.sort_values(["value", "site_name"], ascending=[True, True]).copy()
    y = np.arange(len(ordered))
    colors = [
        COLORS["blue"] if site_type == "cow shed" else COLORS["orange"]
        if site_type == "downtown"
        else COLORS["teal"]
        for site_type in ordered["site_type"]
    ]
    fig, ax = plt.subplots(figsize=(9.6, 4.9), constrained_layout=True)
    fig.suptitle(
        "Source-reported Ae. albopictus trap indices at six ROK sites",
        fontsize=17,
        fontweight="bold",
        y=1.03,
    )
    bars = ax.barh(y, ordered["value"], color=colors, height=0.62)
    ax.set_yticks(y, [name.replace(", Busan", "") for name in ordered["site_name"]])
    ax.set_xlabel("Female mosquitoes per trap-night (published index)")
    ax.set_xlim(0, max(1.02, float(ordered["value"].max()) * 1.15))
    ax.grid(axis="x", alpha=0.7)
    ax.bar_label(bars, labels=[f"{value:.1f}" for value in ordered["value"]], padding=4)
    ax.text(
        0.99,
        0.04,
        "Each site-period row: 32 trap-nights | 448 trap-hours\n"
        "April–November 2013 and April–November 2014 pooled",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=9,
        color=COLORS["muted"],
    )
    add_figure_note(
        fig,
        "Kim et al. (2018), Tables 1, 2, and 4. Values are rounded source-reported trap indices; "
        "raw specimen counts and monthly values were not reconstructed.",
    )
    return save_figure(fig, output_stem)


def export_csv(path: Path, rows: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows.to_csv(path, index=False, lineterminator="\n", quoting=csv.QUOTE_MINIMAL)


def build_summary(
    seasonal_change: pd.DataFrame,
    population_change: pd.DataFrame,
    observations: pd.DataFrame,
    traps: pd.DataFrame,
    population_audit: dict[str, Any],
    aedes_audit: dict[str, Any],
) -> dict[str, Any]:
    seasonal_peninsula = seasonal_change.set_index(["geography", "species"]).loc["Korean Peninsula"]
    population_peninsula = population_change.set_index(["geography", "species"]).loc["Korean Peninsula"]
    summary: dict[str, Any] = {
        "status": "publication_products_built_from_audited_outputs",
        "analysis_period": "1975-2024",
        "comparison_periods": [EARLY_PERIOD, MIDDLE_PERIOD, RECENT_PERIOD],
        "grid_cells": 370,
        "north_korea_cells": 215,
        "south_korea_cells": 155,
        "suitability": {},
        "population_exposure": {},
        "rok_aedes_evidence": {
            "occurrence_records": int(len(observations)),
            "occurrence_year_min": int(observations["year"].min()),
            "occurrence_year_max": int(observations["year"].max()),
            "trap_index_rows": int(len(traps)),
            "trap_sites": int(traps["site_id"].nunique()),
            "trap_nights_per_row": int(traps["trap_nights"].iloc[0]),
            "trap_hours_per_row": float(traps["trap_hours"].iloc[0]),
            "total_trap_nights": int(traps["trap_nights"].sum()),
            "total_trap_hours": float(traps["trap_hours"].sum()),
            "trap_periods": ["2013-04-01/2013-11-30", "2014-04-01/2014-11-30"],
            "trap_value_semantics": "source-reported pooled female trap index; not raw counts",
            "audit_status": aedes_audit["status"],
        },
        "quality": {
            "population_audit_status": population_audit["status"],
            "population_coverage_fraction": 1.0,
            "aedes_audit_status": aedes_audit["status"],
            "per_cell_model_uncertainty": "not supplied by source release",
        },
        "interpretation_boundary": (
            "Modeled environmental suitability and population exposure indicators only; "
            "not observed vector abundance outside the six trap sites, disease risk, incidence, "
            "infection probability, or transmission forecasts."
        ),
    }
    for species in SPECIES:
        seasonal = seasonal_peninsula.loc[species]
        population = population_peninsula.loc[species]
        summary["suitability"][species] = {
            "early_mean_suitable_months": float(seasonal[f"mean_suitable_months_{EARLY_PERIOD}"]),
            "recent_mean_suitable_months": float(seasonal[f"mean_suitable_months_{RECENT_PERIOD}"]),
            "change_months": float(seasonal["mean_suitable_months_delta_recent_minus_early"]),
            "onset_change_calendar_month": float(
                seasonal["mean_first_suitable_month_delta_recent_minus_early"]
            ),
            "end_change_calendar_month": float(
                seasonal["mean_last_suitable_month_delta_recent_minus_early"]
            ),
        }
        summary["population_exposure"][species] = {
            "recent_mean_annual_ambient_population_observed_cells": float(
                population["recent_mean_annual_ambient_population_observed_cells"]
            ),
            "share_recent_population_in_cells_with_increasing_suitable_month_count": float(
                population["share_recent_population_in_cells_with_increasing_suitable_month_count"]
            ),
            "population_weighted_suitable_month_count_delta": float(
                population["population_weighted_suitable_month_count_delta"]
            ),
        }
    return summary


def main() -> None:
    args = parse_args()
    docs_dir = resolve_path(args.docs_dir)
    output_dir = resolve_path(args.output_dir)
    figure_dir = docs_dir / "assets" / "figures"
    data_dir = docs_dir / "assets" / "data"
    figure_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    configure_style()

    inputs = {
        "grid": PROJECT_ROOT / "outputs" / "korea_focus" / "korea_focus_cell_grid.geojson",
        "cell_period": PROJECT_ROOT
        / "outputs"
        / "korea_focus"
        / "tables"
        / "korea_focus_cell_decadal_season.csv.gz",
        "monthly": PROJECT_ROOT
        / "outputs"
        / "korea_focus"
        / "tables"
        / "korea_focus_monthly_suitability.csv",
        "seasonal_change": PROJECT_ROOT
        / "outputs"
        / "korea_focus"
        / "tables"
        / "korea_focus_seasonal_change_early_to_recent.csv",
        "population_cell_period": PROJECT_ROOT
        / "outputs"
        / "korea_focus_population"
        / "population_cell_period.csv.gz",
        "population_change": PROJECT_ROOT
        / "outputs"
        / "korea_focus_population"
        / "population_exposure_change_early_to_recent.csv",
        "population_audit": PROJECT_ROOT
        / "outputs"
        / "korea_focus_population"
        / "population_exposure_audit.json",
        "observations": PROJECT_ROOT / "inputs" / "aedes_observations.csv",
        "traps": PROJECT_ROOT / "inputs" / "aedes_trap_abundance.csv",
        "aedes_audit": PROJECT_ROOT
        / "outputs"
        / "rok_aedes_validation"
        / "rok_aedes_observation_audit_metadata.json",
    }
    missing = [str(path) for path in inputs.values() if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing publication inputs:\n" + "\n".join(missing))

    features = load_grid(inputs["grid"])
    cell_period = pd.read_csv(inputs["cell_period"])
    monthly = pd.read_csv(inputs["monthly"])
    seasonal_change = pd.read_csv(inputs["seasonal_change"])
    population_cell_period = pd.read_csv(inputs["population_cell_period"])
    population_change = pd.read_csv(inputs["population_change"])
    observations = pd.read_csv(inputs["observations"])
    traps = pd.read_csv(inputs["traps"])
    population_audit = json.loads(inputs["population_audit"].read_text(encoding="utf-8"))
    aedes_audit = json.loads(inputs["aedes_audit"].read_text(encoding="utf-8"))

    if population_audit.get("status") != "PASS":
        raise ValueError("Population exposure audit must pass before publication")
    if aedes_audit.get("status") != "ready_for_model_review":
        raise ValueError("ROK Aedes audit must be ready_for_model_review before publication")
    if len(observations) != 54 or len(traps) != 6:
        raise ValueError("Expected 54 occurrence records and six pooled trap-index rows")
    if set(traps["collection_years"].astype(str)) != {"2013;2014"}:
        raise ValueError("Trap rows must remain pooled across 2013 and 2014")

    figure_outputs: list[Path] = []
    figure_outputs.extend(
        suitability_change_map(cell_period, features, figure_dir / "suitability-change-map")
    )
    figure_outputs.extend(
        seasonal_profile_figure(monthly, figure_dir / "seasonal-profile-shift")
    )
    figure_outputs.extend(
        population_exposure_map(
            population_cell_period, features, figure_dir / "population-exposure-map"
        )
    )
    figure_outputs.extend(
        population_exposure_summary_figure(
            population_change, figure_dir / "population-exposure-summary"
        )
    )
    figure_outputs.extend(
        evidence_map(observations, traps, features, figure_dir / "rok-aedes-evidence-map")
    )
    figure_outputs.extend(pooled_trap_figure(traps, figure_dir / "pooled-trap-indices"))

    summary = build_summary(
        seasonal_change,
        population_change,
        observations,
        traps,
        population_audit,
        aedes_audit,
    )
    summary_path = data_dir / "project_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    export_csv(data_dir / "suitability_change_summary.csv", seasonal_change)
    export_csv(data_dir / "population_exposure_change.csv", population_change)
    export_csv(
        data_dir / "pooled_trap_indices.csv",
        traps[
            [
                "record_id",
                "site_id",
                "site_name",
                "cell_id",
                "longitude",
                "latitude",
                "collection_start",
                "collection_end",
                "collection_years",
                "active_months",
                "trap_nights",
                "trap_hours",
                "value",
                "value_unit",
                "source_url",
                "license",
            ]
        ],
    )

    generated_outputs = figure_outputs + [
        summary_path,
        data_dir / "suitability_change_summary.csv",
        data_dir / "population_exposure_change.csv",
        data_dir / "pooled_trap_indices.csv",
    ]
    manifest = {
        "generated_utc": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "status": "PASS",
        "purpose": "GitHub Pages publication figures and bounded analysis summaries",
        "inputs": {
            name: {"path": str(path), "sha256": sha256_file(path)}
            for name, path in inputs.items()
        },
        "outputs": {
            str(path.relative_to(PROJECT_ROOT)): {
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            }
            for path in generated_outputs
        },
        "checks": {
            "population_audit_passed": True,
            "aedes_audit_ready_for_model_review": True,
            "occurrence_and_trap_rows_separate": True,
            "trap_rows_are_six_pooled_site_period_indices": True,
            "monthly_trap_rows_created": 0,
            "raw_trap_counts_reconstructed": False,
            "dprk_extrapolation_labeled": True,
            "disease_interpretation_excluded": True,
        },
        "interpretation_boundary": summary["interpretation_boundary"],
        "builder": {
            "path": str(Path(__file__).resolve()),
            "sha256": sha256_file(Path(__file__).resolve()),
        },
    }
    manifest_path = output_dir / "publication_product_manifest.json"
    manifest_text = json.dumps(manifest, indent=2) + "\n"
    manifest_path.write_text(manifest_text, encoding="utf-8")
    (data_dir / "publication_product_manifest.json").write_text(
        manifest_text, encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": "PASS",
                "figures": len(figure_outputs) // 2,
                "figure_files": len(figure_outputs),
                "data_products": 5,
                "occurrence_records": len(observations),
                "pooled_trap_rows": len(traps),
                "manifest": str(manifest_path),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
