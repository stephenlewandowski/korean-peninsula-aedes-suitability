#!/usr/bin/env python3
"""Build a reviewed ROK Aedes occurrence table from a pinned GBIF query.

The importer keeps presence-only records separate from trap observations. It
requires an accepted target taxon, South Korea country code, coordinates,
documented year/month, PRESENT status, and a source license. Records with
year-only dates are excluded rather than assigned a fabricated month.
Sampling effort remains blank because these occurrence records do not report a
standardized effort denominator.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GBIF_SEARCH_URL = "https://api.gbif.org/v1/occurrence/search"
GBIF_DATASET_URL = "https://api.gbif.org/v1/dataset/"
TARGET_SPECIES = "Aedes albopictus"
TARGET_COUNTRY = "South Korea"
TARGET_COUNTRY_CODE = "KR"
YEAR_RANGE = (1975, 2024)
ROK_BOUNDS = {"longitude": (124.0, 132.5), "latitude": (33.0, 39.0)}
FIELDNAMES = [
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "inputs" / "aedes_observations.csv",
    )
    parser.add_argument(
        "--grid",
        type=Path,
        default=PROJECT_ROOT / "outputs" / "korea_focus" / "korea_focus_cell_grid.geojson",
        help="Public Korea grid used for an exact point-in-polygon cell join.",
    )
    parser.add_argument(
        "--registry-output",
        type=Path,
        default=PROJECT_ROOT / "metadata" / "rok_aedes_source_registry.json",
    )
    parser.add_argument("--page-size", type=int, default=300)
    return parser.parse_args()


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else PROJECT_ROOT / path


def fetch_json(url: str) -> dict[str, Any]:
    request = Request(url, headers={"User-Agent": "korean-peninsula-aedes-suitability/1.0"})
    with urlopen(request, timeout=120) as response:
        return json.load(response)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def point_in_ring(longitude: float, latitude: float, ring: list[list[float]]) -> bool:
    inside = False
    for index, (x2, y2) in enumerate(ring):
        x1, y1 = ring[index - 1]
        if ((y1 > latitude) != (y2 > latitude)) and (
            longitude < (x2 - x1) * (latitude - y1) / (y2 - y1) + x1
        ):
            inside = not inside
    return inside


def point_in_geometry(longitude: float, latitude: float, geometry: dict[str, Any]) -> bool:
    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates", [])
    polygons = coordinates if geometry_type == "MultiPolygon" else [coordinates]
    for polygon in polygons:
        if not polygon:
            continue
        if point_in_ring(longitude, latitude, polygon[0]) and not any(
            point_in_ring(longitude, latitude, hole) for hole in polygon[1:]
        ):
            return True
    return False


def load_grid(path: Path) -> list[dict[str, Any]]:
    document = json.loads(path.read_text(encoding="utf-8"))
    features = document.get("features", [])
    cells = []
    for feature in features:
        cell_id = feature.get("properties", {}).get("cell_id")
        geometry = feature.get("geometry")
        if cell_id and geometry:
            cells.append({"cell_id": str(cell_id), "geometry": geometry})
    if not cells:
        raise ValueError(f"Grid has no usable cell features: {path}")
    return cells


def exact_cell_join(longitude: float, latitude: float, cells: list[dict[str, Any]]) -> str:
    matches = [
        cell["cell_id"]
        for cell in cells
        if point_in_geometry(longitude, latitude, cell["geometry"])
    ]
    if len(matches) > 1:
        raise ValueError(f"Coordinate intersects multiple grid cells: {longitude}, {latitude}")
    return matches[0] if matches else ""


def parse_event_date(record: dict[str, Any], year: int, month: int) -> tuple[str, str]:
    event_date = str(record.get("eventDate", "")).strip()
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})", event_date)
    if match:
        date_text = match.group(0)
        if int(match.group(1)) == year and int(match.group(2)) == month:
            return date_text, "day"
    return "", "month"


def dataset_metadata(dataset_key: str) -> dict[str, Any]:
    return fetch_json(GBIF_DATASET_URL + dataset_key)


def build_query(page_size: int, offset: int) -> str:
    params = {
        "scientificName": TARGET_SPECIES,
        "country": TARGET_COUNTRY_CODE,
        "hasCoordinate": "true",
        "occurrenceStatus": "PRESENT",
        "year": f"{YEAR_RANGE[0]},{YEAR_RANGE[1]}",
        "limit": page_size,
        "offset": offset,
    }
    return GBIF_SEARCH_URL + "?" + urlencode(params)


def fetch_occurrences(page_size: int) -> tuple[list[dict[str, Any]], str]:
    first_url = build_query(page_size, 0)
    first_page = fetch_json(first_url)
    total = int(first_page.get("count", 0))
    results = list(first_page.get("results", []))
    if total > page_size:
        for offset in range(page_size, total, page_size):
            results.extend(fetch_json(build_query(page_size, offset)).get("results", []))
    if len(results) != total:
        raise ValueError(f"GBIF result count mismatch: API={total}, retrieved={len(results)}")
    return results, first_url


def make_row(
    record: dict[str, Any],
    source: dict[str, Any],
    cells: list[dict[str, Any]],
) -> dict[str, str] | None:
    accepted = str(record.get("acceptedScientificName") or record.get("scientificName") or "")
    if not accepted.startswith(TARGET_SPECIES):
        return None
    if str(record.get("countryCode", "")).upper() != TARGET_COUNTRY_CODE:
        return None
    if str(record.get("occurrenceStatus", "")).upper() != "PRESENT":
        return None
    if str(record.get("basisOfRecord", "")).upper() != "HUMAN_OBSERVATION":
        return None
    year = parse_int(record.get("year"))
    month = parse_int(record.get("month"))
    longitude = parse_float(record.get("decimalLongitude"))
    latitude = parse_float(record.get("decimalLatitude"))
    license_url = str(record.get("license", "")).strip()
    key = str(record.get("key", "")).strip()
    occurrence_id = str(record.get("occurrenceID", "")).strip()
    if year is None or month is None or not 1 <= month <= 12:
        return None
    if not YEAR_RANGE[0] <= year <= YEAR_RANGE[1]:
        return None
    if longitude is None or latitude is None:
        return None
    if not (
        ROK_BOUNDS["longitude"][0] <= longitude <= ROK_BOUNDS["longitude"][1]
        and ROK_BOUNDS["latitude"][0] <= latitude <= ROK_BOUNDS["latitude"][1]
    ):
        return None
    if not key or not occurrence_id or not license_url:
        return None
    collection_date, date_precision = parse_event_date(record, year, month)
    dataset_key = str(record.get("datasetKey", "")).strip()
    dataset_title = str(source.get("title") or record.get("datasetName") or dataset_key).strip()
    identified_by = str(record.get("identifiedBy", "")).strip() or "not reported"
    recorded_by = str(record.get("recordedBy", "")).strip() or "not reported"
    locality = str(record.get("locality", "")).strip() or "not reported"
    cell_id = exact_cell_join(longitude, latitude, cells)
    join_note = cell_id or "no exact cell intersection"
    reporting_note = (
        f"GBIF occurrence key={key}; occurrenceID={occurrence_id}; "
        f"datasetKey={dataset_key}; datasetTitle={dataset_title}; "
        f"occurrenceStatus=PRESENT; basisOfRecord=HUMAN_OBSERVATION; "
        f"identifiedBy={identified_by}; recordedBy={recorded_by}; locality={locality}; "
        f"exact_grid_join={join_note}; sampling effort not reported; "
        "occurrence-only presence record; not a trap-abundance denominator."
    )
    taxonomic_basis = (
        f"GBIF acceptedScientificName={accepted}; "
        "source-reported human observation; GBIF taxon and occurrence fields screened"
    )
    return {
        "record_id": f"gbif_{key}",
        "source_id": f"GBIF:{dataset_key}",
        "observation_type": "occurrence",
        "species": TARGET_SPECIES,
        "country": TARGET_COUNTRY,
        "geography": TARGET_COUNTRY,
        "cell_id": cell_id,
        "longitude": f"{longitude:.6f}",
        "latitude": f"{latitude:.6f}",
        "collection_date": collection_date,
        "date_precision": date_precision,
        "year": str(year),
        "month": str(month),
        "value": "1",
        "unit": "presence",
        "sampling_effort": "",
        "taxonomic_basis": taxonomic_basis,
        "license": license_url,
        "reporting_note": reporting_note,
    }


def main() -> None:
    args = parse_args()
    output_path = resolve_path(args.output)
    grid_path = resolve_path(args.grid)
    registry_path = resolve_path(args.registry_output)
    cells = load_grid(grid_path)
    raw_records, query_url = fetch_occurrences(args.page_size)
    dataset_keys = sorted({str(record.get("datasetKey", "")) for record in raw_records if record.get("datasetKey")})
    sources = {key: dataset_metadata(key) for key in dataset_keys}
    rows = []
    exclusion_reasons: dict[str, int] = {}
    for record in raw_records:
        before = len(rows)
        source = sources.get(str(record.get("datasetKey", "")), {})
        row = make_row(record, source, cells)
        if row is not None:
            rows.append(row)
        elif len(rows) == before:
            reason = "missing_month_or_required_source_field_or_screen_failure"
            exclusion_reasons[reason] = exclusion_reasons.get(reason, 0) + 1
    rows.sort(key=lambda row: (int(row["year"]), int(row["month"]), row["record_id"]))
    if not rows:
        raise ValueError("No reviewed GBIF occurrence rows passed the import screen")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    registry = {
        "generated_utc": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "review_status": "source_fields_reviewed_for_taxon_country_coordinate_date_license",
        "modeling_status": "occurrence_only; human scientific review remains required before model fitting",
        "target_species": TARGET_SPECIES,
        "target_country": TARGET_COUNTRY,
        "query_url": query_url,
        "query_policy": {
            "accepted_taxon_prefix": TARGET_SPECIES,
            "country_code": TARGET_COUNTRY_CODE,
            "occurrence_status": "PRESENT",
            "basis_of_record": "HUMAN_OBSERVATION",
            "requires_coordinate": True,
            "requires_year_and_month": True,
            "year_range": list(YEAR_RANGE),
            "rok_coordinate_bounds": ROK_BOUNDS,
            "sampling_effort_policy": "blank for occurrence records when the source does not report a standardized effort denominator",
            "year_only_policy": "exclude; do not fabricate month or date precision",
        },
        "raw_api_records": len(raw_records),
        "included_rows": len(rows),
        "excluded_records": len(raw_records) - len(rows),
        "exclusion_reasons": exclusion_reasons,
        "grid": {
            "path": str(grid_path),
            "cell_count": len(cells),
            "join_policy": "exact point-in-polygon only; blank cell_id means no exact intersection",
        },
        "sources": {
            key: {
                "title": value.get("title"),
                "description": value.get("description"),
                "license": value.get("license"),
                "homepage": value.get("homepage"),
                "gbif_dataset_url": GBIF_DATASET_URL + key,
            }
            for key, value in sources.items()
        },
        "output": {
            "path": str(output_path),
            "sha256": sha256_file(output_path),
            "fieldnames": FIELDNAMES,
        },
    }
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"included_rows": len(rows), "excluded_records": len(raw_records) - len(rows), "output": str(output_path), "registry": str(registry_path)}, indent=2))


if __name__ == "__main__":
    main()
