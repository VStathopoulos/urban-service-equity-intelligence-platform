import html
import os
from pathlib import Path

import folium
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
import html as html_lib

# --- Step 6D.1: Folium category styling helpers ---

CATEGORY_PALETTE = [
    "#2563eb",  # blue
    "#dc2626",  # red
    "#16a34a",  # green
    "#9333ea",  # purple
    "#ea580c",  # orange
    "#0891b2",  # cyan
    "#ca8a04",  # amber
    "#be185d",  # pink
    "#4f46e5",  # indigo
    "#65a30d",  # lime
    "#7c2d12",  # brown
    "#475569",  # slate
]

DEFAULT_CATEGORY_COLOR = "#6b7280"


def _clean_category(value):
    if value is None:
        return "Unknown / Missing"

    value = str(value).strip()

    if value == "" or value.lower() in {"nan", "none", "null"}:
        return "Unknown / Missing"

    return value


GLOBAL_CATEGORY_COLOR_BY_KEY = {
    # Explicit semantic colors for common standardized service groups.
    # Keys are normalized by _category_key(): lowercase, punctuation removed,
    # whitespace collapsed. This makes colors stable across cities.
    "waste sanitation": "#16a34a",
    "sanitation waste": "#16a34a",
    "trash garbage sanitation": "#16a34a",

    "streets transport": "#2563eb",
    "transport streets": "#2563eb",
    "roads sidewalks transport": "#2563eb",
    "street road sidewalk": "#2563eb",

    "water drainage": "#0891b2",
    "sewer water drainage": "#0891b2",

    "noise": "#dc2626",
    "noise complaints": "#dc2626",

    "housing buildings": "#9333ea",
    "buildings housing": "#9333ea",

    "parks public space": "#65a30d",
    "public space parks": "#65a30d",

    "public safety": "#ea580c",
    "safety enforcement": "#ea580c",

    "parking vehicles": "#ca8a04",
    "vehicles parking": "#ca8a04",

    "environment air quality": "#0f766e",
    "air quality environment": "#0f766e",

    "other": "#475569",
    "other unclassified": "#475569",
    "unknown missing": DEFAULT_CATEGORY_COLOR,
}


KEYWORD_CATEGORY_COLOR_RULES = [
    (("waste", "sanitation", "trash", "garbage", "cleaning"), "#16a34a"),
    (("street", "streets", "road", "roads", "sidewalk", "traffic", "transport"), "#2563eb"),
    (("water", "drainage", "sewer", "flood"), "#0891b2"),
    (("noise",), "#dc2626"),
    (("housing", "building", "buildings", "construction"), "#9333ea"),
    (("park", "parks", "public space", "green"), "#65a30d"),
    (("safety", "police", "enforcement"), "#ea580c"),
    (("parking", "vehicle", "vehicles", "car"), "#ca8a04"),
    (("environment", "air quality", "pollution", "tree"), "#0f766e"),
    (("other", "uncategorized", "unclassified"), "#475569"),
]


EXACT_CATEGORY_COLOR_BY_KEY = {
    # Exact standardized categories currently present in the NYC/Barcelona maps.
    # Keys are normalized through _category_key().
    "administrative information digital services": "#ca8a04",  # amber
    "culture leisure sports": "#be185d",  # magenta
    "economic development commerce": "#a16207",  # ochre
    "housing buildings urban planning": "#9333ea",  # purple
    "mobility parking traffic": "#2563eb",  # blue
    "noise": "#dc2626",  # red
    "other unmapped": "#475569",  # slate
    "parks trees environment": "#0f766e",  # teal
    "public health pests": "#7c2d12",  # brown
    "public safety police": "#ea580c",  # orange
    "public space maintenance": "#65a30d",  # lime
    "sanitation cleaning waste": "#16a34a",  # green
    "social services homelessness": "#4f46e5",  # indigo
    "utilities water sewer": "#0891b2",  # cyan
    "unknown missing": DEFAULT_CATEGORY_COLOR,
}


EXTENDED_CATEGORY_PALETTE = [
    "#2563eb",  # blue
    "#dc2626",  # red
    "#16a34a",  # green
    "#9333ea",  # purple
    "#ea580c",  # orange
    "#0891b2",  # cyan
    "#ca8a04",  # amber
    "#be185d",  # magenta
    "#4f46e5",  # indigo
    "#65a30d",  # lime
    "#0f766e",  # teal
    "#7c2d12",  # brown
    "#a16207",  # ochre
    "#0e7490",  # dark cyan
    "#9d174d",  # dark pink
    "#334155",  # dark slate
]


def _category_key(value):
    category = _clean_category(value).lower()
    category = category.replace("&", " and ")

    import re as _re

    category = _re.sub(r"[^a-z0-9]+", " ", category)
    category = _re.sub(r"\s+", " ", category).strip()

    return category


def _stable_palette_index(category):
    import hashlib

    key = _category_key(category)
    digest = hashlib.md5(key.encode("utf-8")).hexdigest()

    return int(digest[:8], 16) % len(EXTENDED_CATEGORY_PALETTE)


def build_category_color_map(categories):
    """Return stable, readable colors for standardized service categories.

    Rules:
    - Exact standardized categories get explicit colors.
    - The same category gets the same color in every city.
    - Within a single map legend, avoid assigning the same color to different
      categories whenever the palette has enough available colors.
    """
    clean_categories = sorted({_clean_category(category) for category in categories})
    color_map = {}
    used_colors = set()

    # First pass: apply exact semantic category colors.
    for category in clean_categories:
        key = _category_key(category)

        if category == "Unknown / Missing":
            color = DEFAULT_CATEGORY_COLOR
        else:
            color = EXACT_CATEGORY_COLOR_BY_KEY.get(key)

        if color is None:
            continue

        color_map[category] = color
        used_colors.add(color)

    # Second pass: stable fallback with collision avoidance inside this legend.
    for category in clean_categories:
        if category in color_map:
            continue

        start_idx = _stable_palette_index(category)

        chosen_color = None
        for offset in range(len(EXTENDED_CATEGORY_PALETTE)):
            candidate = EXTENDED_CATEGORY_PALETTE[
                (start_idx + offset) % len(EXTENDED_CATEGORY_PALETTE)
            ]

            if candidate not in used_colors:
                chosen_color = candidate
                break

        if chosen_color is None:
            # Only happens if categories exceed palette size.
            chosen_color = EXTENDED_CATEGORY_PALETTE[start_idx]

        color_map[category] = chosen_color
        used_colors.add(chosen_color)

    return color_map


def add_category_legend(folium_map, category_color_map, title="Service category"):
    legend_rows = []

    for category, color in sorted(category_color_map.items()):
        safe_category = html_lib.escape(category)

        legend_rows.append(
            f"""
            <div style="display:flex; align-items:center; gap:8px; margin-bottom:4px;">
                <span style="
                    background:{color};
                    width:11px;
                    height:11px;
                    border-radius:50%;
                    display:inline-block;
                    border:1px solid #111827;
                    opacity:0.85;
                "></span>
                <span>{safe_category}</span>
            </div>
            """
        )

    legend_html = f"""
    <div style="
        position: fixed;
        bottom: 28px;
        left: 28px;
        z-index: 9999;
        background: rgba(255, 255, 255, 0.94);
        padding: 12px 14px;
        border: 1px solid #d1d5db;
        border-radius: 8px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.18);
        font-size: 12px;
        line-height: 1.25;
        max-width: 280px;
    ">
        <div style="font-weight:700; margin-bottom:8px;">{html_lib.escape(title)}</div>
        {''.join(legend_rows)}
    </div>
    """

    folium_map.get_root().html.add_child(folium.Element(legend_html))


def add_geospatial_coverage_caveat(
    folium_map,
    *,
    city_label,
    displayed_rows,
    geocoded_rows=None,
    total_2024_rows=None,
    sample_applied=False,
):
    safe_city = html_lib.escape(str(city_label))

    caveat_lines = [
        f"<strong>{safe_city} map coverage</strong>",
        f"Displayed points: {displayed_rows:,}",
    ]

    if geocoded_rows is not None:
        caveat_lines.append(f"Valid coordinate records: {geocoded_rows:,}")

    if total_2024_rows is not None and total_2024_rows > 0 and geocoded_rows is not None:
        coverage_pct = geocoded_rows / total_2024_rows * 100
        caveat_lines.append(
            f"Coordinate coverage: {coverage_pct:.1f}% of harmonized 2024 records"
        )

    caveat_lines.append("Only requests with valid latitude/longitude are shown.")

    if sample_applied:
        caveat_lines.append(
            "For browser performance, points are reproducibly sampled after coordinate filtering."
        )

    caveat_html = f"""
    <div style="
        position: fixed;
        top: 18px;
        right: 18px;
        z-index: 9999;
        background: rgba(255, 255, 255, 0.94);
        padding: 10px 12px;
        border: 1px solid #d1d5db;
        border-radius: 8px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.18);
        font-size: 12px;
        line-height: 1.35;
        max-width: 340px;
    ">
        {"<br>".join(caveat_lines)}
    </div>
    """

    folium_map.get_root().html.add_child(folium.Element(caveat_html))


# --- End Step 6D.1 helpers ---



DEFAULT_MAP_START_DATE = "2024-01-01"
DEFAULT_MAP_END_DATE = "2025-01-01"
DEFAULT_MAX_POINTS_PER_CITY = 8000

OUTPUT_DIR = Path("reports/maps")

CITY_OUTPUT_FILES = {
    "NYC": "nyc_service_request_map.html",
    "Barcelona": "barcelona_service_request_map.html",
}


def get_env_value(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if value is None or value == "":
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def build_engine():
    host = get_env_value("POSTGRES_HOST", "localhost")
    port = get_env_value("POSTGRES_PORT", "5433")
    db = get_env_value("POSTGRES_DB", "urban_service_equity")
    user = get_env_value("POSTGRES_USER", "urban_admin")
    password = get_env_value("POSTGRES_PASSWORD")

    url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"
    return create_engine(url)


def fetch_city_points(
    engine,
    city: str,
    start_date: str,
    end_date: str,
    max_points: int,
) -> pd.DataFrame:
    query = text(
        """
        select
            source_city,
            created_date,
            service_category_standardized,
            area_name,
            status,
            resolution_time_bucket,
            latitude,
            longitude
        from analytics.mart_request_map_points
        where source_city = :city
          and created_date >= cast(:start_date as date)
          and created_date < cast(:end_date as date)
          and latitude is not null
          and longitude is not null
          and latitude between -90 and 90
          and longitude between -180 and 180
        order by md5(
            concat_ws(
                '|',
                source_city::text,
                created_date::text,
                latitude::text,
                longitude::text,
                coalesce(service_category_standardized::text, ''),
                coalesce(area_name::text, ''),
                coalesce(status::text, '')
            )
        )
        limit :max_points
        """
    )

    return pd.read_sql(
        query,
        engine,
        params={
            "city": city,
            "start_date": start_date,
            "end_date": end_date,
            "max_points": max_points,
        },
    )


def build_popup(row: pd.Series) -> str:
    fields = {
        "City": row.get("source_city"),
        "Created date": row.get("created_date"),
        "Category": row.get("service_category_standardized"),
        "Area": row.get("area_name"),
        "Status": row.get("status"),
        "Resolution bucket": row.get("resolution_time_bucket"),
    }

    lines = []
    for label, value in fields.items():
        clean_value = "" if pd.isna(value) else html.escape(str(value))
        lines.append(f"<strong>{html.escape(label)}:</strong> {clean_value}")

    return "<br>".join(lines)


def export_city_map(
    city: str,
    df: pd.DataFrame,
    start_date: str,
    end_date: str,
    output_path: Path,
) -> None:
    if df.empty:
        raise RuntimeError(f"No geocoded map points returned for {city}.")

    center_lat = float(df["latitude"].median())
    center_lon = float(df["longitude"].median())

    title = (
        f"{city} Service Request Distribution — "
        f"2024 sampled geocoded records"
    )

    fmap = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=11,
        tiles="OpenStreetMap",
        control_scale=True,
    )

    title_html = f"""
    <div style="
        position: fixed;
        top: 10px;
        left: 50px;
        z-index: 9999;
        background: white;
        padding: 10px 14px;
        border: 1px solid #999;
        border-radius: 4px;
        font-size: 15px;
        box-shadow: 0 1px 4px rgba(0,0,0,0.25);
    ">
        <strong>{html.escape(title)}</strong><br>
        Shared comparison window: {html.escape(start_date)} to 2024-12-31<br>
        Displayed points: {len(df):,} deterministic sample
    </div>
    """
    fmap.get_root().html.add_child(folium.Element(title_html))

    category_color_map = build_category_color_map(
        df["service_category_standardized"]
        if "service_category_standardized" in df.columns
        else []
    )

    for _, row in df.iterrows():
        category = _clean_category(row.get("service_category_standardized"))
        marker_color = category_color_map.get(category, DEFAULT_CATEGORY_COLOR)
        folium.CircleMarker(
            location=[row["latitude"], row["longitude"]],
            radius=3,
            color=marker_color,
            weight=1,
            opacity=0.75,
            fill=True,
            fill_color=marker_color,
            fill_opacity=0.60,
            popup=folium.Popup(build_popup(row), max_width=350),
            tooltip=str(row.get("service_category_standardized") or "Service request"),
        ).add_to(fmap)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    _city_label = (
        locals().get("city_name")
        or locals().get("source_city")
        or locals().get("city")
        or locals().get("city_label")
        or "Selected city"
    )
    _display_df = locals().get("map_df", locals().get("df", None))
    _geo_obj = locals().get("geo_df", _display_df)
    _city_obj = locals().get("city_df", None)
    _sample_applied = bool(locals().get("sample_applied", False))

    add_category_legend(
        fmap,
        category_color_map,
        title="Service category",
    )

    add_geospatial_coverage_caveat(
        fmap,
        city_label=_city_label,
        displayed_rows=len(_display_df) if _display_df is not None else 0,
        geocoded_rows=len(_geo_obj) if _geo_obj is not None else None,
        total_2024_rows=len(_city_obj) if _city_obj is not None else None,
        sample_applied=_sample_applied,
    )

    fmap.save(output_path)


def main() -> None:
    load_dotenv()

    start_date = get_env_value("MAP_START_DATE", DEFAULT_MAP_START_DATE)
    end_date = get_env_value("MAP_END_DATE", DEFAULT_MAP_END_DATE)
    max_points = int(get_env_value("MAX_POINTS_PER_CITY", str(DEFAULT_MAX_POINTS_PER_CITY)))

    print("Folium map export configuration:")
    print(f"- start_date: {start_date}")
    print(f"- end_date: {end_date}")
    print(f"- max_points_per_city: {max_points:,}")
    print("- source mart: analytics.mart_request_map_points")

    engine = build_engine()

    for city, filename in CITY_OUTPUT_FILES.items():
        print(f"\nExporting {city} map...")
        df = fetch_city_points(
            engine=engine,
            city=city,
            start_date=start_date,
            end_date=end_date,
            max_points=max_points,
        )

        print(f"- returned points: {len(df):,}")
        if not df.empty:
            print(f"- first date: {df['created_date'].min()}")
            print(f"- last date: {df['created_date'].max()}")

        output_path = OUTPUT_DIR / filename
        export_city_map(
            city=city,
            df=df,
            start_date=start_date,
            end_date=end_date,
            output_path=output_path,
        )
        print(f"- wrote: {output_path}")

    print("\nFolium map export complete.")


if __name__ == "__main__":
    main()
