#!/usr/bin/env python3
"""Build the reviewed ROK Anopheles sinensis PCR evidence tables.

The builder deliberately keeps three evidence classes separate:

1. Molecular occurrence records from the public MosquitoMap/VectorMap layer.
2. Individual molecular records extracted from published supplementary tables.
3. Published site-period or study aggregates for which individual rows are not
   publicly available in the cited article.

No absence is inferred from a missing record.  The resulting tables are
therefore suitable for a provenance and holdout-structure audit, but are not
by themselves a presence/absence training set.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import re
import urllib.parse
import urllib.request
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from xml.etree import ElementTree


ARCGIS_LAYER = (
    "https://services2.arcgis.com/HRY6x8qt5qjGnAA9/arcgis/rest/services/"
    "MosquitoMap2/FeatureServer/0"
)
ARCGIS_QUERY = ARCGIS_LAYER + "/query"
ARCGIS_EXPERIENCE = (
    "https://experience.arcgis.com/experience/5f95c3edfbea4634b8347fec0bd1dcd6"
)

HONG_2023_DOCX = (
    "https://media.springernature.com/original/springer-static/esm/"
    "art%3A10.1186%2Fs12936-023-04821-x/MediaObjects/"
    "12936_2023_4821_MOESM1_ESM.docx"
)
JEON_2024_DOCX = (
    "https://media.springernature.com/original/springer-static/esm/"
    "art%3A10.1038%2Fs41598-025-29307-5/MediaObjects/"
    "41598_2025_29307_MOESM1_ESM.docx"
)

TARGET_SPECIES = "Anopheles sinensis"
COUNTRY = "South Korea"

ARCGIS_FIELDS = ",".join(
    [
        "OBJECTID",
        "Sequence",
        "ScientificName",
        "Species",
        "Country",
        "StateProvince",
        "County",
        "Locality",
        "Source",
        "RelatedInformation",
        "IdentificationMethod",
        "IdentificationConfidence",
        "IdentificationRemarks",
        "IdentifiedBy",
        "VerbatimCollectingDate",
        "EarliestDateCollected",
        "LatestDateCollected",
        "EarliestYearCollected",
        "EarliestMonthCollected",
        "DecimalLatitude",
        "DecimalLongitude",
        "CoordinateUncertaintyInMeters",
        "IndividualCount",
        "Sex",
        "LifeStage",
        "CollectingMethod",
        "CollectingEffortInHours",
        "GenBankNum",
        "GlobalUniqueIdentifier",
        "BasisOfRecord",
        "CatalogNumber",
    ]
)

SITE_COORDINATES = {
    # Hong et al. 2023: DMS converted to decimal degrees.
    "WG": (37.745000, 126.534444),  # Wolgot-myeon, Gimpo
    "NG": (37.731111, 126.415278),  # Naega-myeon, Ganghwa
    # Jeon et al. 2025: DMS converted to decimal degrees.
    "KH": (37.743444, 126.459417),  # Kukhwa-ri, Ganghwa
    "SH": (37.730694, 126.452639),  # Seonhaeng-ri, Ganghwa
}

SITE_NAMES = {
    "WG": "Wolgot-myeon, Gimpo-si, Gyeonggi-do",
    "NG": "Naega-myeon, Ganghwa-gun, Incheon",
    "KH": "Kukhwa-ri, Ganghwa-gun, Incheon",
    "SH": "Seonhaeng-ri, Ganghwa-gun, Incheon",
}


def fetch_json(url: str, params: dict[str, str]) -> dict:
    request_url = url + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(
        request_url,
        headers={"User-Agent": "climademic-korea-research/1.0"},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_bytes(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "climademic-korea-research/1.0"},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def fetch_arcgis_records() -> list[dict]:
    """Fetch all target molecular records from the public feature service."""

    where = (
        "Species = 'sinensis' AND Country LIKE '%Korea%' "
        "AND IdentificationMethod = 'DNA'"
    )
    rows: list[dict] = []
    offset = 0
    while True:
        payload = fetch_json(
            ARCGIS_QUERY,
            {
                "where": where,
                "outFields": ARCGIS_FIELDS,
                "returnGeometry": "false",
                "resultOffset": str(offset),
                "resultRecordCount": "2000",
                "orderByFields": "OBJECTID",
                "f": "json",
            },
        )
        features = payload.get("features", [])
        rows.extend(feature["attributes"] for feature in features)
        if len(features) < 2000 or not payload.get("exceededTransferLimit"):
            break
        offset += len(features)
    return rows


def text_or_blank(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"no data", "none", "null", "nd", "-"}:
        return ""
    return text


def parse_int(value: object) -> int | None:
    text = text_or_blank(value)
    if not text:
        return None
    match = re.fullmatch(r"\d+", text)
    return int(match.group(0)) if match else None


def parse_float(value: object) -> float | None:
    text = text_or_blank(value)
    if not text:
        return None
    try:
        result = float(text)
    except ValueError:
        return None
    return result if math.isfinite(result) else None


def normalize_date(value: object) -> str:
    text = text_or_blank(value)
    if not text:
        return ""
    match = re.search(r"(\d{4})[./-](\d{1,2})[./-](\d{1,2})", text)
    if not match:
        match = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", text)
        if match:
            month, day, year = map(int, match.groups())
        else:
            return ""
    else:
        year, month, day = map(int, match.groups())
    try:
        return dt.date(year, month, day).isoformat()
    except ValueError:
        return ""


def year_from_date(date_text: str) -> int | None:
    if not date_text:
        return None
    return int(date_text[:4])


def canonical_province(value: object) -> str:
    text = text_or_blank(value)
    replacements = {
        "Geonggi-do": "Gyeonggi-do",
        "Geonggi-do ": "Gyeonggi-do",
        "Geongsangbuk-do": "Gyeongsangbuk-do",
        "Pusan-gwangyoksi": "Busan Metropolitan City",
        "Gwangju Gwangyeoksi": "Gwangju Metropolitan City",
    }
    return replacements.get(text, text)


def source_id_for_arcgis(source: object) -> str:
    text = text_or_blank(source)
    if text == "2005 general survey":
        return "KIM_2007_ROK_2005_SURVEY"
    if text == "USFK_Installation survey 2005":
        return "USFK_2005_INSTALLATION_SURVEY"
    if text.startswith("Klein et al."):
        return "KLEIN_2006_FIELD_COLLECTION"
    if text.startswith("Rueda LM"):
        return "RUEDA_2006_ROK_1998_2004"
    return "MOSQUITOMAP_UNMAPPED_SOURCE"


def arcgis_molecular_status(source_id: str) -> tuple[str, str]:
    if source_id == "KIM_2007_ROK_2005_SURVEY":
        return (
            "source_confirmed_molecular_ITS2",
            "The 2005 survey publication reports ITS2 molecular confirmation; "
            "the service record exposes IdentificationMethod=DNA.",
        )
    if source_id == "RUEDA_2006_ROK_1998_2004":
        return (
            "molecular_DNA_source_record",
            "Molecular occurrence record in the public layer; the layer does "
            "not preserve the specimen-level PCR protocol.",
        )
    return (
        "molecular_DNA_layer_record_protocol_pending",
        "The public layer reports IdentificationMethod=DNA; the underlying "
        "specimen protocol is not reproduced in the layer.",
    )


class GridIndex:
    """Simple point-in-polygon lookup for the regular Korea cell grid."""

    def __init__(self, path: Path | None):
        self.features: list[tuple[str, str, list[list[float]], tuple[float, float, float, float]]] = []
        if not path or not path.exists():
            return
        data = json.loads(path.read_text(encoding="utf-8"))
        for feature in data.get("features", []):
            geometry = feature.get("geometry") or {}
            if geometry.get("type") != "Polygon":
                continue
            rings = geometry.get("coordinates") or []
            if not rings:
                continue
            ring = [[float(point[0]), float(point[1])] for point in rings[0]]
            xs = [point[0] for point in ring]
            ys = [point[1] for point in ring]
            bounds = min(xs), min(ys), max(xs), max(ys)
            props = feature.get("properties") or {}
            self.features.append(
                (
                    text_or_blank(props.get("cell_id")),
                    text_or_blank(props.get("country")),
                    ring,
                    bounds,
                )
            )

    @staticmethod
    def point_in_ring(lon: float, lat: float, ring: list[list[float]]) -> bool:
        inside = False
        for index in range(len(ring)):
            x1, y1 = ring[index - 1]
            x2, y2 = ring[index]
            if (y1 > lat) != (y2 > lat):
                crossing = (x2 - x1) * (lat - y1) / (y2 - y1) + x1
                if lon < crossing:
                    inside = not inside
        return inside

    def lookup(self, lon: float | None, lat: float | None) -> tuple[str, str]:
        if lon is None or lat is None:
            return "", ""
        for cell_id, country, ring, bounds in self.features:
            min_x, min_y, max_x, max_y = bounds
            if not (min_x <= lon <= max_x and min_y <= lat <= max_y):
                continue
            if self.point_in_ring(lon, lat, ring):
                return cell_id, country
        return "", ""


def spatial_block_id(lon: float | None, lat: float | None, size: float = 0.1) -> str:
    if lon is None or lat is None:
        return ""
    return f"b{math.floor(lat / size):+04d}_{math.floor(lon / size):+05d}"


def site_id_from_coordinates(lat: float | None, lon: float | None) -> str:
    if lat is None or lon is None:
        return ""
    return f"MMAP_{lat:.5f}_{lon:.5f}"


def base_row() -> dict[str, object]:
    return {
        "record_id": "",
        "source_id": "",
        "source_record_id": "",
        "observation_type": "",
        "species": TARGET_SPECIES,
        "country": COUNTRY,
        "geography": "",
        "site_id": "",
        "site_name": "",
        "spatial_block_id": "",
        "cell_id": "",
        "longitude": "",
        "latitude": "",
        "collection_date": "",
        "year": "",
        "month": "",
        "value": "",
        "unit": "",
        "reported_individual_count": "",
        "life_stage": "",
        "collecting_method": "",
        "sampling_effort": "",
        "taxonomic_basis": "",
        "molecular_method": "",
        "pcr_confirmation_status": "",
        "genbank_accession": "",
        "presence_absence_status": "detected; no non-detection inferred",
        "license": "",
        "source_url": "",
        "reporting_note": "",
    }


def arcgis_observation_rows(records: list[dict], grid: GridIndex) -> list[dict]:
    rows = []
    for record in records:
        lat = parse_float(record.get("DecimalLatitude"))
        lon = parse_float(record.get("DecimalLongitude"))
        date_text = normalize_date(record.get("VerbatimCollectingDate"))
        year = year_from_date(date_text) or parse_int(record.get("EarliestYearCollected"))
        month = (
            int(date_text[5:7])
            if date_text
            else parse_int(record.get("EarliestMonthCollected"))
        )
        source_id = source_id_for_arcgis(record.get("Source"))
        status, note = arcgis_molecular_status(source_id)
        cell_id, grid_country = grid.lookup(lon, lat)
        global_id = text_or_blank(record.get("GlobalUniqueIdentifier"))
        record_id = global_id or f"MMap:OBJECTID:{record.get('OBJECTID')}"
        individual_count = parse_int(record.get("IndividualCount"))
        geography = canonical_province(record.get("StateProvince"))
        locality = text_or_blank(record.get("Locality"))
        collecting_method = text_or_blank(record.get("CollectingMethod"))
        row = base_row()
        row.update(
            {
                "record_id": record_id,
                "source_id": source_id,
                "source_record_id": str(record.get("OBJECTID")),
                "observation_type": "confirmed_occurrence",
                "geography": geography,
                "site_id": site_id_from_coordinates(lat, lon),
                "site_name": locality,
                "spatial_block_id": spatial_block_id(lon, lat),
                "cell_id": cell_id,
                "longitude": lon if lon is not None else "",
                "latitude": lat if lat is not None else "",
                "collection_date": date_text,
                "year": year if year is not None else "",
                "month": month if month is not None else "",
                "value": 1,
                "unit": "presence",
                "reported_individual_count": (
                    individual_count if individual_count is not None else ""
                ),
                "life_stage": text_or_blank(record.get("LifeStage")),
                "collecting_method": collecting_method,
                "sampling_effort": (
                    text_or_blank(record.get("CollectingEffortInHours"))
                    or "not reported at record level"
                ),
                "taxonomic_basis": "molecular_DNA_field_record",
                "molecular_method": "DNA; method detail not retained in layer",
                "pcr_confirmation_status": status,
                "genbank_accession": text_or_blank(record.get("GenBankNum")),
                "license": "public layer terms/reuse status require review",
                "source_url": ARCGIS_EXPERIENCE,
                "reporting_note": (
                    f"ArcGIS MosquitoMap2 OBJECTID={record.get('OBJECTID')}; "
                    f"raw source={text_or_blank(record.get('Source')) or 'not reported'}; "
                    f"locality={locality or 'not reported'}; {note}"
                ),
            }
        )
        if grid.features and not cell_id:
            row["reporting_note"] += " Point did not intersect the supplied 0.25-degree grid."
        elif grid_country and grid_country not in {"South Korea", "North Korea"}:
            row["reporting_note"] += f" Grid country={grid_country}."
        rows.append(row)
    return rows


def clean_docx_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text or "")
    return text.strip()


def parse_docx_tables(blob: bytes) -> list[list[list[str]]]:
    tables: list[list[list[str]]] = []
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    with zipfile.ZipFile(__import__("io").BytesIO(blob)) as archive:
        root = ElementTree.fromstring(archive.read("word/document.xml"))
    for table in root.findall(".//w:tbl", namespace):
        table_rows = []
        for tr in table.findall("./w:tr", namespace):
            cells = []
            for tc in tr.findall("./w:tc", namespace):
                cell_text = "".join(
                    node.text or "" for node in tc.findall(".//w:t", namespace)
                )
                cells.append(clean_docx_text(cell_text))
            if any(cells):
                table_rows.append(cells)
        if table_rows:
            tables.append(table_rows)
    return tables


def start_date_from_range(value: str) -> str:
    return normalize_date(value)


def docx_observation_rows(
    blob: bytes,
    source_id: str,
    source_url: str,
    grid: GridIndex,
) -> list[dict]:
    rows = []
    for table in parse_docx_tables(blob):
        header = table[0]
        if "Anopheles spp." not in header or "Date" not in header or "Place" not in header:
            continue
        species_index = header.index("Anopheles spp.")
        date_index = header.index("Date")
        place_index = header.index("Place")
        id_index = header.index("#") if "#" in header else 0
        method_index = (
            header.index("Method of Identification")
            if "Method of Identification" in header
            else None
        )
        stage_index = header.index("Stage") if "Stage" in header else None
        for cells in table[1:]:
            if max(species_index, date_index, place_index, id_index) >= len(cells):
                continue
            species = cells[species_index].replace("  ", " ").strip()
            if species not in {"An. sinensis", "An. sinensis."}:
                continue
            place = cells[place_index].strip()
            date_text = start_date_from_range(cells[date_index])
            year = year_from_date(date_text)
            lat, lon = SITE_COORDINATES.get(place, (None, None))
            cell_id, _ = grid.lookup(lon, lat)
            record_id = cells[id_index].strip()
            method = cells[method_index].strip() if method_index is not None else ""
            stage = cells[stage_index].strip() if stage_index is not None else ""
            pcr_status = (
                "verified_PCR_or_ITS2_source_table"
                if method
                else "verified_species_source_table_method_not_printed"
            )
            if source_id == "HONG_2023_GIMPO_GANGHWA":
                effort = (
                    "adult traps, 5 traps, 20:00-09:00, site-specific event denominator "
                    "not attached to individual row"
                    if stage.lower().startswith("adult")
                    else "10 dip larval sampling description; individual denominator not "
                    "attached to row"
                )
                license_text = "CC BY 4.0 article; derivative-data reuse should be reviewed"
            else:
                effort = (
                    "Blackhole Mosquito Buster adult trap, 20:00-08:00; event denominator "
                    "not attached to individual row"
                    if stage.lower().startswith("adult")
                    else "10-dip larval sampling per site visit; individual denominator "
                    "not attached to row"
                )
                license_text = (
                    "CC BY-NC-ND 4.0 article; derivative-data reuse should be reviewed"
                )
            row = base_row()
            row.update(
                {
                    "record_id": record_id,
                    "source_id": source_id,
                    "source_record_id": record_id,
                    "observation_type": "confirmed_specimen",
                    "geography": SITE_NAMES.get(place, place),
                    "site_id": f"{source_id}_{place}",
                    "site_name": SITE_NAMES.get(place, place),
                    "spatial_block_id": spatial_block_id(lon, lat),
                    "cell_id": cell_id,
                    "longitude": lon if lon is not None else "",
                    "latitude": lat if lat is not None else "",
                    "collection_date": date_text,
                    "year": year if year is not None else "",
                    "month": int(date_text[5:7]) if date_text else "",
                    "value": 1,
                    "unit": "specimen",
                    "reported_individual_count": 1,
                    "life_stage": stage,
                    "collecting_method": "published supplementary individual record",
                    "sampling_effort": effort,
                    "taxonomic_basis": "molecular_species_confirmation",
                    "molecular_method": method,
                    "pcr_confirmation_status": pcr_status,
                    "license": license_text,
                    "source_url": source_url,
                    "reporting_note": (
                        f"Individual row extracted from the published supplementary table; "
                        f"place code={place}; date range={cells[date_index]}; "
                        "the table is detection-positive and does not create non-detections."
                        + (" The per-row method cell is blank." if not method else "")
                        + (
                            " The main article reports 124 An. sinensis in the kdr-analysis "
                            "subset; this row belongs to the 146-row species table and is "
                            "not assumed to be part of that subset."
                            if source_id == "JEON_2025_GANGHWA_2024"
                            else ""
                        )
                    ),
                }
            )
            # The source tables list molecular sequence/accession detail in separate columns
            # only for some tables. Keep the raw method text in molecular_method rather than
            # fabricating an accession for rows where it was not printed.
            rows.append(row)
    return rows


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def source_registry_rows() -> list[dict]:
    return [
        {
            "source_id": "LI_2005_MULTIPLEX_ITS2",
            "field_years": "foundational assay/reference material",
            "publication_year": 2005,
            "geography": "Republic of Korea",
            "sites_or_scope": "molecular identification of Korean Anopheles Hyrcanus Group",
            "target_species_count": "method/reference study; no harmonized abundance table",
            "molecular_method": "molecular identification using ITS2-based assay/reference sequences",
            "data_status": "method_reference_only",
            "source_url": "https://doi.org/10.11646/zootaxa.939.1.1",
            "notes": "Foundational taxonomic reference; not merged as a response table.",
        },
        {
            "source_id": "RUEDA_2006_ROK_1998_2004",
            "field_years": "1998-2004",
            "publication_year": 2006,
            "geography": "Republic of Korea",
            "sites_or_scope": "204 collection locations reported in the article",
            "target_species_count": "partial public-layer extraction: 45 records, 35 coordinate sites",
            "molecular_method": "molecular species records; original specimen protocol requires source review",
            "data_status": "individual_occurrence_records_included_partial",
            "source_url": "https://bioone.org/journals/journal-of-vector-ecology/volume-31/issue-1/1081-1710%282006%2931%5B198%3ADALHCO%5D2.0.CO%3B2/Distribution-and-larval-habitat-characteristics-of-span-classgenus-speciesAnopheles-span/10.3376/1081-1710%282006%2931%5B198%3ADALHCO%5D2.0.CO%3B2.full",
            "notes": "No zero records or effort-standardized rates are inferred.",
        },
        {
            "source_id": "KIM_2007_ROK_2005_SURVEY",
            "field_years": "2005",
            "publication_year": 2007,
            "geography": "Republic of Korea",
            "sites_or_scope": "selected adult and larval surveillance sites",
            "target_species_count": "3,194 An. sinensis among 4,534 Anopheles; 6,644 mosquitoes total",
            "molecular_method": "ITS2 within nuclear ribosomal DNA",
            "data_status": "individual_occurrence_records_included_partial",
            "source_url": "https://doi.org/10.1111/j.1748-5967.2007.00049.x",
            "notes": "Published aggregate and partial public-layer records are kept separate.",
        },
        {
            "source_id": "FOLEY_2009_ROK_ENM",
            "field_years": "1998-2006",
            "publication_year": 2009,
            "geography": "Republic of Korea",
            "sites_or_scope": "occurrence points used for ecological niche modeling",
            "target_species_count": "152 unique An. sinensis sites before 5-km thinning; 80 retained for analysis",
            "molecular_method": "literature-linked molecular occurrence records; source-specific methods vary",
            "data_status": "analysis_reference_only",
            "source_url": "https://academic.oup.com/jme/article/46/3/680/861860",
            "notes": "Occurrence-only ENM input; not an effort-standardized abundance panel.",
        },
        {
            "source_id": "KANG_2012_ROK_KDR",
            "field_years": "not stated in article summary",
            "publication_year": 2012,
            "geography": "Republic of Korea",
            "sites_or_scope": "22 locations",
            "target_species_count": "665 An. sinensis among 755 An. sinensis complex specimens; present at 21/22 sites",
            "molecular_method": "multiplex molecular assay for species; VGSC PCR and direct sequencing",
            "data_status": "published_aggregate_only",
            "source_url": "https://doi.org/10.1186/1475-2875-11-151",
            "notes": "No collection year or site-level response rows were added without extraction from Table 1.",
        },
        {
            "source_id": "LEE_2022_FIELD_2020",
            "field_years": "May-early November 2020",
            "publication_year": 2022,
            "geography": "Gyeonggi Province, Republic of Korea",
            "sites_or_scope": "6 high-risk near-DMZ sites plus Yongsan and Humphreys USAG",
            "target_species_count": "165 An. sinensis among 1,622 assayed; 1,864 Anopheles identified to species",
            "molecular_method": "PCR species identification; P. vivax PCR separately",
            "data_status": "published_aggregate_only",
            "source_url": "https://doi.org/10.1093/jme/tjac086",
            "notes": "Exact site-level target counts and non-detections were not available in the reviewed abstract record.",
        },
        {
            "source_id": "JEON_2025_FIELD_2021",
            "field_years": "April-October 2021",
            "publication_year": 2025,
            "geography": "Gyeonggi/Seoul, Republic of Korea",
            "sites_or_scope": "8 sites: 6 in/near DMZ, Yongsan USAG, Humphreys USAG",
            "target_species_count": "122 An. sinensis among 489 Anopheles",
            "molecular_method": "multiplex PCR species identification; ITS2 sequencing for selected specimens",
            "data_status": "published_site_period_counts_included",
            "source_url": "https://journals.plos.org/plosntds/article?id=10.1371/journal.pntd.0012748",
            "notes": "Table 1 counts are site-period aggregates; exact trap-hours and non-detection denominators are not reported there.",
        },
        {
            "source_id": "HONG_2023_GIMPO_GANGHWA",
            "field_years": "July-October 2022; July-October 2023",
            "publication_year": 2023,
            "geography": "Gimpo/Ganghwa, Republic of Korea",
            "sites_or_scope": "Wolgot-myeon and Naega-myeon",
            "target_species_count": "individual supplementary records; source aggregate includes 118 An. sinensis among 267 Anopheles",
            "molecular_method": "multiplex PCR, ITS2, and COI sequencing as printed per specimen",
            "data_status": "individual_supplementary_records_included",
            "source_url": "https://doi.org/10.1186/s12936-023-04821-x",
            "notes": "Individual rows are detection-positive; protocol denominators remain site/event metadata, not per-row negatives.",
        },
        {
            "source_id": "JEON_2025_GANGHWA_2024",
            "field_years": "July-mid September 2024",
            "publication_year": 2025,
            "geography": "Ganghwa-gun, Incheon, Republic of Korea",
            "sites_or_scope": "Naega-myeon, Kukhwa-ri, Seonhaeng-ri",
            "target_species_count": (
                "146 An. sinensis rows in Supplementary Table S1; "
                "main text reports a 124-mosquito kdr-analysis subset"
            ),
            "molecular_method": "multiplex PCR and ITS2 sequencing as printed per specimen",
            "data_status": "individual_supplementary_records_included",
            "source_url": "https://doi.org/10.1038/s41598-025-29307-5",
            "notes": (
                "The individual table preserves all 146 target rows. Do not use the "
                "124 kdr subset as the denominator for the full supplementary table. "
                "2024 source is CC BY-NC-ND; derivative-data reuse should be reviewed "
                "before public redistribution."
            ),
        },
    ]


def published_site_period_rows() -> list[dict]:
    rows = []
    # Lee et al. 2020 is retained as one study aggregate because the reviewed
    # public record does not expose site-level target counts.
    rows.append(
        {
            "source_id": "LEE_2022_FIELD_2020",
            "year": 2020,
            "site_id": "LEE2020_GYEONGGI_ALL",
            "site_name": "Gyeonggi 8-site study aggregate",
            "longitude": "",
            "latitude": "",
            "period": "May-early November 2020",
            "observation_type": "published_study_aggregate",
            "species": TARGET_SPECIES,
            "value": 165,
            "unit": "specimens_assayed_as_An_sinensis",
            "denominator": 1622,
            "total_anopheles_identified": 1864,
            "sampling_effort": "Mosquito Magnet traps; six high-risk near-DMZ sites plus Yongsan and Humphreys USAG; exact trap-hours not in reviewed abstract",
            "taxonomic_basis": "PCR",
            "data_granularity": "study_aggregate",
            "validation_role": "context_only_until_site_rows_obtained",
            "source_url": "https://doi.org/10.1093/jme/tjac086",
            "notes": "Do not merge with site-level counts as if they shared a common denominator.",
        }
    )
    site_counts_2021 = [
        ("NNSC", 37.954775, 126.679975, 4),
        ("Daeseong-dong", 37.941197, 126.677050, 26),
        ("South Gate", 37.934314, 126.720961, 2),
        ("Camp Bonifas", 37.932014, 126.722703, 8),
        ("Warrior Base", 37.917767, 126.741594, 27),
        ("Dagmar North", 37.974958, 126.844689, 4),
        ("Yongsan USAG", 37.532278, 126.981500, 17),
        ("Humphreys USAG", 36.955528, 127.028167, 34),
    ]
    for site, lat, lon, count in site_counts_2021:
        rows.append(
            {
                "source_id": "JEON_2025_FIELD_2021",
                "year": 2021,
                "site_id": "JEON2021_" + re.sub(r"[^A-Za-z0-9]+", "_", site).strip("_"),
                "site_name": site,
                "longitude": lon,
                "latitude": lat,
                "period": "April-October 2021",
                "observation_type": "published_site_period_count",
                "species": TARGET_SPECIES,
                "value": count,
                "unit": "specimens_over_collection_period",
                "denominator": "",
                "total_anopheles_identified": 489,
                "sampling_effort": "Mosquito Magnet traps; biweekly collection; exact trap-hours and site-specific non-detection denominators not reported in Table 1",
                "taxonomic_basis": "multiplex_PCR",
                "data_granularity": "site_period_aggregate",
                "validation_role": "site_period_context; not a weekly rate",
                "source_url": "https://journals.plos.org/plosntds/article?id=10.1371/journal.pntd.0012748",
                "notes": "Coordinates transcribed from the article methods; counts transcribed from Table 1.",
            }
        )
    return rows


def longitudinal_summary(observation_rows: list[dict]) -> list[dict]:
    groups: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for row in observation_rows:
        if row.get("year") in {"", None}:
            continue
        groups[(str(row["source_id"]), int(row["year"]))].append(row)
    rows = []
    for (source_id, year), group in sorted(groups.items(), key=lambda item: item[0]):
        sites = {row["site_id"] for row in group if row.get("site_id")}
        blocks = {row["spatial_block_id"] for row in group if row.get("spatial_block_id")}
        reported = [
            int(row["reported_individual_count"])
            for row in group
            if str(row.get("reported_individual_count", "")).isdigit()
        ]
        rows.append(
            {
                "source_id": source_id,
                "year": year,
                "observation_rows": len(group),
                "unique_sites": len(sites),
                "unique_spatial_blocks_0p1deg": len(blocks),
                "unique_cells": len({row["cell_id"] for row in group if row.get("cell_id")}),
                "reported_individual_count_sum": sum(reported) if reported else "",
                "rows_with_collection_date": sum(bool(row.get("collection_date")) for row in group),
                "rows_with_month": sum(bool(row.get("month")) for row in group),
                "taxonomic_basis": "; ".join(sorted({str(row["pcr_confirmation_status"]) for row in group})),
                "sampling_effort_status": "not standardized across records; no zeros inferred",
                "validation_role": "presence-only molecular stratum",
            }
        )
    # Add the two published aggregate periods without pretending they are the
    # same row type as the individual evidence table.
    rows.extend(
        [
            {
                "source_id": "LEE_2022_FIELD_2020",
                "year": 2020,
                "observation_rows": 1,
                "unique_sites": 8,
                "unique_spatial_blocks_0p1deg": "",
                "unique_cells": "",
                "reported_individual_count_sum": 165,
                "rows_with_collection_date": 0,
                "rows_with_month": 0,
                "taxonomic_basis": "PCR; published study aggregate",
                "sampling_effort_status": "trap type and study window reported; site-event denominators not extracted",
                "validation_role": "aggregate context only",
            },
            {
                "source_id": "JEON_2025_FIELD_2021",
                "year": 2021,
                "observation_rows": 8,
                "unique_sites": 8,
                "unique_spatial_blocks_0p1deg": "",
                "unique_cells": "",
                "reported_individual_count_sum": 122,
                "rows_with_collection_date": 0,
                "rows_with_month": 0,
                "taxonomic_basis": "multiplex PCR; published site-period aggregate",
                "sampling_effort_status": "biweekly trap collection reported; exact site-event denominators not extracted",
                "validation_role": "site-period aggregate context",
            },
        ]
    )
    return sorted(rows, key=lambda row: (int(row["year"]), row["source_id"]))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=Path("."))
    parser.add_argument("--grid", type=Path, default=None)
    parser.add_argument("--no-network", action="store_true")
    args = parser.parse_args()

    output_root = args.output_root
    inputs = output_root / "inputs"
    metadata = output_root / "metadata"

    if args.no_network:
        raise SystemExit("--no-network is not supported: the source records are built from reviewed public endpoints")

    grid = GridIndex(args.grid)
    arcgis_records = fetch_arcgis_records()
    observations = arcgis_observation_rows(arcgis_records, grid)

    hong_blob = fetch_bytes(HONG_2023_DOCX)
    observations.extend(
        docx_observation_rows(
            hong_blob,
            "HONG_2023_GIMPO_GANGHWA",
            "https://doi.org/10.1186/s12936-023-04821-x",
            grid,
        )
    )
    jeon_blob = fetch_bytes(JEON_2024_DOCX)
    observations.extend(
        docx_observation_rows(
            jeon_blob,
            "JEON_2025_GANGHWA_2024",
            "https://doi.org/10.1038/s41598-025-29307-5",
            grid,
        )
    )

    observations.sort(
        key=lambda row: (
            int(row["year"]) if str(row.get("year", "")).isdigit() else 9999,
            str(row.get("source_id", "")),
            str(row.get("site_id", "")),
            str(row.get("record_id", "")),
        )
    )

    observation_fields = list(base_row().keys())
    write_csv(inputs / "rok_anopheles_sinensis_pcr_observations.csv", observations, observation_fields)

    aggregate_rows = published_site_period_rows()
    aggregate_fields = [
        "source_id",
        "year",
        "site_id",
        "site_name",
        "longitude",
        "latitude",
        "period",
        "observation_type",
        "species",
        "value",
        "unit",
        "denominator",
        "total_anopheles_identified",
        "sampling_effort",
        "taxonomic_basis",
        "data_granularity",
        "validation_role",
        "source_url",
        "notes",
    ]
    write_csv(inputs / "rok_anopheles_sinensis_pcr_site_period_counts.csv", aggregate_rows, aggregate_fields)

    summary_rows = longitudinal_summary(observations)
    summary_fields = list(summary_rows[0].keys())
    write_csv(inputs / "rok_anopheles_sinensis_longitudinal_validation.csv", summary_rows, summary_fields)

    registry = source_registry_rows()
    registry_fields = list(registry[0].keys())
    write_csv(metadata / "rok_anopheles_pcr_source_registry.csv", registry, registry_fields)

    metadata_payload = {
        "generated_utc": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "target_species": TARGET_SPECIES,
        "country": COUNTRY,
        "arcgis_layer": ARCGIS_LAYER,
        "arcgis_experience": ARCGIS_EXPERIENCE,
        "arcgis_filter": "Species = 'sinensis' AND Country LIKE '%Korea%' AND IdentificationMethod = 'DNA'",
        "supplementary_sources": {
            "hong_2023": HONG_2023_DOCX,
            "jeon_2024": JEON_2024_DOCX,
        },
        "grid_path": str(args.grid) if args.grid else "not supplied",
        "observation_rows": len(observations),
        "observation_rows_with_grid_cell": sum(
            bool(row["cell_id"]) for row in observations
        ),
        "observation_rows_without_grid_cell": sum(
            not bool(row["cell_id"]) for row in observations
        ),
        "observation_source_counts": dict(Counter(str(row["source_id"]) for row in observations)),
        "observation_year_counts": dict(
            sorted(
                Counter(
                    int(row["year"])
                    for row in observations
                    if str(row.get("year", "")).isdigit()
                ).items()
            )
        ),
        "unique_site_ids": len({row["site_id"] for row in observations if row.get("site_id")}),
        "unique_spatial_blocks_0p1deg": len(
            {row["spatial_block_id"] for row in observations if row.get("spatial_block_id")}
        ),
        "direct_observation_years": sorted(
            {
                int(row["year"])
                for row in observations
                if str(row.get("year", "")).isdigit()
            }
        ),
        "published_aggregate_rows": len(aggregate_rows),
        "scope_boundary": [
            "No absence or effort-standardized rate is inferred from missing records.",
            "Published aggregates are not pooled with individual records.",
            "The table supports validation partition design but not a completed predictive gate.",
        ],
    }
    metadata.mkdir(parents=True, exist_ok=True)
    (metadata / "rok_anopheles_table_run_metadata.json").write_text(
        json.dumps(metadata_payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(metadata_payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
