#!/usr/bin/env python3

from __future__ import annotations

import re
from pathlib import Path


MAP_DIR = Path("reports/maps")
HEX_MAP_GLOB = "*_service_request_hex_map.html"


REQUIRED_TEXT = [
    "Service Request Hex Hotspots",
    "H3 aggregation of geocoded service requests",
    "Hex request density",
    "Hex map caveat",
    "Source points:",
    "Displayed hexes:",
    "H3 resolution:",
    "H3 request hotspot",
    "Dominant category",
    "Open rate",
    "72h breach proxy",
]


def count_polygons(html_text: str) -> int:
    return len(re.findall(r"\bL\.polygon\(", html_text))


def extract_header_counts(html_text: str) -> tuple[int | None, int | None]:
    source_match = re.search(r"Source points:\s*([0-9,]+)", html_text)
    hex_match = re.search(r"Displayed hexes:\s*([0-9,]+)", html_text)

    source_points = (
        int(source_match.group(1).replace(",", ""))
        if source_match
        else None
    )

    displayed_hexes = (
        int(hex_match.group(1).replace(",", ""))
        if hex_match
        else None
    )

    return source_points, displayed_hexes


def check_hex_map(path: Path) -> list[str]:
    errors: list[str] = []
    html_text = path.read_text(encoding="utf-8", errors="ignore")

    for fragment in REQUIRED_TEXT:
        if fragment not in html_text:
            errors.append(f"{path.name}: missing required text: {fragment!r}")

    polygon_count = count_polygons(html_text)
    source_points, displayed_hexes = extract_header_counts(html_text)

    print(f"\n{path.name}")
    print(f"  polygons found: {polygon_count}")

    if source_points is not None:
        print(f"  source points from header: {source_points:,}")
    else:
        errors.append(f"{path.name}: could not parse source-points header value")

    if displayed_hexes is not None:
        print(f"  displayed hexes from header: {displayed_hexes:,}")
    else:
        errors.append(f"{path.name}: could not parse displayed-hexes header value")

    if polygon_count == 0:
        errors.append(f"{path.name}: no Leaflet polygon layers found")

    if displayed_hexes is not None and polygon_count != displayed_hexes:
        errors.append(
            f"{path.name}: polygon count {polygon_count:,} does not match "
            f"displayed hexes {displayed_hexes:,}"
        )

    if source_points is not None and source_points <= 0:
        errors.append(f"{path.name}: source-points count is not positive")

    if displayed_hexes is not None and displayed_hexes <= 0:
        errors.append(f"{path.name}: displayed-hexes count is not positive")

    return errors


def main() -> int:
    html_paths = sorted(MAP_DIR.glob(HEX_MAP_GLOB))

    if not html_paths:
        print(f"ERROR: no generated H3 hex map files found under {MAP_DIR}/{HEX_MAP_GLOB}")
        return 1

    print("Checking generated H3 Folium hex maps...")
    print(f"Hex map files found: {len(html_paths)}")

    all_errors: list[str] = []

    for path in html_paths:
        all_errors.extend(check_hex_map(path))

    if all_errors:
        print("\nFAILED H3 hex-map QA checks:")
        for error in all_errors:
            print(f"- {error}")
        return 1

    print("\nPASSED H3 hex-map QA checks:")
    print("- Generated H3 hex map HTML files exist.")
    print("- Each hex map contains header, legend, caveat, and popup content.")
    print("- Each hex map contains Leaflet polygon layers.")
    print("- Polygon counts match displayed-hex counts from the header.")
    print("- Source-point and displayed-hex counts are positive.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
