#!/usr/bin/env python3
"""Audit exact joins to the current public 370-cell Korea grid.

Rows without a cell_id are retained as ROK observations but are excluded from
the grid-linked analysis cohort. No nearest-cell or boundary imputation is
performed.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from collections import Counter
from pathlib import Path


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--observations",
        type=Path,
        default=Path("repo_patch/inputs/rok_anopheles_sinensis_pcr_observations.csv"),
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("repo_patch"),
    )
    args = parser.parse_args()

    observations = read_csv(args.observations)
    audit_rows = []
    for row in observations:
        joined = bool(row.get("cell_id", "").strip())
        audit_rows.append(
            {
                "record_id": row["record_id"],
                "source_id": row["source_id"],
                "year": row["year"],
                "site_id": row["site_id"],
                "longitude": row["longitude"],
                "latitude": row["latitude"],
                "cell_id": row.get("cell_id", ""),
                "grid_join_status": "exact_polygon_join" if joined else "outside_current_370_cell_grid",
                "grid_linked_analysis_decision": "include" if joined else "exclude_without_imputation",
            }
        )

    joined_count = sum(row["grid_join_status"] == "exact_polygon_join" for row in audit_rows)
    excluded_count = len(audit_rows) - joined_count
    summary = {
        "generated_utc": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "observation_table": str(args.observations),
        "total_rows": len(audit_rows),
        "exact_grid_join_rows": joined_count,
        "outside_current_grid_rows": excluded_count,
        "grid_cell_count": 370,
        "policy": "Use exact polygon joins only; exclude non-intersecting records from grid-linked analysis and retain them in the ROK evidence table.",
        "nearest_cell_imputation": False,
        "source_counts": dict(Counter(row["source_id"] for row in audit_rows)),
        "year_counts_outside_grid": dict(
            Counter(row["year"] for row in audit_rows if row["grid_join_status"] != "exact_polygon_join")
        ),
    }
    output_inputs = args.output_root / "inputs"
    output_metadata = args.output_root / "metadata"
    write_csv(output_inputs / "rok_anopheles_sinensis_grid_join_audit.csv", audit_rows)
    output_metadata.mkdir(parents=True, exist_ok=True)
    (output_metadata / "rok_anopheles_grid_join_audit.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
