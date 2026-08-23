#!/usr/bin/env python3
"""Prepare separate ROK Aedes occurrence and effort-aware model inputs.

The six imported Kim et al. (2018) rows are site-level female trap indices
pooled across the 2013 and 2014 April-November seasonal windows.  This script
keeps those rows as six observations with explicit trap-night and trap-hour
effort.  It never expands them into monthly rows and never treats the
published indices as reconstructed raw specimen counts.

The output contains two design matrices rather than one merged table:

* occurrence records remain presence-only observations;
* trap-abundance records remain effort-aware, site-pooled trap indices.

This is a preparation and provenance check, not a fitted model or a disease
risk/incidence estimate.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import math
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

OCCURRENCE_COLUMNS = [
    "record_id",
    "source_id",
    "observation_type",
    "species",
    "country",
    "geography",
    "cell_id",
    "longitude",
    "latitude",
    "collection_date",
    "date_precision",
    "year",
    "month",
    "value",
    "unit",
    "sampling_effort",
    "taxonomic_basis",
    "license",
    "reporting_note",
]

TRAP_ABUNDANCE_COLUMNS = [
    "record_id",
    "source_id",
    "observation_type",
    "species",
    "country",
    "site_id",
    "site_name",
    "site_type",
    "habitat",
    "cell_id",
    "longitude",
    "latitude",
    "source_coordinate",
    "collection_start",
    "collection_end",
    "collection_years",
    "active_months",
    "sampling_frequency",
    "trap_type",
    "trap_bait",
    "trap_start_time",
    "trap_end_time",
    "trap_hours_per_night",
    "trap_nights",
    "trap_hours",
    "value",
    "value_unit",
    "value_qualifier",
    "sex",
    "taxonomic_basis",
    "license",
    "source_url",
    "source_table",
    "reporting_note",
]

OCCURRENCE_OUTPUT_COLUMNS = OCCURRENCE_COLUMNS + [
    "model_input_role",
    "time_resolution",
    "aggregation_level",
    "observation_denominator",
    "effort_hours",
    "count_semantics",
    "monthly_expansion",
    "disease_endpoint",
]

TRAP_OUTPUT_COLUMNS = TRAP_ABUNDANCE_COLUMNS + [
    "model_input_role",
    "period_definition",
    "period_label",
    "time_resolution",
    "aggregation_level",
    "observation_denominator",
    "effort_denominator",
    "effort_hours",
    "sampling_units",
    "count_semantics",
    "monthly_expansion",
    "disease_endpoint",
]

EXPECTED_PERIOD_DEFINITION = (
    "2013-04-01/2013-11-30;2014-04-01/2014-11-30"
)
EXPECTED_PERIOD_LABEL = "2013-2014_April-November_seasonal_windows"
EXPECTED_COLLECTION_START = "2013-04-01"
EXPECTED_COLLECTION_END = "2014-11-30"
EXPECTED_COLLECTION_YEARS = "2013;2014"
EXPECTED_ACTIVE_MONTHS = "04;05;06;07;08;09;10;11"
EXPECTED_TRAP_HOURS_PER_NIGHT = 14.0
EXPECTED_TRAP_NIGHTS_PER_ROW = 32
EXPECTED_TRAP_HOURS_PER_ROW = 448.0
EXPECTED_VALUE_UNIT = "female mosquitoes per trap-night"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--occurrences",
        type=Path,
        default=PROJECT_ROOT / "inputs" / "aedes_observations.csv",
        help="Reviewed occurrence-only input CSV.",
    )
    parser.add_argument(
        "--trap-abundance",
        type=Path,
        default=PROJECT_ROOT / "inputs" / "aedes_trap_abundance.csv",
        help="Separate effort-aware trap-abundance input CSV.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "outputs" / "rok_aedes_model_input",
        help="Directory for the two design matrices and manifest.",
    )
    parser.add_argument(
        "--expected-trap-rows",
        type=int,
        default=6,
        help="Expected number of retained pooled trap rows (default: 6).",
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


def read_csv(path: Path, expected_columns: list[str]) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing input CSV: {path}")
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != expected_columns:
            raise ValueError(
                f"{path} has an unexpected header. Expected exactly: "
                f"{expected_columns}"
            )
        rows: list[dict[str, str]] = []
        for line_number, row in enumerate(reader, start=2):
            if None in row:
                raise ValueError(f"{path}:{line_number} has extra CSV fields")
            cleaned = {key: (value or "").strip() for key, value in row.items()}
            cleaned["_line"] = str(line_number)
            rows.append(cleaned)
    return rows


def require_text(row: dict[str, str], fields: list[str], location: str) -> None:
    missing = [field for field in fields if not row.get(field, "")]
    if missing:
        raise ValueError(f"{location}: required fields are blank: {', '.join(missing)}")


def finite_float(value: str, field: str, location: str) -> float:
    try:
        number = float(value)
    except ValueError as error:
        raise ValueError(f"{location}: {field} must be numeric") from error
    if not math.isfinite(number):
        raise ValueError(f"{location}: {field} must be finite")
    return number


def integer(value: str, field: str, location: str) -> int:
    try:
        return int(value)
    except ValueError as error:
        raise ValueError(f"{location}: {field} must be an integer") from error


def validate_occurrences(rows: list[dict[str, str]]) -> None:
    if not rows:
        raise ValueError("The occurrence input is empty; no occurrence design matrix was prepared")
    record_ids: set[str] = set()
    for row in rows:
        location = f"occurrence line {row['_line']}"
        require_text(
            row,
            [
                "record_id",
                "source_id",
                "species",
                "country",
                "longitude",
                "latitude",
                "year",
                "month",
                "value",
                "unit",
                "taxonomic_basis",
                "license",
                "reporting_note",
            ],
            location,
        )
        if row["record_id"] in record_ids:
            raise ValueError(f"{location}: duplicate record_id {row['record_id']!r}")
        record_ids.add(row["record_id"])
        if row["observation_type"] != "occurrence":
            raise ValueError(
                f"{location}: occurrence input must contain only observation_type='occurrence'"
            )
        if row["unit"] != "presence" or finite_float(row["value"], "value", location) != 1:
            raise ValueError(
                f"{location}: occurrence rows must remain presence-only value=1, unit=presence"
            )
        longitude = finite_float(row["longitude"], "longitude", location)
        latitude = finite_float(row["latitude"], "latitude", location)
        if not -180 <= longitude <= 180 or not -90 <= latitude <= 90:
            raise ValueError(f"{location}: coordinate is outside EPSG:4326 bounds")
        year = integer(row["year"], "year", location)
        month = integer(row["month"], "month", location)
        if not 1 <= month <= 12:
            raise ValueError(f"{location}: month must be 1-12")
        if not 1975 <= year <= 2024:
            raise ValueError(f"{location}: year must be in the reviewed 1975-2024 range")
        if row["sampling_effort"]:
            raise ValueError(
                f"{location}: occurrence sampling_effort must stay blank when no standardized effort was reported"
            )


def validate_trap_rows(rows: list[dict[str, str]], expected_rows: int) -> None:
    if expected_rows < 1:
        raise ValueError("--expected-trap-rows must be positive")
    if len(rows) != expected_rows:
        raise ValueError(
            f"Expected exactly {expected_rows} pooled trap rows; received {len(rows)}. "
            "Do not silently change the model-input design."
        )
    record_ids: set[str] = set()
    site_ids: set[str] = set()
    for row in rows:
        location = f"trap-abundance line {row['_line']}"
        require_text(
            row,
            [
                "record_id",
                "source_id",
                "observation_type",
                "species",
                "country",
                "site_id",
                "site_name",
                "site_type",
                "habitat",
                "cell_id",
                "longitude",
                "latitude",
                "source_coordinate",
                "collection_start",
                "collection_end",
                "collection_years",
                "active_months",
                "sampling_frequency",
                "trap_type",
                "trap_bait",
                "trap_start_time",
                "trap_end_time",
                "trap_hours_per_night",
                "trap_nights",
                "trap_hours",
                "value",
                "value_unit",
                "value_qualifier",
                "sex",
                "taxonomic_basis",
                "license",
                "source_url",
                "source_table",
                "reporting_note",
            ],
            location,
        )
        if row["record_id"] in record_ids:
            raise ValueError(f"{location}: duplicate record_id {row['record_id']!r}")
        record_ids.add(row["record_id"])
        if row["observation_type"] != "trap_abundance":
            raise ValueError(f"{location}: observation_type must be trap_abundance")
        if row["site_id"] in site_ids:
            raise ValueError(f"{location}: duplicate site_id {row['site_id']!r}")
        site_ids.add(row["site_id"])
        if row["collection_start"] != EXPECTED_COLLECTION_START:
            raise ValueError(f"{location}: collection_start is not the reviewed 2013 start")
        if row["collection_end"] != EXPECTED_COLLECTION_END:
            raise ValueError(f"{location}: collection_end is not the reviewed 2014 end")
        if row["collection_years"] != EXPECTED_COLLECTION_YEARS:
            raise ValueError(f"{location}: collection_years must be exactly 2013;2014")
        if row["active_months"] != EXPECTED_ACTIVE_MONTHS:
            raise ValueError(
                f"{location}: active_months must be exactly the April-November seasonal months"
            )
        if row["value_unit"] != EXPECTED_VALUE_UNIT:
            raise ValueError(
                f"{location}: value_unit must remain the published female trap-night index unit"
            )
        if row["sex"] != "female":
            raise ValueError(f"{location}: the imported index is female-specific")
        if not row["source_url"].startswith("https://"):
            raise ValueError(f"{location}: source_url must be HTTPS")
        note = row["reporting_note"].lower()
        qualifier = row["value_qualifier"].lower()
        if "not a reconstructed count" not in note:
            raise ValueError(
                f"{location}: reporting_note must state that raw counts were not reconstructed"
            )
        if "trap index" not in qualifier:
            raise ValueError(f"{location}: value_qualifier must identify a trap index")
        if "monthly" in note and "not" not in note:
            raise ValueError(f"{location}: monthly interpretation is not allowed for pooled rows")
        for forbidden in ("disease risk", "incidence"):
            if forbidden in note:
                raise ValueError(f"{location}: abundance rows must not be labeled {forbidden}")

        longitude = finite_float(row["longitude"], "longitude", location)
        latitude = finite_float(row["latitude"], "latitude", location)
        if not -180 <= longitude <= 180 or not -90 <= latitude <= 90:
            raise ValueError(f"{location}: coordinate is outside EPSG:4326 bounds")
        hours_per_night = finite_float(
            row["trap_hours_per_night"], "trap_hours_per_night", location
        )
        trap_nights = integer(row["trap_nights"], "trap_nights", location)
        trap_hours = finite_float(row["trap_hours"], "trap_hours", location)
        value = finite_float(row["value"], "value", location)
        if hours_per_night != EXPECTED_TRAP_HOURS_PER_NIGHT:
            raise ValueError(f"{location}: trap_hours_per_night must be 14")
        if trap_nights != EXPECTED_TRAP_NIGHTS_PER_ROW:
            raise ValueError(f"{location}: trap_nights must be 32 for each pooled row")
        if trap_hours != EXPECTED_TRAP_HOURS_PER_ROW:
            raise ValueError(f"{location}: trap_hours must be 448 for each pooled row")
        if not math.isclose(trap_hours, hours_per_night * trap_nights, abs_tol=1e-9):
            raise ValueError(f"{location}: trap_hours does not equal hours_per_night x trap_nights")
        if value < 0:
            raise ValueError(f"{location}: trap index value must be non-negative")


def occurrence_design_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    for row in rows:
        prepared = {field: row[field] for field in OCCURRENCE_COLUMNS}
        prepared.update(
            {
                "model_input_role": "presence_only_occurrence",
                "time_resolution": "monthly_presence_record",
                "aggregation_level": "source_record",
                "observation_denominator": "not_reported",
                "effort_hours": "",
                "count_semantics": "presence_only_not_count",
                "monthly_expansion": "not_applicable",
                "disease_endpoint": "not disease risk or incidence",
            }
        )
        output.append(prepared)
    return output


def trap_design_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    for row in rows:
        prepared = {field: row[field] for field in TRAP_ABUNDANCE_COLUMNS}
        prepared.update(
            {
                "model_input_role": "effort_aware_trap_index",
                "period_definition": EXPECTED_PERIOD_DEFINITION,
                "period_label": EXPECTED_PERIOD_LABEL,
                "time_resolution": "pooled_2013_2014_seasonal_windows",
                "aggregation_level": "site_pooled_2013_2014",
                "observation_denominator": "trap_nights",
                "effort_denominator": "trap_nights",
                "effort_hours": row["trap_hours"],
                "sampling_units": "trap-nights;trap-hours",
                "count_semantics": "source_reported_trap_index_not_raw_count",
                "monthly_expansion": "none",
                "disease_endpoint": "not disease risk or incidence",
            }
        )
        output.append(prepared)
    return output


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    occurrence_path = resolve_path(args.occurrences)
    trap_path = resolve_path(args.trap_abundance)
    output_dir = resolve_path(args.output_dir)
    if occurrence_path.resolve() == trap_path.resolve():
        raise ValueError("Occurrence and trap-abundance inputs must be separate files")

    occurrence_rows = read_csv(occurrence_path, OCCURRENCE_COLUMNS)
    trap_rows = read_csv(trap_path, TRAP_ABUNDANCE_COLUMNS)
    validate_occurrences(occurrence_rows)
    validate_trap_rows(trap_rows, args.expected_trap_rows)

    occurrence_output = output_dir / "aedes_occurrence_design_matrix.csv"
    trap_output = output_dir / "aedes_trap_abundance_design_matrix.csv"
    manifest_output = output_dir / "aedes_model_input_manifest.json"
    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(occurrence_output, OCCURRENCE_OUTPUT_COLUMNS, occurrence_design_rows(occurrence_rows))
    write_csv(trap_output, TRAP_OUTPUT_COLUMNS, trap_design_rows(trap_rows))

    total_trap_nights = sum(int(row["trap_nights"]) for row in trap_rows)
    total_trap_hours = sum(float(row["trap_hours"]) for row in trap_rows)
    manifest = {
        "generated_utc": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "status": "prepared_for_model_review",
        "purpose": (
            "Separate model-input design matrices for occurrence-only observations and "
            "effort-aware pooled ROK Aedes trap indices."
        ),
        "inputs": {
            "occurrences": {
                "path": str(occurrence_path),
                "sha256": sha256_file(occurrence_path),
                "n_rows": len(occurrence_rows),
                "observation_type": "occurrence",
            },
            "trap_abundance": {
                "path": str(trap_path),
                "sha256": sha256_file(trap_path),
                "sha256_basis": "source-reviewed six-row effort-aware import",
                "n_rows": len(trap_rows),
                "observation_type": "trap_abundance",
            },
        },
        "outputs": {
            "occurrence_design_matrix": {
                "path": str(occurrence_output),
                "sha256": sha256_file(occurrence_output),
                "n_rows": len(occurrence_rows),
                "fieldnames": OCCURRENCE_OUTPUT_COLUMNS,
            },
            "trap_abundance_design_matrix": {
                "path": str(trap_output),
                "sha256": sha256_file(trap_output),
                "n_rows": len(trap_rows),
                "fieldnames": TRAP_OUTPUT_COLUMNS,
            },
        },
        "design": {
            "observation_types_are_separate": True,
            "occurrence_rows_are_presence_only": True,
            "trap_rows_are_pooled": True,
            "trap_row_granularity": "one row per site over pooled 2013-2014 seasonal windows",
            "trap_period_definition": EXPECTED_PERIOD_DEFINITION,
            "trap_period_label": EXPECTED_PERIOD_LABEL,
            "trap_time_resolution": "pooled_2013_2014_seasonal_windows",
            "monthly_rows_created": 0,
            "raw_count_reconstruction": False,
            "trap_rows_have_explicit_effort": True,
            "trap_sites": len({row["site_id"] for row in trap_rows}),
            "trap_cells": len({row["cell_id"] for row in trap_rows}),
            "trap_nights_per_row": EXPECTED_TRAP_NIGHTS_PER_ROW,
            "trap_hours_per_row": EXPECTED_TRAP_HOURS_PER_ROW,
            "total_trap_nights": total_trap_nights,
            "total_trap_hours": total_trap_hours,
            "effort_denominator_field": "effort_denominator=trap_nights",
            "effort_hours_field": "effort_hours",
            "value_semantics": EXPECTED_VALUE_UNIT + "; source-reported index, not raw count",
        },
        "checks": {
            "six_pooled_rows_verified": len(trap_rows) == args.expected_trap_rows == 6,
            "all_trap_rows_share_documented_period": all(
                row["collection_years"] == EXPECTED_COLLECTION_YEARS for row in trap_rows
            ),
            "monthly_trap_expansion_absent": True,
            "raw_counts_not_reconstructed": True,
            "provenance_and_checksums_recorded": True,
        },
        "modeling_boundary": (
            "These are observation inputs. The trap value is a source-reported female "
            "trap index and requires a source-specific observation model. Outputs are "
            "not disease risk, incidence, prevalence, or a disease forecast."
        ),
        "builder": {
            "path": str(Path(__file__).resolve()),
            "sha256": sha256_file(Path(__file__).resolve()),
        },
    }
    manifest_output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": manifest["status"],
                "occurrence_rows": len(occurrence_rows),
                "pooled_trap_rows": len(trap_rows),
                "trap_sites": manifest["design"]["trap_sites"],
                "total_trap_nights": total_trap_nights,
                "total_trap_hours": total_trap_hours,
                "monthly_rows_created": 0,
                "raw_count_reconstruction": False,
                "output_dir": str(output_dir),
                "manifest": str(manifest_output),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
