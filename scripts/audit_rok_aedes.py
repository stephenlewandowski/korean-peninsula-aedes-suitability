#!/usr/bin/env python3
"""Audit a public Republic of Korea Aedes observation table before modelling.

This is a data-readiness and observation-structure check. It does not fit a
species-distribution model and it does not merge occurrence records with trap
abundance. A populated input is required before any validation metric is
reported.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_COLUMNS = [
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
ALLOWED_OBSERVATION_TYPES = {"occurrence", "trap_presence", "trap_abundance"}
ALLOWED_SPECIES = {"Aedes aegypti", "Aedes albopictus"}
MODEL_YEAR_RANGE = (1975, 2024)
ROK_BOUNDS = {"longitude": (124.0, 132.5), "latitude": (33.0, 39.0)}
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
AUDIT_COLUMNS = [
    "source_id",
    "observation_type",
    "species",
    "country",
    "n_records",
    "n_with_coordinates",
    "n_with_collection_date",
    "n_with_collection_period",
    "n_with_cell_id",
    "n_with_sampling_effort",
    "n_with_trap_nights",
    "n_with_trap_hours",
    "n_censored",
    "observation_model_required",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--observations",
        type=Path,
        default=None,
        help="Populated observation CSV; omit to validate the empty schema template.",
    )
    parser.add_argument(
        "--template",
        type=Path,
        default=PROJECT_ROOT / "inputs" / "aedes_observations.template.csv",
    )
    parser.add_argument(
        "--trap-abundance",
        type=Path,
        default=None,
        help="Separate effort-aware trap-abundance CSV; never merged into occurrence rows.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "outputs" / "rok_aedes_validation",
    )
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != REQUIRED_COLUMNS:
            raise ValueError(
                f"{path} has an unexpected header. Expected exactly: {REQUIRED_COLUMNS}"
            )
        rows: list[dict[str, str]] = []
        for line_number, row in enumerate(reader, start=2):
            if None in row:
                raise ValueError(f"{path}:{line_number} has extra CSV fields")
            cleaned = {key: (value or "").strip() for key, value in row.items()}
            cleaned["_line"] = str(line_number)
            rows.append(cleaned)
    return rows


def read_trap_abundance_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != TRAP_ABUNDANCE_COLUMNS:
            raise ValueError(
                f"{path} has an unexpected trap-abundance header. "
                f"Expected exactly: {TRAP_ABUNDANCE_COLUMNS}"
            )
        rows: list[dict[str, str]] = []
        for line_number, row in enumerate(reader, start=2):
            if None in row:
                raise ValueError(f"{path}:{line_number} has extra CSV fields")
            cleaned = {key: (value or "").strip() for key, value in row.items()}
            cleaned["_line"] = str(line_number)
            rows.append(cleaned)
    return rows


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def optional_float(value: str, field: str, location: str, errors: list[str]) -> float | None:
    if not value:
        return None
    try:
        result = float(value)
    except ValueError:
        errors.append(f"{location}: {field} must be numeric")
        return None
    if not math.isfinite(result):
        errors.append(f"{location}: {field} must be finite")
        return None
    return result


def optional_int(value: str, field: str, location: str, errors: list[str]) -> int | None:
    if not value:
        return None
    try:
        result = int(value)
    except ValueError:
        errors.append(f"{location}: {field} must be an integer")
        return None
    return result


def audit_rows(rows: list[dict[str, str]]) -> tuple[list[dict[str, object]], list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    record_ids: set[str] = set()
    groups: Counter[tuple[str, str, str]] = Counter()
    audit: list[dict[str, object]] = []

    for row in rows:
        location = f"line {row['_line']}"
        record_id = row["record_id"]
        if not record_id:
            errors.append(f"{location}: record_id is required")
        elif record_id in record_ids:
            errors.append(f"{location}: duplicate record_id {record_id!r}")
        record_ids.add(record_id)

        source_id = row["source_id"]
        if not source_id:
            errors.append(f"{location}: source_id is required")
        observation_type = row["observation_type"]
        if observation_type not in ALLOWED_OBSERVATION_TYPES:
            errors.append(f"{location}: unsupported observation_type {observation_type!r}")
        species = row["species"]
        if species not in ALLOWED_SPECIES:
            errors.append(f"{location}: species must be one of {sorted(ALLOWED_SPECIES)}")
        if row["country"] != "South Korea":
            errors.append(
                f"{location}: country must be canonical 'South Korea'; DPRK rows are not accepted"
            )

        longitude = optional_float(row["longitude"], "longitude", location, errors)
        latitude = optional_float(row["latitude"], "latitude", location, errors)
        if longitude is None or latitude is None:
            errors.append(f"{location}: longitude and latitude are required")
        elif not (-180 <= longitude <= 180 and -90 <= latitude <= 90):
            errors.append(f"{location}: coordinate is outside EPSG:4326 bounds")
        elif not (
            ROK_BOUNDS["longitude"][0] <= longitude <= ROK_BOUNDS["longitude"][1]
            and ROK_BOUNDS["latitude"][0] <= latitude <= ROK_BOUNDS["latitude"][1]
        ):
            warnings.append(f"{location}: coordinate is outside the broad ROK review box")

        year = optional_int(row["year"], "year", location, errors)
        month = optional_int(row["month"], "month", location, errors)
        if year is None or month is None:
            errors.append(f"{location}: year and month are required for temporal holdouts")
        else:
            if not 1 <= month <= 12:
                errors.append(f"{location}: month must be 1–12")
            if not MODEL_YEAR_RANGE[0] <= year <= MODEL_YEAR_RANGE[1]:
                warnings.append(f"{location}: year is outside the 1975–2024 model period")

        collection_date = row["collection_date"]
        if collection_date:
            try:
                parsed_date = date.fromisoformat(collection_date)
            except ValueError:
                errors.append(f"{location}: collection_date must be ISO YYYY-MM-DD")
            else:
                if year is not None and parsed_date.year != year:
                    errors.append(f"{location}: collection_date year disagrees with year")
                if month is not None and parsed_date.month != month:
                    errors.append(f"{location}: collection_date month disagrees with month")

        value = optional_float(row["value"], "value", location, errors)
        if value is None:
            errors.append(f"{location}: value is required")
        elif value < 0:
            errors.append(f"{location}: value must be non-negative")
        effort = optional_float(row["sampling_effort"], "sampling_effort", location, errors)
        if observation_type in {"trap_presence", "trap_abundance"} and effort is None:
            errors.append(f"{location}: trap observations require sampling_effort")
        if not row["taxonomic_basis"]:
            errors.append(f"{location}: taxonomic_basis is required")
        if not row["license"]:
            errors.append(f"{location}: license is required")
        if not row["reporting_note"]:
            warnings.append(f"{location}: reporting_note is blank")

        if row["cell_id"]:
            joined_status = "cell_id_supplied"
        else:
            joined_status = "cell_id_missing_requires_spatial_join"
            warnings.append(f"{location}: cell_id is blank and requires a documented spatial join")
        groups[(source_id, observation_type, species)] += 1

    for (source_id, observation_type, species), count in sorted(groups.items()):
        group_rows = [
            row
            for row in rows
            if row["source_id"] == source_id
            and row["observation_type"] == observation_type
            and row["species"] == species
        ]
        audit.append(
            {
                "source_id": source_id,
                "observation_type": observation_type,
                "species": species,
                "country": "South Korea",
                "n_records": count,
                "n_with_coordinates": sum(bool(row["longitude"] and row["latitude"]) for row in group_rows),
                "n_with_collection_date": sum(bool(row["collection_date"]) for row in group_rows),
                "n_with_collection_period": 0,
                "n_with_cell_id": sum(bool(row["cell_id"]) for row in group_rows),
                "n_with_sampling_effort": sum(bool(row["sampling_effort"]) for row in group_rows),
                "n_with_trap_nights": 0,
                "n_with_trap_hours": 0,
                "n_censored": 0,
                "observation_model_required": observation_type == "trap_abundance",
            }
        )
    return audit, errors, warnings


def parse_time(value: str, field: str, location: str, errors: list[str]) -> int | None:
    try:
        parsed = datetime.strptime(value, "%H:%M")
    except ValueError:
        errors.append(f"{location}: {field} must be HH:MM")
        return None
    return parsed.hour * 60 + parsed.minute


def audit_trap_abundance_rows(
    rows: list[dict[str, str]], occurrence_record_ids: set[str]
) -> tuple[list[dict[str, object]], list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    record_ids: set[str] = set()
    groups: Counter[tuple[str, str, str]] = Counter()

    for row in rows:
        location = f"trap-abundance line {row['_line']}"
        record_id = row["record_id"]
        if not record_id:
            errors.append(f"{location}: record_id is required")
        elif record_id in record_ids or record_id in occurrence_record_ids:
            errors.append(f"{location}: duplicate or cross-file record_id {record_id!r}")
        record_ids.add(record_id)

        if row["observation_type"] != "trap_abundance":
            errors.append(f"{location}: observation_type must be 'trap_abundance'")
        if row["species"] not in ALLOWED_SPECIES:
            errors.append(f"{location}: unsupported species {row['species']!r}")
        if row["country"] != "South Korea":
            errors.append(f"{location}: country must be canonical 'South Korea'")
        for field in ["source_id", "site_id", "site_name", "site_type", "habitat"]:
            if not row[field]:
                errors.append(f"{location}: {field} is required")
        longitude = optional_float(row["longitude"], "longitude", location, errors)
        latitude = optional_float(row["latitude"], "latitude", location, errors)
        if longitude is None or latitude is None:
            errors.append(f"{location}: longitude and latitude are required")
        elif not (
            ROK_BOUNDS["longitude"][0] <= longitude <= ROK_BOUNDS["longitude"][1]
            and ROK_BOUNDS["latitude"][0] <= latitude <= ROK_BOUNDS["latitude"][1]
        ):
            errors.append(f"{location}: coordinate is outside the broad ROK review box")
        if not row["source_coordinate"]:
            errors.append(f"{location}: verbatim source_coordinate is required")

        collection_start: date | None = None
        collection_end: date | None = None
        try:
            collection_start = date.fromisoformat(row["collection_start"])
            collection_end = date.fromisoformat(row["collection_end"])
        except ValueError:
            errors.append(f"{location}: collection_start/end must be ISO YYYY-MM-DD")
        else:
            if collection_start > collection_end:
                errors.append(f"{location}: collection_start is after collection_end")
        years = row["collection_years"].split(";") if row["collection_years"] else []
        if not years or any(not value.isdigit() for value in years):
            errors.append(f"{location}: collection_years must be semicolon-separated years")
        elif collection_start is not None and collection_end is not None:
            declared_years = [int(value) for value in years]
            if min(declared_years) != collection_start.year or max(declared_years) != collection_end.year:
                errors.append(f"{location}: collection_years disagree with collection_start/end")
        months = row["active_months"].split(";") if row["active_months"] else []
        if not months or any(not value.isdigit() or not 1 <= int(value) <= 12 for value in months):
            errors.append(f"{location}: active_months must be semicolon-separated months 01-12")
        elif collection_start is not None and collection_end is not None:
            declared_months = [int(value) for value in months]
            if collection_start.month not in declared_months or collection_end.month not in declared_months:
                errors.append(f"{location}: active_months disagree with collection_start/end")
        if not row["sampling_frequency"]:
            errors.append(f"{location}: sampling_frequency is required")

        start_minutes = parse_time(row["trap_start_time"], "trap_start_time", location, errors)
        end_minutes = parse_time(row["trap_end_time"], "trap_end_time", location, errors)
        hours_per_night = optional_float(
            row["trap_hours_per_night"], "trap_hours_per_night", location, errors
        )
        trap_nights = optional_int(row["trap_nights"], "trap_nights", location, errors)
        trap_hours = optional_float(row["trap_hours"], "trap_hours", location, errors)
        if start_minutes is not None and end_minutes is not None and hours_per_night is not None:
            elapsed_hours = ((end_minutes - start_minutes) % (24 * 60)) / 60
            if not math.isclose(elapsed_hours, hours_per_night, abs_tol=1e-9):
                errors.append(f"{location}: trap times do not reconcile with trap_hours_per_night")
        if hours_per_night is None or hours_per_night <= 0:
            errors.append(f"{location}: trap_hours_per_night must be positive")
        if trap_nights is None or trap_nights <= 0:
            errors.append(f"{location}: trap_nights must be a positive integer")
        if trap_hours is None or trap_hours <= 0:
            errors.append(f"{location}: trap_hours must be positive")
        if hours_per_night and trap_nights and trap_hours is not None and not math.isclose(
            trap_hours, hours_per_night * trap_nights, abs_tol=1e-9
        ):
            errors.append(f"{location}: trap_hours does not equal nights x hours_per_night")

        value = optional_float(row["value"], "value", location, errors)
        if value is None or value < 0:
            errors.append(f"{location}: value must be finite and non-negative")
        if row["value_unit"] != "female mosquitoes per trap-night":
            errors.append(f"{location}: value_unit must preserve the published trap-index unit")
        for field in [
            "trap_type",
            "trap_bait",
            "value_qualifier",
            "sex",
            "taxonomic_basis",
            "license",
            "source_url",
            "source_table",
            "reporting_note",
        ]:
            if not row[field]:
                errors.append(f"{location}: {field} is required")
        if row["sex"] != "female":
            errors.append(f"{location}: source trap index applies to female mosquitoes")
        if not row["source_url"].startswith("https://"):
            errors.append(f"{location}: source_url must be HTTPS")
        note_lower = row["reporting_note"].lower()
        if "disease risk" in note_lower or "incidence" in note_lower:
            errors.append(f"{location}: reporting_note must not label abundance as disease risk/incidence")
        if row["cell_id"] == "":
            warnings.append(f"{location}: cell_id is blank after exact spatial join")
        groups[(row["source_id"], row["observation_type"], row["species"])] += 1

    audit: list[dict[str, object]] = []
    for (source_id, observation_type, species), count in sorted(groups.items()):
        group_rows = [
            row
            for row in rows
            if row["source_id"] == source_id
            and row["observation_type"] == observation_type
            and row["species"] == species
        ]
        audit.append(
            {
                "source_id": source_id,
                "observation_type": observation_type,
                "species": species,
                "country": "South Korea",
                "n_records": count,
                "n_with_coordinates": sum(bool(row["longitude"] and row["latitude"]) for row in group_rows),
                "n_with_collection_date": 0,
                "n_with_collection_period": sum(bool(row["collection_start"] and row["collection_end"]) for row in group_rows),
                "n_with_cell_id": sum(bool(row["cell_id"]) for row in group_rows),
                "n_with_sampling_effort": sum(bool(row["trap_nights"] and row["trap_hours"]) for row in group_rows),
                "n_with_trap_nights": sum(bool(row["trap_nights"]) for row in group_rows),
                "n_with_trap_hours": sum(bool(row["trap_hours"]) for row in group_rows),
                "n_censored": sum(
                    row["value_qualifier"].lstrip().startswith("<")
                    or "censor" in row["value_qualifier"].lower()
                    for row in group_rows
                ),
                "observation_model_required": True,
            }
        )
    return audit, errors, warnings


def main() -> None:
    args = parse_args()
    if not args.template.exists():
        raise FileNotFoundError(f"Missing schema template: {args.template}")
    read_csv(args.template)

    observation_path = args.observations
    rows = read_csv(observation_path) if observation_path else []
    audit, errors, warnings = audit_rows(rows)
    trap_path = args.trap_abundance
    if observation_path and trap_path and observation_path.resolve() == trap_path.resolve():
        raise ValueError("Occurrence and trap-abundance inputs must be separate files")
    trap_rows = read_trap_abundance_csv(trap_path) if trap_path else []
    trap_audit, trap_errors, trap_warnings = audit_trap_abundance_rows(
        trap_rows, {row["record_id"] for row in rows}
    )
    audit.extend(trap_audit)
    errors.extend(trap_errors)
    warnings.extend(trap_warnings)
    if errors:
        raise ValueError("ROK Aedes observation audit failed:\n" + "\n".join(errors[:30]))

    args.output_dir.mkdir(parents=True, exist_ok=True)
    with (args.output_dir / "rok_aedes_observation_audit.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=AUDIT_COLUMNS)
        writer.writeheader()
        writer.writerows(audit)

    metadata = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "schema_checked_no_observations_supplied" if not rows and not trap_rows else "ready_for_model_review",
        "template": str(args.template),
        "observations": str(observation_path) if observation_path else None,
        "trap_abundance": str(trap_path) if trap_path else None,
        "n_records": len(rows) + len(trap_rows),
        "n_occurrence_records": len(rows),
        "n_trap_abundance_records": len(trap_rows),
        "n_groups": len(audit),
        "warnings": warnings,
        "input_sha256": {
            "observations": sha256_file(observation_path) if observation_path else None,
            "trap_abundance": sha256_file(trap_path) if trap_path else None,
        },
        "interpretation_boundary": "This audit is not a fitted model, validation score, abundance estimate, disease forecast, or DPRK assessment.",
        "observation_types_are_separate": True,
        "trap_abundance_value_semantics": (
            "Source-reported female mosquitoes per trap-night; not reconstructed raw counts, "
            "occurrence, disease risk, or incidence."
        ),
    }
    (args.output_dir / "rok_aedes_observation_audit_metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": metadata["status"],
                "n_records": len(rows) + len(trap_rows),
                "n_occurrence_records": len(rows),
                "n_trap_abundance_records": len(trap_rows),
                "n_groups": len(audit),
            }
        )
    )


if __name__ == "__main__":
    main()
