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
                "n_with_cell_id": sum(bool(row["cell_id"]) for row in group_rows),
                "n_with_sampling_effort": sum(bool(row["sampling_effort"]) for row in group_rows),
                "observation_model_required": observation_type == "trap_abundance",
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
    if errors:
        raise ValueError("ROK Aedes observation audit failed:\n" + "\n".join(errors[:30]))

    args.output_dir.mkdir(parents=True, exist_ok=True)
    with (args.output_dir / "rok_aedes_observation_audit.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(audit[0]) if audit else [
            "source_id",
            "observation_type",
            "species",
            "country",
            "n_records",
            "n_with_coordinates",
            "n_with_collection_date",
            "n_with_cell_id",
            "n_with_sampling_effort",
            "observation_model_required",
        ])
        writer.writeheader()
        writer.writerows(audit)

    metadata = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "schema_checked_no_observations_supplied" if not rows else "ready_for_model_review",
        "template": str(args.template),
        "observations": str(observation_path) if observation_path else None,
        "n_records": len(rows),
        "n_groups": len(audit),
        "warnings": warnings,
        "interpretation_boundary": "This audit is not a fitted model, validation score, abundance estimate, disease forecast, or DPRK assessment.",
        "observation_types_are_separate": True,
    }
    (args.output_dir / "rok_aedes_observation_audit_metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"status": metadata["status"], "n_records": len(rows), "n_groups": len(audit)}))


if __name__ == "__main__":
    main()
