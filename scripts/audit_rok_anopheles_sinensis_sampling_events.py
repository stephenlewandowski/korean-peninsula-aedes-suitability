#!/usr/bin/env python3
"""Validate the reviewed Anopheles sampling-event input contract.

The repository currently has positive molecular evidence but does not have a
reviewed event-level table with documented non-detections and harmonized
effort. This script makes that missing-input gate explicit and never creates
zeros from absent records.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path


REQUIRED_FIELDS = [
    "sampling_event_id",
    "source_id",
    "site_id",
    "country",
    "longitude",
    "latitude",
    "collection_date",
    "year",
    "collection_method",
    "sampling_effort",
    "effort_unit",
    "total_anopheles",
    "target_detected",
    "target_count",
    "taxonomic_basis",
    "non_detection_basis",
    "source_url",
    "review_status",
]


def read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return reader.fieldnames or [], list(reader)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--events",
        type=Path,
        default=Path("repo_patch/inputs/rok_anopheles_sinensis_sampling_events.csv"),
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("repo_patch"),
    )
    args = parser.parse_args()

    output_metadata = args.output_root / "metadata"
    output_metadata.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] = {
        "generated_utc": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "events_path": str(args.events),
        "required_fields": REQUIRED_FIELDS,
        "status": "BLOCKED_MISSING_REVIEWED_EVENT_TABLE",
        "rows": 0,
        "duplicate_event_ids": 0,
        "missing_required_field_counts": {},
        "non_detection_rows": 0,
        "detection_rows": 0,
        "effort_standardized_rows": 0,
        "zero_inference_performed": False,
        "notes": [
            "The template is intentionally header-only.",
            "Do not convert missing observations into non-detections.",
            "Do not pool occurrence records with trap-abundance records without an observation model.",
        ],
    }

    if not args.events.exists():
        payload["notes"].append("Populate the reviewed event table before running predictive validation.")
    else:
        fields, rows = read_rows(args.events)
        missing_fields = [field for field in REQUIRED_FIELDS if field not in fields]
        payload["rows"] = len(rows)
        payload["missing_required_field_counts"] = {
            field: sum(not row.get(field, "").strip() for row in rows)
            for field in REQUIRED_FIELDS
            if field in fields
        }
        payload["missing_columns"] = missing_fields
        payload["duplicate_event_ids"] = len(rows) - len(
            {row.get("sampling_event_id", "") for row in rows}
        )
        payload["non_detection_rows"] = sum(
            row.get("target_detected", "").strip().lower()
            in {"0", "false", "no", "not_detected", "non-detection"}
            for row in rows
        )
        payload["detection_rows"] = sum(
            row.get("target_detected", "").strip().lower()
            in {"1", "true", "yes", "detected", "presence"}
            for row in rows
        )
        payload["effort_standardized_rows"] = sum(
            bool(row.get("sampling_effort", "").strip())
            and bool(row.get("effort_unit", "").strip())
            for row in rows
        )
        if missing_fields:
            payload["status"] = "FAIL_SCHEMA"
        elif not rows:
            payload["status"] = "BLOCKED_EMPTY_EVENT_TABLE"
        elif payload["non_detection_rows"] == 0:
            payload["status"] = "BLOCKED_NO_REVIEWED_NON_DETECTIONS"
        elif payload["effort_standardized_rows"] < len(rows):
            payload["status"] = "BLOCKED_INCOMPLETE_EFFORT_STANDARDIZATION"
        else:
            payload["status"] = "READY_FOR_REVIEW"

    output_path = output_metadata / "rok_anopheles_sampling_event_audit.json"
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
