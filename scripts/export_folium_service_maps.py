from __future__ import annotations

import html
import os
from pathlib import Path

import folium
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "reports" / "maps"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

MAX_POINTS_PER_CITY = 8000


def get_database_url() -> str:
    load_dotenv(PROJECT_ROOT / ".env")

    user = os.getenv("POSTGRES_USER")
    password = os.getenv("POSTGRES_PASSWORD")
    db = os.getenv("POSTGRES_DB")
    port = os.getenv("POSTGRES_PORT", "5433")

    # From host machine, Docker exposes Postgres on localhost:${POSTGRES_PORT}
    host = os.getenv("POSTGRES_HOST", "localhost")

    missing = [
        name
        for name, value in {
            "POSTGRES_USER": user,
            "POSTGRES_PASSWORD": password,
            "POSTGRES_DB": db,
        }.items()
        if not value
    ]

    if missing:
        raise RuntimeError(f"Missing required .env variables: {', '.join(missing)}")

    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"


def find_table_schema(engine, table_name: str) -> str:
    query = text(
        """
        select table_schema
        from information_schema.tables
        where table_name = :table_name
          and table_schema not in ('pg_catalog', 'information_schema')
        order by
            case when table_schema = 'public' then 0 else 1 end,
            table_schema
        limit 1
        """
    )

    with engine.connect() as conn:
        result = conn.execute(query, {"table_name": table_name}).fetchone()

    if result is None:
        raise RuntimeError(f"Could not find table '{table_name}' in Postgres.")

    return result[0]


def load_city_points(engine, schema: str, city: str) -> pd.DataFrame:
    query = text(
        f"""
        select
            source_city,
            service_category_standardized,
            area_name,
            status,
            resolution_time_bucket,
            created_date,
            longitude,
            latitude
        from {schema}.mart_request_map_points
        where source_city = :city
          and longitude is not null
          and latitude is not null
          and longitude between -180 and 180
          and latitude between -90 and 90
        order by random()
        limit :max_points
        """
    )

    return pd.read_sql(
        query,
        engine,
        params={"city": city, "max_points": MAX_POINTS_PER_CITY},
    )


def safe_text(value) -> str:
    if pd.isna(value):
        return "Unknown"
    return html.escape(str(value))


def color_for_status(status: str) -> str:
    status_clean = str(status or "").strip().lower()

    if status_clean in {"closed", "resolved", "complete", "completed"}:
        return "green"

    if status_clean in {"open", "pending", "in progress", "assigned"}:
        return "red"

    return "blue"


def create_city_map(df: pd.DataFrame, city: str, output_path: Path) -> None:
    if df.empty:
        raise RuntimeError(f"No geocoded points found for city: {city}")

    center_lat = df["latitude"].median()
    center_lon = df["longitude"].median()

    fmap = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=12,
        tiles="CartoDB positron",
        control_scale=True,
    )

    title_html = f"""
    <div style="
        position: fixed;
        top: 12px;
        left: 50px;
        z-index: 9999;
        background: white;
        padding: 10px 14px;
        border: 1px solid #cccccc;
        border-radius: 6px;
        font-size: 16px;
        font-weight: bold;
        box-shadow: 0 1px 4px rgba(0,0,0,0.2);
    ">
        {safe_text(city)} Service Request Distribution
    </div>
    """
    fmap.get_root().html.add_child(folium.Element(title_html))

    legend_html = """
    <div style="
        position: fixed;
        bottom: 30px;
        left: 50px;
        z-index: 9999;
        background: white;
        padding: 10px 14px;
        border: 1px solid #cccccc;
        border-radius: 6px;
        font-size: 13px;
        box-shadow: 0 1px 4px rgba(0,0,0,0.2);
    ">
        <b>Status</b><br>
        <span style="color: green;">●</span> Closed / Resolved<br>
        <span style="color: red;">●</span> Open / Pending / In progress<br>
        <span style="color: blue;">●</span> Other / Unknown
    </div>
    """
    fmap.get_root().html.add_child(folium.Element(legend_html))

    for row in df.itertuples(index=False):
        tooltip = (
            f"<b>City:</b> {safe_text(row.source_city)}<br>"
            f"<b>Category:</b> {safe_text(row.service_category_standardized)}<br>"
            f"<b>Area:</b> {safe_text(row.area_name)}<br>"
            f"<b>Status:</b> {safe_text(row.status)}<br>"
            f"<b>Resolution bucket:</b> {safe_text(row.resolution_time_bucket)}<br>"
            f"<b>Created date:</b> {safe_text(row.created_date)}"
        )

        folium.CircleMarker(
            location=[row.latitude, row.longitude],
            radius=3,
            color=color_for_status(row.status),
            fill=True,
            fill_color=color_for_status(row.status),
            fill_opacity=0.65,
            opacity=0.65,
            tooltip=folium.Tooltip(tooltip, sticky=True),
        ).add_to(fmap)

    fmap.save(output_path)


def main() -> None:
    engine = create_engine(get_database_url())
    schema = find_table_schema(engine, "mart_request_map_points")

    print(f"Using table: {schema}.mart_request_map_points")

    city_outputs = {
        "NYC": OUTPUT_DIR / "nyc_service_request_map.html",
        "Barcelona": OUTPUT_DIR / "barcelona_service_request_map.html",
    }

    for city, output_path in city_outputs.items():
        df = load_city_points(engine, schema, city)
        print(f"{city}: loaded {len(df):,} points")

        create_city_map(df, city, output_path)
        print(f"Saved: {output_path}")


if __name__ == "__main__":
    main()
