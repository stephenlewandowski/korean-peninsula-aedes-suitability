#!/usr/bin/env python3
"""Build a source-reviewed, effort-aware ROK Aedes trap-abundance table.

The source is Kim et al. (2018), doi:10.1111/1748-5967.12314. Tables 1,
2, and 4 report fixed sites, site-level effort, and female Aedes albopictus
trap indices for April-November 2013 and 2014. The output remains separate
from opportunistic occurrence records. Reported trap indices are preserved;
rounded indices are not reverse-engineered into specimen counts.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path

from build_rok_aedes_observations import (
    exact_cell_join,
    load_grid,
    resolve_path,
    sha256_file,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ID = "DOI:10.1111/1748-5967.12314"
SOURCE_URL = "https://doi.org/10.1111/1748-5967.12314"
SOURCE_LICENSE = "http://onlinelibrary.wiley.com/termsAndConditions#vor"
FIELDNAMES = [
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


# Manually transcribed from the version-of-record tables. DMS coordinates are
# retained verbatim and converted arithmetically to decimal degrees below.
SOURCE_ROWS = [
    {
        "site_id": "hapcheon_seosan_ri",
        "site_name": "Seosan-ri, Hapcheon",
        "site_type": "cow shed",
        "habitat": "rice paddies; 3 cows; no chemical control reported",
        "latitude_dms": (35, 34, 16.57, "N"),
        "longitude_dms": (128, 8, 43.38, "E"),
        "trap_index": 0.1,
    },
    {
        "site_id": "miryang_sannae_myeon",
        "site_name": "Sannae-myeon, Miryang",
        "site_type": "cow shed",
        "habitat": "rice paddies; 56 cows; no chemical control reported",
        "latitude_dms": (35, 33, 40.05, "N"),
        "longitude_dms": (128, 53, 6.14, "E"),
        "trap_index": 0.1,
    },
    {
        "site_id": "busan_daejeo_1",
        "site_name": "Daejeo-1-dong, Gangseo-gu, Busan",
        "site_type": "pigsty",
        "habitat": "rice paddies; 100 pigs; no chemical control reported",
        "latitude_dms": (35, 13, 28.05, "N"),
        "longitude_dms": (128, 56, 44.14, "E"),
        "trap_index": 0.9,
    },
    {
        "site_id": "busan_eulsukdo",
        "site_name": "Eulsukdo, Hadan-dong, Saha-gu, Busan",
        "site_type": "wild bird refuge",
        "habitat": "Nakdong estuary; no chemical control reported",
        "latitude_dms": (35, 6, 16.57, "N"),
        "longitude_dms": (128, 56, 45.56, "E"),
        "trap_index": 0.1,
    },
    {
        "site_id": "busan_cheonghak",
        "site_name": "Cheonghak-dong, Yeongdo-gu, Busan",
        "site_type": "downtown",
        "habitat": "markets; no chemical control reported",
        "latitude_dms": (35, 5, 47.81, "N"),
        "longitude_dms": (129, 3, 36.86, "E"),
        "trap_index": 0.3,
    },
    {
        "site_id": "busan_dongsam",
        "site_name": "Dongsam-dong, Yeongdo-gu, Busan",
        "site_type": "downtown",
        "habitat": "residential houses; no chemical control reported",
        "latitude_dms": (35, 3, 45.31, "N"),
        "longitude_dms": (129, 4, 51.69, "E"),
        "trap_index": 0.1,
    },
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "inputs" / "aedes_trap_abundance.csv",
    )
    parser.add_argument(
        "--grid",
        type=Path,
        default=PROJECT_ROOT / "outputs" / "korea_focus" / "korea_focus_cell_grid.geojson",
    )
    parser.add_argument(
        "--registry-output",
        type=Path,
        default=PROJECT_ROOT / "metadata" / "rok_aedes_trap_abundance_source_registry.json",
    )
    return parser.parse_args()


def dms_text(value: tuple[int, int, float, str]) -> str:
    degrees, minutes, seconds, hemisphere = value
    return f"{degrees}d{minutes:02d}m{seconds:05.2f}s{hemisphere}"


def dms_decimal(value: tuple[int, int, float, str]) -> float:
    degrees, minutes, seconds, hemisphere = value
    result = degrees + minutes / 60 + seconds / 3600
    return -result if hemisphere in {"S", "W"} else result


def build_rows(cells: list[dict[str, object]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for source in SOURCE_ROWS:
        latitude = dms_decimal(source["latitude_dms"])
        longitude = dms_decimal(source["longitude_dms"])
        cell_id = exact_cell_join(longitude, latitude, cells)
        site_id = str(source["site_id"])
        rows.append(
            {
                "record_id": f"kim2018_{site_id}_2013_2014",
                "source_id": SOURCE_ID,
                "observation_type": "trap_abundance",
                "species": "Aedes albopictus",
                "country": "South Korea",
                "site_id": site_id,
                "site_name": str(source["site_name"]),
                "site_type": str(source["site_type"]),
                "habitat": str(source["habitat"]),
                "cell_id": cell_id,
                "longitude": f"{longitude:.6f}",
                "latitude": f"{latitude:.6f}",
                "source_coordinate": (
                    f"{dms_text(source['latitude_dms'])};"
                    f"{dms_text(source['longitude_dms'])}"
                ),
                "collection_start": "2013-04-01",
                "collection_end": "2014-11-30",
                "collection_years": "2013;2014",
                "active_months": "04;05;06;07;08;09;10;11",
                "sampling_frequency": "one trap-night biweekly during active months",
                "trap_type": "SC-2000 black light trap; 6 W near-UV fluorescent lamp",
                "trap_bait": (
                    "none (dry ice was not used at cattle sheds)"
                    if source["site_type"] == "cow shed"
                    else "approximately 2 kg dry ice (CO2)"
                ),
                "trap_start_time": "19:00",
                "trap_end_time": "09:00",
                "trap_hours_per_night": "14",
                "trap_nights": "32",
                "trap_hours": "448",
                "value": f"{float(source['trap_index']):.1f}",
                "value_unit": "female mosquitoes per trap-night",
                "value_qualifier": "source-reported trap index rounded to 0.1",
                "sex": "female",
                "taxonomic_basis": (
                    "Source Table 4 Aedes albopictus row; adult specimens were "
                    "identified by the KCDC-coordinated surveillance centers"
                ),
                "license": SOURCE_LICENSE,
                "source_url": SOURCE_URL,
                "source_table": "Tables 1, 2, and 4; Materials and methods",
                "reporting_note": (
                    "Effort-aware relative abundance over two non-contiguous seasonal "
                    "windows (April-November 2013 and April-November 2014). Value is "
                    "the published female trap index, not a reconstructed count. "
                    "Keep separate from occurrence records and fit a source-specific "
                    "observation model before inference."
                ),
            }
        )
    return rows


def main() -> None:
    args = parse_args()
    output_path = resolve_path(args.output)
    grid_path = resolve_path(args.grid)
    registry_path = resolve_path(args.registry_output)
    cells = load_grid(grid_path)
    rows = build_rows(cells)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    registry = {
        "generated_utc": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "review_status": "source Tables 1, 2, and 4 reviewed; one source row withheld",
        "modeling_status": (
            "effort-aware trap-index validation input; source-specific observation "
            "model required; not disease risk or incidence"
        ),
        "source": {
            "title": (
                "Seasonal Prevalence of Mosquitoes Collected from Light Traps in "
                "Gyeongsangnam Province, Republic of Korea (2013-2014)"
            ),
            "doi": "10.1111/1748-5967.12314",
            "url": SOURCE_URL,
            "publisher": "Wiley / Entomological Society of Korea",
            "published_online": "2018-07-12",
            "license": SOURCE_LICENSE,
            "license_basis": "Crossref version-of-record license deposit",
            "funder": "Korea Centers for Disease Control & Prevention",
            "awards": ["2013-E5500200", "2013-E5500201"],
            "source_tables": ["Table 1", "Table 2", "Table 4", "Materials and methods"],
            "source_artifact_checksum": None,
            "source_artifact_checksum_note": (
                "No machine-readable source dataset was published; factual table values "
                "were manually transcribed from the version of record."
            ),
        },
        "effort_basis": {
            "active_periods": ["2013-04-01/2013-11-30", "2014-04-01/2014-11-30"],
            "frequency": "one trap-night biweekly",
            "hours_per_night": 14,
            "trap_nights_per_site_per_year": 16,
            "trap_nights_per_imported_row": 32,
            "trap_hours_per_imported_row": 448,
            "value_semantics": (
                "published mean female Aedes albopictus per trap-night, rounded to 0.1; "
                "raw specimen counts were not reconstructed"
            ),
        },
        "screening": {
            "published_site_rows": 7,
            "included_rows": len(rows),
            "excluded_rows": [
                {
                    "site": "Daejeo-2-dong, Gangseo-gu, Busan",
                    "published_value": "<0.1 female mosquitoes per trap-night",
                    "reason": (
                        "published longitude is internally inconsistent with the named "
                        "locality and the value is left-censored; neither field was corrected "
                        "or assigned a point estimate"
                    ),
                }
            ],
            "occurrence_rows_modified": False,
        },
        "grid": {
            "path": str(grid_path),
            "sha256": sha256_file(grid_path),
            "cell_count": len(cells),
            "join_policy": "exact point-in-polygon only",
        },
        "output": {
            "path": str(output_path),
            "sha256": sha256_file(output_path),
            "fieldnames": FIELDNAMES,
        },
        "builder": {
            "path": str(Path(__file__).resolve()),
            "sha256": sha256_file(Path(__file__).resolve()),
        },
    }
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "included_rows": len(rows),
                "excluded_source_rows": 1,
                "output": str(output_path),
                "registry": str(registry_path),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
