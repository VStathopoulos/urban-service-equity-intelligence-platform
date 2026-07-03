#!/usr/bin/env python3

from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path


MAP_DIR = Path("reports/maps")
MAP_GLOB = "*service_request_map.html"


def extract_legend_pairs(html_text: str) -> list[tuple[str, str]]:
    """Return legend pairs as (hex_color, category_label)."""
    return re.findall(
        r"background:(#[0-9a-fA-F]{6}).*?<span>([^<]+)</span>",
        html_text,
        flags=re.S,
    )


def check_required_text(html_path: Path, html_text: str) -> list[str]:
    errors = []

    required_fragments = [
        "Service category",
        "map coverage",
        "Displayed points:",
        "Only requests with valid latitude/longitude are shown.",
    ]

    for fragment in required_fragments:
        if fragment not in html_text:
            errors.append(f"{html_path.name}: missing required text: {fragment!r}")

    return errors


def check_duplicate_legend_colors(
    html_path: Path,
    legend_pairs: list[tuple[str, str]],
) -> list[str]:
    errors = []
    color_to_categories: dict[str, list[str]] = defaultdict(list)

    for color, category in legend_pairs:
        color_to_categories[color].append(category)

    duplicates = {
        color: categories
        for color, categories in color_to_categories.items()
        if len(categories) > 1
    }

    for color, categories in duplicates.items():
        errors.append(
            f"{html_path.name}: duplicate legend color {color} for categories: {categories}"
        )

    return errors


def check_cross_map_consistency(
    category_to_colors: dict[str, set[str]],
) -> list[str]:
    errors = []

    inconsistent = {
        category: colors
        for category, colors in category_to_colors.items()
        if len(colors) > 1
    }

    for category, colors in inconsistent.items():
        errors.append(
            f"Cross-map inconsistency: {category!r} has colors {sorted(colors)}"
        )

    return errors


def main() -> int:
    html_paths = sorted(MAP_DIR.glob(MAP_GLOB))

    if not html_paths:
        print(f"ERROR: no generated Folium map files found under {MAP_DIR}/{MAP_GLOB}")
        return 1

    print("Checking generated Folium map outputs...")
    print(f"Map files found: {len(html_paths)}")

    all_errors: list[str] = []
    category_to_colors: dict[str, set[str]] = defaultdict(set)

    for html_path in html_paths:
        html_text = html_path.read_text(encoding="utf-8", errors="ignore")
        legend_pairs = extract_legend_pairs(html_text)

        print(f"\n{html_path.name}")
        print(f"Legend categories: {len(legend_pairs)}")

        if not legend_pairs:
            all_errors.append(f"{html_path.name}: no legend category/color pairs found")
            continue

        for color, category in legend_pairs:
            print(f"  {color}  {category}")
            category_to_colors[category].add(color)

        all_errors.extend(check_required_text(html_path, html_text))
        all_errors.extend(check_duplicate_legend_colors(html_path, legend_pairs))

    all_errors.extend(check_cross_map_consistency(category_to_colors))

    if all_errors:
        print("\nFAILED Folium map QA checks:")
        for error in all_errors:
            print(f"- {error}")
        return 1

    print("\nPASSED Folium map QA checks:")
    print("- Generated map HTML files exist.")
    print("- Each map contains a service-category legend.")
    print("- Each map contains the geospatial coverage caveat.")
    print("- No duplicate legend colors exist within a map.")
    print("- Repeated categories use consistent colors across maps.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
