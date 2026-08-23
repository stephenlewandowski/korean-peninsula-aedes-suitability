#!/usr/bin/env python3
"""Independently audit publication figures, website claims, and downloads."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import math
import re
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EARLY_PERIOD = "1975-1984"
RECENT_PERIOD = "2015-2024"
SPECIES = ["aegypti", "albopictus"]
FIGURE_STEMS = [
    "suitability-change-map",
    "seasonal-profile-shift",
    "population-exposure-map",
    "population-exposure-summary",
    "rok-aedes-evidence-map",
    "pooled-trap-indices",
]


class LinkAndImageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []
        self.images: list[tuple[str, str | None]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "a" and attributes.get("href"):
            self.links.append(str(attributes["href"]))
        if tag == "img" and attributes.get("src"):
            self.images.append((str(attributes["src"]), attributes.get("alt")))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docs-dir", type=Path, default=PROJECT_ROOT / "docs")
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "outputs" / "publication" / "publication_audit.json",
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


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [{key: (value or "").strip() for key, value in row.items()} for row in csv.DictReader(handle)]


def require_close(actual: float, expected: float, label: str, tolerance: float = 1e-9) -> None:
    if not math.isclose(actual, expected, rel_tol=tolerance, abs_tol=tolerance):
        raise ValueError(f"{label} mismatch: site={actual}, source={expected}")


def audit_summary_values(summary: dict[str, object]) -> None:
    seasonal_rows = read_csv(
        PROJECT_ROOT
        / "outputs"
        / "korea_focus"
        / "tables"
        / "korea_focus_seasonal_change_early_to_recent.csv"
    )
    population_rows = read_csv(
        PROJECT_ROOT
        / "outputs"
        / "korea_focus_population"
        / "population_exposure_change_early_to_recent.csv"
    )
    observations = read_csv(PROJECT_ROOT / "inputs" / "aedes_observations.csv")
    traps = read_csv(PROJECT_ROOT / "inputs" / "aedes_trap_abundance.csv")

    suitability = summary["suitability"]
    population = summary["population_exposure"]
    evidence = summary["rok_aedes_evidence"]
    assert isinstance(suitability, dict)
    assert isinstance(population, dict)
    assert isinstance(evidence, dict)

    for species in SPECIES:
        seasonal = next(
            row
            for row in seasonal_rows
            if row["geography"] == "Korean Peninsula" and row["species"] == species
        )
        exposed = next(
            row
            for row in population_rows
            if row["geography"] == "Korean Peninsula" and row["species"] == species
        )
        species_summary = suitability[species]
        population_summary = population[species]
        assert isinstance(species_summary, dict)
        assert isinstance(population_summary, dict)
        require_close(
            float(species_summary["change_months"]),
            float(seasonal["mean_suitable_months_delta_recent_minus_early"]),
            f"{species} suitable-month change",
        )
        require_close(
            float(population_summary["share_recent_population_in_cells_with_increasing_suitable_month_count"]),
            float(exposed["share_recent_population_in_cells_with_increasing_suitable_month_count"]),
            f"{species} recent population share",
        )
        require_close(
            float(population_summary["population_weighted_suitable_month_count_delta"]),
            float(exposed["population_weighted_suitable_month_count_delta"]),
            f"{species} population-weighted change",
        )

    if int(evidence["occurrence_records"]) != len(observations) or len(observations) != 54:
        raise ValueError("Occurrence record count does not reconcile")
    if int(evidence["trap_index_rows"]) != len(traps) or len(traps) != 6:
        raise ValueError("Pooled trap-index row count does not reconcile")
    if len({row["site_id"] for row in traps}) != 6:
        raise ValueError("Trap rows are not six unique sites")
    if any(row["collection_years"] != "2013;2014" for row in traps):
        raise ValueError("Trap rows do not preserve pooled 2013-2014 periods")
    if any(row["active_months"] != "04;05;06;07;08;09;10;11" for row in traps):
        raise ValueError("Trap rows do not preserve April-November active months")
    total_nights = sum(int(row["trap_nights"]) for row in traps)
    total_hours = sum(float(row["trap_hours"]) for row in traps)
    if total_nights != 192 or not math.isclose(total_hours, 2688.0):
        raise ValueError("Trap effort totals do not reconcile")
    if int(evidence["total_trap_nights"]) != total_nights:
        raise ValueError("Website summary trap-night total does not reconcile")
    require_close(float(evidence["total_trap_hours"]), total_hours, "Website trap-hour total")


def audit_manifest(manifest: dict[str, object]) -> None:
    if manifest.get("status") != "PASS":
        raise ValueError("Publication product manifest is not PASS")
    for section in ["inputs", "outputs"]:
        entries = manifest.get(section)
        if not isinstance(entries, dict) or not entries:
            raise ValueError(f"Manifest {section} is empty")
        for label, details in entries.items():
            if not isinstance(details, dict):
                raise ValueError(f"Manifest entry {label} is malformed")
            path = Path(str(details["path"])) if section == "inputs" else PROJECT_ROOT / str(label)
            if not path.exists():
                raise FileNotFoundError(f"Manifest path is missing: {path}")
            if sha256_file(path) != details["sha256"]:
                raise ValueError(f"Manifest checksum mismatch: {path}")


def audit_figures(docs_dir: Path) -> dict[str, dict[str, object]]:
    audited: dict[str, dict[str, object]] = {}
    for stem in FIGURE_STEMS:
        svg_path = docs_dir / "assets" / "figures" / f"{stem}.svg"
        png_path = docs_dir / "assets" / "figures" / f"{stem}.png"
        if not svg_path.exists() or not png_path.exists():
            raise FileNotFoundError(f"Missing SVG/PNG figure pair for {stem}")
        if svg_path.stat().st_size < 5_000 or png_path.stat().st_size < 20_000:
            raise ValueError(f"Figure output appears unexpectedly small: {stem}")
        root = ET.parse(svg_path).getroot()
        if not root.tag.endswith("svg"):
            raise ValueError(f"Invalid SVG root: {svg_path}")
        with png_path.open("rb") as handle:
            if handle.read(8) != b"\x89PNG\r\n\x1a\n":
                raise ValueError(f"Invalid PNG signature: {png_path}")
        audited[stem] = {
            "svg_sha256": sha256_file(svg_path),
            "png_sha256": sha256_file(png_path),
            "svg_bytes": svg_path.stat().st_size,
            "png_bytes": png_path.stat().st_size,
        }
    return audited


def audit_site(docs_dir: Path) -> dict[str, object]:
    pages = [docs_dir / "index.html", docs_dir / "methods.html", docs_dir / "data.html"]
    checked_links = 0
    checked_images = 0
    page_checksums: dict[str, str] = {}
    for page in pages:
        if not page.exists():
            raise FileNotFoundError(f"Missing website page: {page}")
        text = page.read_text(encoding="utf-8")
        if "<meta name=\"viewport\"" not in text:
            raise ValueError(f"Missing responsive viewport metadata: {page}")
        if "file://" in text:
            raise ValueError(f"Website contains a local file URI: {page}")
        parser = LinkAndImageParser()
        parser.feed(text)
        for source, alt in parser.images:
            checked_images += 1
            if not alt or len(alt.strip()) < 20:
                raise ValueError(f"Image lacks meaningful alt text: {page}:{source}")
            target = page.parent / source
            if not target.exists():
                raise FileNotFoundError(f"Missing website image: {target}")
        for href in parser.links:
            parsed = urlparse(href)
            if parsed.scheme in {"http", "https", "mailto"} or href.startswith("#"):
                continue
            checked_links += 1
            local_path = href.split("#", 1)[0]
            if not local_path:
                continue
            target = page.parent / local_path
            if not target.exists():
                raise FileNotFoundError(f"Broken local link: {page}:{href}")
        page_checksums[str(page.relative_to(PROJECT_ROOT))] = sha256_file(page)

    index_text = (docs_dir / "index.html").read_text(encoding="utf-8")
    required_claims = [
        "+0.57",
        "+0.50",
        "95.6–98.8%",
        "54 + 6",
        "192 trap-nights",
        "2,688 trap-hours",
        "not disease incidence",
        "modeled extrapolation",
        "Monthly counts were not fabricated",
    ]
    missing_claims = [claim for claim in required_claims if claim not in index_text]
    if missing_claims:
        raise ValueError("Website is missing required bounded claims: " + ", ".join(missing_claims))
    return {
        "pages": len(pages),
        "local_links_checked": checked_links,
        "images_checked": checked_images,
        "page_sha256": page_checksums,
    }


def audit_workflow() -> str:
    path = PROJECT_ROOT / ".github" / "workflows" / "pages.yml"
    text = path.read_text(encoding="utf-8")
    required = [
        "actions/checkout@v6",
        "actions/configure-pages@v5",
        "actions/upload-pages-artifact@v4",
        "actions/deploy-pages@v4",
        "path: docs",
    ]
    missing = [value for value in required if value not in text]
    if missing:
        raise ValueError("Pages workflow is missing: " + ", ".join(missing))
    return sha256_file(path)


def main() -> None:
    args = parse_args()
    docs_dir = resolve_path(args.docs_dir)
    output_path = resolve_path(args.output)
    summary_path = docs_dir / "assets" / "data" / "project_summary.json"
    public_manifest_path = docs_dir / "assets" / "data" / "publication_product_manifest.json"
    manifest_path = PROJECT_ROOT / "outputs" / "publication" / "publication_product_manifest.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if sha256_file(public_manifest_path) != sha256_file(manifest_path):
        raise ValueError("Public and repository publication manifests do not match")

    audit_summary_values(summary)
    audit_manifest(manifest)
    figures = audit_figures(docs_dir)
    site = audit_site(docs_dir)
    workflow_sha256 = audit_workflow()

    checks = {
        "headline_values_reconcile_with_source_tables": True,
        "population_exposure_language_is_bounded": True,
        "occurrence_and_trap_inputs_remain_separate": True,
        "six_trap_rows_remain_pooled_2013_2014_indices": True,
        "trap_effort_reconciles_to_192_nights_2688_hours": True,
        "monthly_trap_rows_created": 0,
        "raw_trap_counts_reconstructed": False,
        "six_svg_png_figure_pairs_are_valid": True,
        "website_local_links_and_images_resolve": True,
        "website_images_have_alt_text": True,
        "github_pages_workflow_is_configured": True,
    }
    audit = {
        "generated_utc": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "status": "PASS",
        "checks": checks,
        "site": site,
        "figures": figures,
        "provenance": {
            "summary": str(summary_path),
            "summary_sha256": sha256_file(summary_path),
            "product_manifest": str(manifest_path),
            "product_manifest_sha256": sha256_file(manifest_path),
            "public_product_manifest": str(public_manifest_path),
            "pages_workflow_sha256": workflow_sha256,
        },
        "interpretation_boundary": (
            "Publication products report modeled environmental suitability, population exposure, "
            "presence-only occurrence, and pooled effort-aware trap indices. They do not report "
            "disease risk, incidence, infection probability, or transmission forecasts."
        ),
        "errors": [],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "PASS",
                "checks": len(checks),
                "pages": site["pages"],
                "figures": len(figures),
                "output": str(output_path),
            }
        )
    )


if __name__ == "__main__":
    main()
