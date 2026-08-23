#!/usr/bin/env python3
"""Audit the longitudinal ROK Anopheles sinensis validation table.

This audit intentionally separates a valid holdout *partition design* from a
completed predictive validation.  The assembled evidence is detection-only
and mixes occurrence records with specimen records, so no absence-based model
metric is calculated here.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path


TARGET_SPECIES = "Anopheles sinensis"
TARGET_COUNTRY = "South Korea"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def assign_group_folds(
    rows: list[dict[str, str]], group_field: str, n_folds: int
) -> dict[str, str]:
    """Assign complete groups to balanced deterministic folds."""

    group_counts = Counter(row[group_field] for row in rows)
    fold_rows = [0] * n_folds
    group_to_fold: dict[str, str] = {}
    ordered_groups = sorted(
        group_counts,
        key=lambda group: (-group_counts[group], group),
    )
    for group in ordered_groups:
        fold_index = min(range(n_folds), key=lambda index: (fold_rows[index], index))
        group_to_fold[group] = f"site_fold_{fold_index}"
        fold_rows[fold_index] += group_counts[group]
    return group_to_fold


def rename_fold_prefix(folds: dict[str, str], prefix: str) -> dict[str, str]:
    return {
        group: fold.replace("site_fold_", prefix, 1)
        for group, fold in folds.items()
    }


def partition_summary(
    rows: list[dict[str, str]],
    group_field: str,
    groups_to_partitions: dict[str, str],
    axis: str,
) -> list[dict[str, object]]:
    all_groups = set(groups_to_partitions)
    summary = []
    for partition in sorted(set(groups_to_partitions.values())):
        test_rows = [row for row in rows if groups_to_partitions[row[group_field]] == partition]
        train_rows = [row for row in rows if groups_to_partitions[row[group_field]] != partition]
        test_groups = {row[group_field] for row in test_rows}
        train_groups = {row[group_field] for row in train_rows}
        summary.append(
            {
                "validation_axis": axis,
                "holdout": partition,
                "train_rows": len(train_rows),
                "test_rows": len(test_rows),
                "train_groups": len(train_groups),
                "test_groups": len(test_groups),
                "group_overlap": len(train_groups & test_groups),
                "all_groups": len(all_groups),
                "predictive_metrics_eligible": False,
                "eligibility_note": (
                    "Presence-only evidence; no non-detection/effort-standardized "
                    "response is available for a predictive metric."
                ),
            }
        )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--observations",
        type=Path,
        default=Path("repo_patch/inputs/rok_anopheles_sinensis_pcr_observations.csv"),
    )
    parser.add_argument(
        "--longitudinal",
        type=Path,
        default=Path("repo_patch/inputs/rok_anopheles_sinensis_longitudinal_validation.csv"),
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("repo_patch"),
    )
    parser.add_argument("--spatial-folds", type=int, default=5)
    args = parser.parse_args()

    if args.spatial_folds < 2:
        raise SystemExit("--spatial-folds must be at least 2")

    rows = read_csv(args.observations)
    aggregate_rows = read_csv(args.longitudinal)
    if not rows:
        raise SystemExit("Observation table is empty")

    required_fields = [
        "record_id",
        "source_id",
        "species",
        "country",
        "site_id",
        "spatial_block_id",
        "longitude",
        "latitude",
        "year",
        "value",
        "sampling_effort",
        "taxonomic_basis",
        "pcr_confirmation_status",
        "presence_absence_status",
    ]
    missing_fields = {
        field: sum(not row.get(field, "").strip() for row in rows)
        for field in required_fields
    }
    duplicate_record_ids = len(rows) - len({row["record_id"] for row in rows})
    wrong_species_rows = sum(row["species"] != TARGET_SPECIES for row in rows)
    wrong_country_rows = sum(row["country"] != TARGET_COUNTRY for row in rows)
    missing_grid_cell_rows = sum(not row.get("cell_id", "").strip() for row in rows)
    absence_rows = sum(
        row.get("presence_absence_status", "").strip().lower()
        in {"not_detected", "non_detection", "non-detection", "absence", "negative"}
        for row in rows
    )
    effort_standardized_rows = 0
    molecular_status_counts = Counter(row["pcr_confirmation_status"] for row in rows)
    source_counts = Counter(row["source_id"] for row in rows)
    year_counts = Counter(int(row["year"]) for row in rows if row.get("year", "").isdigit())
    site_counts = Counter(row["site_id"] for row in rows)
    block_counts = Counter(row["spatial_block_id"] for row in rows)

    site_to_fold = assign_group_folds(rows, "site_id", args.spatial_folds)
    block_to_fold = rename_fold_prefix(
        assign_group_folds(rows, "spatial_block_id", args.spatial_folds),
        "block_fold_",
    )
    year_to_holdout = {
        str(year): f"year_holdout_{year}"
        for year in sorted(year_counts)
    }

    manifest_rows = []
    for row in rows:
        manifest_rows.append(
            {
                "record_id": row["record_id"],
                "source_id": row["source_id"],
                "year": row["year"],
                "site_id": row["site_id"],
                "spatial_block_id": row["spatial_block_id"],
                "cell_id": row.get("cell_id", ""),
                "longitude": row["longitude"],
                "latitude": row["latitude"],
                "site_holdout_fold": site_to_fold[row["site_id"]],
                "spatial_block_sensitivity_fold": block_to_fold[
                    row["spatial_block_id"]
                ],
                "temporal_holdout_year": year_to_holdout[row["year"]],
                "pcr_confirmation_status": row["pcr_confirmation_status"],
            }
        )

    site_summary = partition_summary(
        rows,
        "site_id",
        site_to_fold,
        "site_blocked_spatial",
    )
    block_summary = partition_summary(
        rows,
        "spatial_block_id",
        block_to_fold,
        "0p1deg_blocked_spatial_sensitivity",
    )
    temporal_summary = partition_summary(
        rows,
        "year",
        year_to_holdout,
        "year_blocked_temporal",
    )
    fold_summary = site_summary + block_summary + temporal_summary

    output_inputs = args.output_root / "inputs"
    output_metadata = args.output_root / "metadata"
    write_csv(
        output_inputs / "rok_anopheles_sinensis_validation_fold_manifest.csv",
        manifest_rows,
        list(manifest_rows[0]),
    )
    write_csv(
        output_inputs / "rok_anopheles_sinensis_validation_fold_summary.csv",
        fold_summary,
        list(fold_summary[0]),
    )

    site_overlap_max = max(row["group_overlap"] for row in site_summary)
    block_overlap_max = max(row["group_overlap"] for row in block_summary)
    temporal_overlap_max = max(row["group_overlap"] for row in temporal_summary)
    gate_reasons = []
    if absence_rows == 0:
        gate_reasons.append("No reviewed non-detection/absence rows are present.")
    if effort_standardized_rows == 0:
        gate_reasons.append("No response rows have a harmonized effort denominator.")
    if wrong_country_rows:
        gate_reasons.append("One or more rows fall outside the ROK country scope.")
    if wrong_species_rows:
        gate_reasons.append("One or more rows fall outside the target species scope.")
    if any(missing_fields.values()) or duplicate_record_ids:
        gate_reasons.append("The core observation schema contains missing or duplicate identifiers.")

    payload = {
        "generated_utc": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "target_species": TARGET_SPECIES,
        "country": TARGET_COUNTRY,
        "observation_table": str(args.observations),
        "longitudinal_table": str(args.longitudinal),
        "observation_rows": len(rows),
        "unique_sites": len(site_counts),
        "unique_spatial_blocks_0p1deg": len(block_counts),
        "direct_observation_years": sorted(year_counts),
        "source_counts": dict(sorted(source_counts.items())),
        "year_counts": dict(sorted(year_counts.items())),
        "molecular_status_counts": dict(sorted(molecular_status_counts.items())),
        "missing_required_fields": missing_fields,
        "duplicate_record_ids": duplicate_record_ids,
        "wrong_species_rows": wrong_species_rows,
        "wrong_country_rows": wrong_country_rows,
        "missing_grid_cell_rows": missing_grid_cell_rows,
        "absence_or_non_detection_rows": absence_rows,
        "effort_standardized_rows": effort_standardized_rows,
        "published_aggregate_context_rows": sum(
            "presence-only" not in row.get("validation_role", "").lower()
            for row in aggregate_rows
        ),
        "site_blocked_spatial": {
            "folds": args.spatial_folds,
            "group_field": "site_id",
            "group_overlap_max": site_overlap_max,
            "partitions_disjoint": site_overlap_max == 0,
            "predictive_metrics_eligible": False,
        },
        "0p1deg_blocked_spatial_sensitivity": {
            "folds": args.spatial_folds,
            "group_field": "spatial_block_id",
            "group_overlap_max": block_overlap_max,
            "partitions_disjoint": block_overlap_max == 0,
            "predictive_metrics_eligible": False,
        },
        "year_blocked_temporal": {
            "holdout_years": sorted(year_counts),
            "group_field": "year",
            "group_overlap_max": temporal_overlap_max,
            "partitions_disjoint": temporal_overlap_max == 0,
            "predictive_metrics_eligible": False,
        },
        "predictive_gate": {
            "status": "NOT_PASSED",
            "reasons": gate_reasons,
            "interpretation": (
                "The table is suitable for provenance review and construction of "
                "leakage-safe holdout partitions. It is not yet a presence/absence "
                "or effort-standardized response table for model performance metrics."
            ),
        },
        "outputs": {
            "fold_manifest": str(
                output_inputs / "rok_anopheles_sinensis_validation_fold_manifest.csv"
            ),
            "fold_summary": str(
                output_inputs / "rok_anopheles_sinensis_validation_fold_summary.csv"
            ),
        },
    }
    output_metadata.mkdir(parents=True, exist_ok=True)
    (output_metadata / "rok_anopheles_validation_structure.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
