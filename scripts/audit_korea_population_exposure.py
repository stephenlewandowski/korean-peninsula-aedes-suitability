#!/usr/bin/env python3
"""Independently audit Korea population-exposure outputs.

This audit reads the prepared cell-period table and its summaries without
importing the preparation script. It checks coverage, arithmetic
reconciliation, finite weighted metrics, period definitions, interpretation
boundaries, and input provenance. It does not estimate disease incidence,
infection risk, or transmission.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import gzip
import hashlib
import json
import math
from pathlib import Path
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PERIODS = {
    "1975-1984": set(range(1975, 1985)),
    "1995-2004": set(range(1995, 2005)),
    "2015-2024": set(range(2015, 2025)),
}
PERIOD_ORDER = tuple(PERIODS)
EARLY_PERIOD = "1975-1984"
RECENT_PERIOD = "2015-2024"
GEOGRAPHIES = {
    "North Korea": ("North Korea",),
    "South Korea": ("South Korea",),
    "Korean Peninsula": ("North Korea", "South Korea"),
}
CELL_PERIOD_REQUIRED = {
    "species",
    "country",
    "cell_id",
    "period",
    "suitable_month_count",
    "suitable_span_months",
    "longest_contiguous_run",
    "population_mean_ambient",
    "population_n_years",
}
PERIOD_SUMMARY_REQUIRED = {
    "geography",
    "species",
    "period",
    "mean_annual_ambient_population_observed_cells",
    "population_weighted_mean_suitable_months",
    "population_weighted_mean_suitable_span_months",
    "population_weighted_mean_longest_contiguous_run",
    "n_cells_total",
    "n_cells_with_population",
    "n_cells_with_joint_data",
    "population_cell_coverage_fraction",
    "joint_cell_coverage_fraction",
    "interpretation",
}
CHANGE_SUMMARY_REQUIRED = {
    "geography",
    "species",
    "recent_mean_annual_ambient_population_observed_cells",
    "population_in_cells_with_increasing_suitable_month_count",
    "share_recent_population_in_cells_with_increasing_suitable_month_count",
    "population_in_cells_with_longer_suitable_span",
    "share_recent_population_in_cells_with_longer_suitable_span",
    "population_in_cells_with_longer_contiguous_run",
    "population_weighted_suitable_month_count_delta",
    "population_weighted_suitable_span_delta",
    "population_weighted_longest_run_delta",
    "n_cells_paired",
    "interpretation",
}
CELL_METRICS = (
    "suitable_month_count",
    "suitable_span_months",
    "longest_contiguous_run",
)
SUMMARY_METRICS = (
    ("population_weighted_mean_suitable_months", "suitable_month_count"),
    ("population_weighted_mean_suitable_span_months", "suitable_span_months"),
    ("population_weighted_mean_longest_contiguous_run", "longest_contiguous_run"),
)
CHANGE_METRICS = (
    ("population_weighted_suitable_month_count_delta", "suitable_month_count"),
    ("population_weighted_suitable_span_delta", "suitable_span_months"),
    ("population_weighted_longest_run_delta", "longest_contiguous_run"),
)
TOLERANCE = 1e-5


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "outputs" / "korea_focus_population",
    )
    parser.add_argument(
        "--population",
        type=Path,
        default=PROJECT_ROOT / "inputs" / "korea_landscan_population_by_cell_year.csv",
    )
    parser.add_argument(
        "--suitability",
        type=Path,
        default=None,
        help="Optional suitability input; otherwise read it from run metadata.",
    )
    parser.add_argument(
        "--run-metadata",
        type=Path,
        default=None,
        help="Preparation metadata; defaults to output-dir/population_exposure_run_metadata.json.",
    )
    return parser.parse_args()


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else PROJECT_ROOT / path


def read_csv(path: Path) -> list[dict[str, str]]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def finite(value: str, field: str, location: str, errors: list[str]) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        errors.append(f"{location}: {field} must be numeric")
        return math.nan
    if not math.isfinite(number):
        errors.append(f"{location}: {field} must be finite")
    return number


def integer(value: str, field: str, location: str, errors: list[str]) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        errors.append(f"{location}: {field} must be an integer")
        return -1


def require_fields(
    rows: list[dict[str, str]], required: set[str], label: str, errors: list[str]
) -> None:
    fields = set(rows[0]) if rows else set()
    missing = sorted(required - fields)
    if missing:
        errors.append(f"{label} is missing required fields: {missing}")


def close_enough(actual: float, expected: float) -> bool:
    return math.isfinite(actual) and math.isfinite(expected) and math.isclose(
        actual, expected, rel_tol=1e-8, abs_tol=TOLERANCE
    )


def weighted_mean(rows: Iterable[dict[str, str]], metric: str) -> float:
    values: list[float] = []
    weights: list[float] = []
    for row in rows:
        value = float(row[metric])
        weight = float(row["population_mean_ambient"])
        if not math.isfinite(value) or not math.isfinite(weight) or weight < 0:
            return math.nan
        values.append(value)
        weights.append(weight)
    total_weight = sum(weights)
    if not values or total_weight <= 0:
        return math.nan
    return sum(value * weight for value, weight in zip(values, weights)) / total_weight


def row_key(row: dict[str, str]) -> tuple[str, ...]:
    return tuple(row[field] for field in ("species", "country", "cell_id", "period"))


def main() -> None:
    args = parse_args()
    output_dir = resolve_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    metadata_path = resolve_path(
        args.run_metadata or output_dir / "population_exposure_run_metadata.json"
    )
    population_path = resolve_path(args.population)
    cell_period_path = output_dir / "population_cell_period.csv.gz"
    period_summary_path = output_dir / "population_exposure_by_period.csv"
    change_summary_path = output_dir / "population_exposure_change_early_to_recent.csv"
    missingness_path = output_dir / "population_missingness.csv"
    audit_path = output_dir / "population_exposure_audit.json"
    errors: list[str] = []
    checks: dict[str, bool] = {}

    metadata: dict[str, object] = {}
    if not metadata_path.exists():
        errors.append(f"Missing run metadata: {metadata_path}")
    else:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    suitability_path = resolve_path(args.suitability) if args.suitability else None
    if suitability_path is None and metadata:
        recorded = metadata.get("suitability_input")
        if isinstance(recorded, str):
            suitability_path = resolve_path(Path(recorded))
    if suitability_path is None:
        suitability_path = PROJECT_ROOT / "outputs/korea_focus/tables/korea_focus_cell_year_season.csv.gz"

    required_paths = {
        "population": population_path,
        "suitability": suitability_path,
        "cell_period": cell_period_path,
        "period_summary": period_summary_path,
        "change_summary": change_summary_path,
        "missingness": missingness_path,
    }
    for label, path in required_paths.items():
        if not path.exists():
            errors.append(f"Missing {label} file: {path}")

    population_rows: list[dict[str, str]] = []
    cell_rows: list[dict[str, str]] = []
    period_rows: list[dict[str, str]] = []
    change_rows: list[dict[str, str]] = []
    missingness_rows: list[dict[str, str]] = []
    if not errors:
        population_rows = read_csv(population_path)
        cell_rows = read_csv(cell_period_path)
        period_rows = read_csv(period_summary_path)
        change_rows = read_csv(change_summary_path)
        missingness_rows = read_csv(missingness_path)

    if population_rows:
        require_fields(population_rows, {"cell_id", "year", "ambient_population"}, "Population input", errors)
        population_keys: set[tuple[str, int]] = set()
        cells: set[str] = set()
        years: set[int] = set()
        for index, row in enumerate(population_rows, start=2):
            location = f"population line {index}"
            year = integer(row.get("year", ""), "year", location, errors)
            value = finite(row.get("ambient_population", ""), "ambient_population", location, errors)
            cell_id = row.get("cell_id", "").strip()
            if not cell_id:
                errors.append(f"{location}: cell_id is required")
            if year < 1975 or year > 2024:
                errors.append(f"{location}: year is outside 1975–2024")
            if math.isfinite(value) and value < 0:
                errors.append(f"{location}: ambient_population must be non-negative")
            key = (cell_id, year)
            if key in population_keys:
                errors.append(f"{location}: duplicate cell-year {key}")
            population_keys.add(key)
            cells.add(cell_id)
            years.add(year)
        expected_years = set(range(1975, 2025))
        expected_keys = {(cell_id, year) for cell_id in cells for year in expected_years}
        missing_keys = expected_keys - population_keys
        checks["population_input_complete_370_cells_1975_2024"] = (
            len(cells) == 370 and years == expected_years and not missing_keys
        )
        if not checks["population_input_complete_370_cells_1975_2024"]:
            errors.append(
                "Population input is not complete for its observed cells across 1975–2024: "
                f"cells={len(cells)}, years={len(years)}, missing={len(missing_keys)}"
            )

    if cell_rows:
        require_fields(cell_rows, CELL_PERIOD_REQUIRED, "Cell-period output", errors)
        keys = [row_key(row) for row in cell_rows]
        duplicate_count = len(keys) - len(set(keys))
        if duplicate_count:
            errors.append(f"Cell-period output has {duplicate_count} duplicate species-cell-period rows")
        expected_periods = set(PERIOD_ORDER)
        observed_periods = {row.get("period", "") for row in cell_rows}
        if observed_periods != expected_periods:
            errors.append(f"Cell-period output periods are {sorted(observed_periods)}, expected {sorted(expected_periods)}")
        for index, row in enumerate(cell_rows, start=2):
            location = f"cell-period line {index}"
            for field in CELL_METRICS + ("population_mean_ambient",):
                value = finite(row.get(field, ""), field, location, errors)
                if field == "population_mean_ambient" and math.isfinite(value) and value < 0:
                    errors.append(f"{location}: population_mean_ambient must be non-negative")
            years = integer(row.get("population_n_years", ""), "population_n_years", location, errors)
            if years != 10:
                errors.append(f"{location}: population_n_years must equal 10, got {years}")
        checks["cell_period_population_values_complete"] = bool(cell_rows) and all(
            row.get("population_mean_ambient", "").strip() != "" for row in cell_rows
        )

    if cell_rows and period_rows:
        require_fields(period_rows, PERIOD_SUMMARY_REQUIRED, "Period summary", errors)
        summary_keys = [(row.get("geography", ""), row.get("species", ""), row.get("period", "")) for row in period_rows]
        if len(summary_keys) != len(set(summary_keys)):
            errors.append("Period summary contains duplicate geography-species-period rows")
        cell_species = sorted({row["species"] for row in cell_rows})
        expected_summary_keys = {
            (geography, species, period)
            for geography in GEOGRAPHIES
            for species in cell_species
            for period in PERIOD_ORDER
        }
        if set(summary_keys) != expected_summary_keys:
            errors.append("Period summary does not contain exactly the expected geography-species-period rows")

        for row in period_rows:
            geography = row["geography"]
            species = row["species"]
            period = row["period"]
            subset = [
                item
                for item in cell_rows
                if item["species"] == species
                and item["country"] in GEOGRAPHIES.get(geography, ())
                and item["period"] == period
            ]
            if not subset:
                errors.append(f"No cell-period rows reconcile to summary row {(geography, species, period)}")
                continue
            total_population = sum(float(item["population_mean_ambient"]) for item in subset)
            summary_total = finite(row["mean_annual_ambient_population_observed_cells"], "summary population total", str((geography, species, period)), errors)
            if not close_enough(summary_total, total_population):
                errors.append(f"Population total does not reconcile for {(geography, species, period)}")
            for summary_field, cell_field in SUMMARY_METRICS:
                actual = finite(row[summary_field], summary_field, str((geography, species, period)), errors)
                expected = weighted_mean(subset, cell_field)
                if not close_enough(actual, expected):
                    errors.append(f"Weighted metric {summary_field} does not reconcile for {(geography, species, period)}")
            n_cells = len({item["cell_id"] for item in subset})
            if int(row["n_cells_total"]) != n_cells or int(row["n_cells_with_population"]) != n_cells or int(row["n_cells_with_joint_data"]) != n_cells:
                errors.append(f"Cell counts do not reconcile for {(geography, species, period)}")
            for field in ("population_cell_coverage_fraction", "joint_cell_coverage_fraction"):
                coverage = finite(row[field], field, str((geography, species, period)), errors)
                if not close_enough(coverage, 1.0):
                    errors.append(f"Coverage is not 100% for {(geography, species, period)}: {field}={coverage}")
            label = row.get("interpretation", "").lower()
            if "population exposure" not in label or "not disease incidence" not in label:
                errors.append(f"Period summary lacks the required population-exposure boundary for {(geography, species, period)}")
            for field in (field for field, _ in SUMMARY_METRICS):
                if not math.isfinite(float(row[field])):
                    errors.append(f"Non-finite weighted metric in period summary: {field}")
        checks["period_summary_reconciles_with_cell_period"] = not any("reconcile" in error for error in errors)
        checks["period_summary_coverage_is_100_percent"] = not any("Coverage is not 100%" in error for error in errors)

    if missingness_rows:
        for row in missingness_rows:
            missing = integer(row.get("missing_cell_year_rows", ""), "missing_cell_year_rows", "missingness", errors)
            fraction = finite(row.get("missing_fraction", ""), "missing_fraction", "missingness", errors)
            if missing != 0 or not close_enough(fraction, 0.0):
                errors.append(f"Missingness is nonzero for {(row.get('country'), row.get('period'))}")
        checks["missingness_report_is_complete"] = all(
            row.get("missing_cell_year_rows") == "0" and row.get("missing_fraction") in {"0", "0.000000"}
            for row in missingness_rows
        )

    if cell_rows and change_rows:
        require_fields(change_rows, CHANGE_SUMMARY_REQUIRED, "Change summary", errors)
        cell_lookup = {row_key(row): row for row in cell_rows}
        for row in change_rows:
            geography = row["geography"]
            species = row["species"]
            countries = GEOGRAPHIES.get(geography, ())
            paired = []
            cells = {
                (item["country"], item["cell_id"])
                for item in cell_rows
                if item["species"] == species and item["country"] in countries
            }
            for country, cell_id in cells:
                early = cell_lookup.get((species, country, cell_id, EARLY_PERIOD))
                recent = cell_lookup.get((species, country, cell_id, RECENT_PERIOD))
                if early is not None and recent is not None:
                    paired.append((early, recent))
            if int(row["n_cells_paired"]) != len(paired):
                errors.append(f"Paired-cell count does not reconcile for {(geography, species)}")
            recent_population = sum(float(recent["population_mean_ambient"]) for _, recent in paired)
            reported_population = finite(row["recent_mean_annual_ambient_population_observed_cells"], "recent population", str((geography, species)), errors)
            if not close_enough(reported_population, recent_population):
                errors.append(f"Recent population total does not reconcile for {(geography, species)}")
            deltas = {
                metric: [float(recent[metric]) - float(early[metric]) for early, recent in paired]
                for metric in CELL_METRICS
            }
            share_fields = {
                "suitable_month_count": "share_recent_population_in_cells_with_increasing_suitable_month_count",
                "suitable_span_months": "share_recent_population_in_cells_with_longer_suitable_span",
                "longest_contiguous_run": None,
            }
            for metric, summary_field in share_fields.items():
                if summary_field is not None:
                    numerator = sum(
                        float(recent["population_mean_ambient"])
                        for (early, recent), delta in zip(paired, deltas[metric])
                        if delta > 0
                    )
                    actual_share = finite(row[summary_field], summary_field, str((geography, species)), errors)
                    expected_share = numerator / recent_population if recent_population > 0 else math.nan
                    if not close_enough(actual_share, expected_share) or not 0 <= actual_share <= 1:
                        errors.append(f"Population share does not reconcile or is outside [0,1] for {(geography, species)}: {summary_field}")
            for summary_field, metric in CHANGE_METRICS:
                actual = finite(row[summary_field], summary_field, str((geography, species)), errors)
                weighted_values = []
                for early, recent in paired:
                    weighted_values.append(
                        {
                            metric: float(recent[metric]) - float(early[metric]),
                            "population_mean_ambient": recent["population_mean_ambient"],
                        }
                    )
                expected = weighted_mean(weighted_values, metric)
                if not close_enough(actual, expected):
                    errors.append(f"Weighted change metric does not reconcile for {(geography, species)}: {summary_field}")
            label = row.get("interpretation", "").lower()
            if "population exposure" not in label or "not disease incidence" not in label:
                errors.append(f"Change summary lacks the required population-exposure boundary for {(geography, species)}")
        checks["change_summary_reconciles_with_cell_period"] = not any("reconcile" in error for error in errors)
        checks["population_shares_are_between_zero_and_one"] = not any("outside [0,1]" in error for error in errors)
        checks["early_recent_periods_are_documented"] = (
            metadata.get("analysis_scope", {}).get("periods") == list(PERIOD_ORDER)
            and EARLY_PERIOD in PERIOD_ORDER
            and RECENT_PERIOD in PERIOD_ORDER
        )
        if not checks["early_recent_periods_are_documented"]:
            errors.append(f"Run metadata does not document the expected periods {list(PERIOD_ORDER)}")

    if metadata:
        scope_text = json.dumps(metadata.get("analysis_scope", {})).lower()
        checks["interpretation_is_population_exposure_only"] = (
            "population exposure" in scope_text
            and "disease incidence" in scope_text
            and "distinct" in scope_text
        )
        if not checks["interpretation_is_population_exposure_only"]:
            errors.append("Run metadata lacks the required population-exposure interpretation boundary")

    provenance = {
        "population_input": str(population_path),
        "population_input_sha256": sha256_file(population_path) if population_path.exists() else None,
        "suitability_input": str(suitability_path),
        "suitability_input_sha256": sha256_file(suitability_path) if suitability_path.exists() else None,
        "run_metadata": str(metadata_path),
        "run_metadata_sha256": sha256_file(metadata_path) if metadata_path.exists() else None,
        "audited_outputs": {
            path.name: sha256_file(path) for path in (cell_period_path, period_summary_path, change_summary_path, missingness_path) if path.exists()
        },
        "recorded_population_source": metadata.get("population_source") if metadata else None,
    }

    payload = {
        "generated_utc": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "status": "PASS" if not errors else "FAIL",
        "scope": "korea",
        "interpretation": "Population exposure indicators only; not disease risk, disease incidence, infection risk, or transmission estimates.",
        "periods": {
            "all": list(PERIOD_ORDER),
            "early": EARLY_PERIOD,
            "recent": RECENT_PERIOD,
        },
        "checks": checks,
        "provenance": provenance,
        "errors": errors,
    }
    audit_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
