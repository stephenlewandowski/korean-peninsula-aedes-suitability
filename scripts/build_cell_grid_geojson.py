#!/usr/bin/env python3
"""Build a scoped public 0.25-degree polygon grid used for external joins."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCOPE_SLUGS = {"korea": "korea_focus", "japan": "japan", "korea-japan": "korea_japan"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scope",
        choices=tuple(SCOPE_SLUGS),
        default="korea",
        help="Country scope used to select the matching suitability extract.",
    )
    parser.add_argument(
        "--cell-year",
        type=Path,
        default=None,
        help="Cell-year table; defaults to outputs/<scope slug>/tables/.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output GeoJSON; defaults to outputs/<scope slug>/<scope slug>_cell_grid.geojson.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    slug = SCOPE_SLUGS[args.scope]
    cell_year = args.cell_year or (
        PROJECT_ROOT / "outputs" / slug / "tables" / f"{slug}_cell_year_season.csv.gz"
    )
    output = args.output or PROJECT_ROOT / "outputs" / slug / f"{slug}_cell_grid.geojson"
    cells = pd.read_csv(
        cell_year,
        usecols=["country", "cell_id", "row_global", "col_global", "longitude", "latitude"],
    ).drop_duplicates("cell_id")
    if cells["cell_id"].duplicated().any():
        raise ValueError("Cell-year table maps a cell_id to multiple records")
    features = []
    half = 0.125
    for row in cells.to_dict("records"):
        lon = float(row["longitude"])
        lat = float(row["latitude"])
        ring = [
            [lon - half, lat - half],
            [lon + half, lat - half],
            [lon + half, lat + half],
            [lon - half, lat + half],
            [lon - half, lat - half],
        ]
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "cell_id": str(row["cell_id"]),
                    "country": str(row["country"]),
                    "row_global": int(row["row_global"]),
                    "col_global": int(row["col_global"]),
                    "longitude": lon,
                    "latitude": lat,
                },
                "geometry": {"type": "Polygon", "coordinates": [ring]},
            }
        )
    document = {"type": "FeatureCollection", "features": features}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    print({"scope": args.scope, "cells": len(features), "output": str(output)})


if __name__ == "__main__":
    main()
