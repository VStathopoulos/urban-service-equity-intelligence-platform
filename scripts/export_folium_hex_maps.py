#!/usr/bin/env python3

from __future__ import annotations

import html
import os
from pathlib import Path

import folium
import h3
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text


DEFAULT_START_DATE = "2024-01-01"
DEFAULT_END_DATE = "2025-01-01"
DEFAULT_H3_RESOLUTION = 8
DEFAULT_MIN_HEX_REQUESTS = 5

OUTPUT_DIR = Path("reports/maps")

HEX_COLORS = [
    "#fef3c7",
    "#fde68a",
    "#fbbf24",
    "#f97316",
    "#dc2626",
    "#7f1d1d",
]


def env_value(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None or str(value).strip() == "":
        return default
    return str(value).strip()


def build_engine():
    env_path = Path(".env")
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)

    user = os.getenv("POSTGRES_USER", "urban_user")
    password = os.getenv("POSTGRES_PASSWORD", "urban_password")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    db = os.getenv("POSTGRES_DB", "urban_services")

    return create_engine(
        f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"
    )


def load_points(engine, start_date: str, end_date: str) -> pd.DataFrame:
    query = text("""
        select
            source_city,
            request_id,
            created_date,
            status,
            is_open,
            service_category_standardized,
            area_name,
            latitude,
            longitude,
            resolution_days,
            resolution_time_bucket,
            is_sla_breach_72h
        from analytics.mart_request_map_points
        where created_date >= :start_date
          and created_date < :end_date
          and has_geo = true
          and latitude is not null
          and longitude is not null
    """)

    return pd.read_sql(
        query,
        engine,
        params={"start_date": start_date, "end_date": end_date},
    )


def most_common(series: pd.Series) -> str:
    clean = series.dropna().astype(str).str.strip()
    clean = clean[clean != ""]
    if clean.empty:
        return "Unknown / Missing"
    return clean.value_counts().index[0]


def add_h3_cells(df: pd.DataFrame, resolution: int) -> pd.DataFrame:
    df = df.copy()
    df["h3_cell"] = df.apply(
        lambda row: h3.latlng_to_cell(
            float(row["latitude"]),
            float(row["longitude"]),
            resolution,
        ),
        axis=1,
    )
    return df


def aggregate_hexes(df: pd.DataFrame, min_hex_requests: int) -> pd.DataFrame:
    df = df.copy()
    df["is_open_numeric"] = df["is_open"].fillna(False).astype(int)
    df["is_sla_breach_72h_numeric"] = df["is_sla_breach_72h"].fillna(False).astype(int)

    hex_df = (
        df.groupby("h3_cell")
        .agg(
            request_count=("request_id", "count"),
            open_count=("is_open_numeric", "sum"),
            sla_breach_72h_count=("is_sla_breach_72h_numeric", "sum"),
            avg_resolution_days=("resolution_days", "mean"),
            median_resolution_days=("resolution_days", "median"),
            dominant_category=("service_category_standardized", most_common),
            dominant_area=("area_name", most_common),
            dominant_status=("status", most_common),
            dominant_resolution_bucket=("resolution_time_bucket", most_common),
        )
        .reset_index()
    )

    hex_df = hex_df[hex_df["request_count"] >= min_hex_requests].copy()

    if hex_df.empty:
        return hex_df

    hex_df["open_rate_pct"] = hex_df["open_count"] / hex_df["request_count"] * 100
    hex_df["sla_breach_72h_rate_pct"] = (
        hex_df["sla_breach_72h_count"] / hex_df["request_count"] * 100
    )

    return hex_df


def build_quantiles(hex_df: pd.DataFrame) -> list[float]:
    values = hex_df["request_count"]

    if values.empty:
        return []

    if values.nunique() == 1:
        only_value = float(values.iloc[0])
        return [only_value] * 5

    return [float(values.quantile(q)) for q in [0.20, 0.40, 0.60, 0.80, 0.95]]


def color_for_count(request_count: int, quantiles: list[float]) -> str:
    if not quantiles:
        return HEX_COLORS[0]

    if request_count <= quantiles[0]:
        return HEX_COLORS[0]
    if request_count <= quantiles[1]:
        return HEX_COLORS[1]
    if request_count <= quantiles[2]:
        return HEX_COLORS[2]
    if request_count <= quantiles[3]:
        return HEX_COLORS[3]
    if request_count <= quantiles[4]:
        return HEX_COLORS[4]
    return HEX_COLORS[5]


def popup_html(row: pd.Series) -> str:
    avg_resolution = row["avg_resolution_days"]
    median_resolution = row["median_resolution_days"]

    avg_text = "Not available" if pd.isna(avg_resolution) else f"{avg_resolution:.1f} days"
    median_text = (
        "Not available" if pd.isna(median_resolution) else f"{median_resolution:.1f} days"
    )

    return f"""
    <div style="font-family: Arial, sans-serif; width: 310px; line-height: 1.35;">
        <div style="font-weight:700; font-size:14px; margin-bottom:8px;">
            H3 request hotspot
        </div>
        <table style="width:100%; border-collapse:collapse; font-size:12px;">
            <tr><td><b>Requests</b></td><td>{int(row["request_count"]):,}</td></tr>
            <tr><td><b>Dominant category</b></td><td>{html.escape(str(row["dominant_category"]))}</td></tr>
            <tr><td><b>Dominant area</b></td><td>{html.escape(str(row["dominant_area"]))}</td></tr>
            <tr><td><b>Open rate</b></td><td>{row["open_rate_pct"]:.1f}%</td></tr>
            <tr><td><b>72h breach proxy</b></td><td>{row["sla_breach_72h_rate_pct"]:.1f}%</td></tr>
            <tr><td><b>Avg resolution</b></td><td>{avg_text}</td></tr>
            <tr><td><b>Median resolution</b></td><td>{median_text}</td></tr>
        </table>
        <div style="margin-top:8px; padding-top:6px; border-top:1px solid #e5e7eb; font-size:11px; color:#6b7280;">
            Aggregated from geocoded service-request points using H3 cells.
        </div>
    </div>
    """


def add_header(
    fmap: folium.Map,
    *,
    city: str,
    start_date: str,
    end_date: str,
    resolution: int,
    source_points: int,
    displayed_hexes: int,
):
    try:
        display_end = str((pd.to_datetime(end_date) - pd.Timedelta(days=1)).date())
    except Exception:
        display_end = end_date

    header = f"""
    <div style="
        position: fixed; top: 12px; left: 60px; z-index: 9999;
        background: rgba(255,255,255,0.96); padding: 12px 14px;
        border: 1px solid #d1d5db; border-radius: 8px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.18);
        font-size: 12px; line-height: 1.35; max-width: 420px;
    ">
        <div style="font-size:15px; font-weight:700; margin-bottom:4px;">
            {html.escape(city)} Service Request Hex Hotspots
        </div>
        <div>H3 aggregation of geocoded service requests</div>
        <div style="color:#4b5563; margin-top:4px;">
            Window: {html.escape(start_date)} to {html.escape(display_end)}
            · H3 resolution: {resolution}
        </div>
        <div style="color:#4b5563; margin-top:4px;">
            Source points: {source_points:,}
            · Displayed hexes: {displayed_hexes:,}
        </div>
    </div>
    """
    fmap.get_root().html.add_child(folium.Element(header))


def add_legend(fmap: folium.Map, quantiles: list[float]):
    labels = [
        f"≤ {quantiles[0]:.0f}",
        f"{quantiles[0]:.0f}–{quantiles[1]:.0f}",
        f"{quantiles[1]:.0f}–{quantiles[2]:.0f}",
        f"{quantiles[2]:.0f}–{quantiles[3]:.0f}",
        f"{quantiles[3]:.0f}–{quantiles[4]:.0f}",
        f"> {quantiles[4]:.0f}",
    ]

    rows = []
    for color, label in zip(HEX_COLORS, labels):
        rows.append(
            f"""
            <div style="display:flex; align-items:center; gap:8px; margin-bottom:4px;">
                <span style="background:{color}; width:14px; height:14px; display:inline-block; border:1px solid #111827;"></span>
                <span>{html.escape(label)} requests</span>
            </div>
            """
        )

    legend = f"""
    <div style="
        position: fixed; bottom: 28px; left: 28px; z-index: 9999;
        background: rgba(255,255,255,0.94); padding: 12px 14px;
        border: 1px solid #d1d5db; border-radius: 8px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.18);
        font-size: 12px; line-height: 1.25; max-width: 280px;
    ">
        <div style="font-weight:700; margin-bottom:8px;">Hex request density</div>
        {''.join(rows)}
    </div>
    """
    fmap.get_root().html.add_child(folium.Element(legend))


def add_caveat(fmap: folium.Map, min_hex_requests: int):
    caveat = f"""
    <div style="
        position: fixed; bottom: 28px; right: 28px; z-index: 9999;
        background: rgba(255,255,255,0.94); padding: 10px 12px;
        border: 1px solid #d1d5db; border-radius: 8px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.18);
        font-size: 12px; line-height: 1.35; max-width: 360px;
    ">
        <strong>Hex map caveat</strong><br>
        Hexes aggregate only records with valid latitude/longitude.<br>
        Cells with fewer than {min_hex_requests:,} requests are hidden.<br>
        Density reflects both request activity and geospatial coverage.
    </div>
    """
    fmap.get_root().html.add_child(folium.Element(caveat))


def export_city_hex_map(
    city: str,
    city_df: pd.DataFrame,
    *,
    start_date: str,
    end_date: str,
    resolution: int,
    min_hex_requests: int,
):
    city_df = add_h3_cells(city_df, resolution)
    hex_df = aggregate_hexes(city_df, min_hex_requests)

    if hex_df.empty:
        print(f"- skipped {city}: no hexes after min_hex_requests={min_hex_requests}")
        return

    center_lat = float(city_df["latitude"].mean())
    center_lon = float(city_df["longitude"].mean())

    fmap = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=11,
        tiles="cartodbpositron",
        control_scale=True,
    )

    quantiles = build_quantiles(hex_df)

    for _, row in hex_df.iterrows():
        boundary = h3.cell_to_boundary(row["h3_cell"])
        color = color_for_count(int(row["request_count"]), quantiles)

        folium.Polygon(
            locations=[list(point) for point in boundary],
            color="#111827",
            weight=0.4,
            opacity=0.45,
            fill=True,
            fill_color=color,
            fill_opacity=0.62,
            popup=folium.Popup(popup_html(row), max_width=380),
            tooltip=f'{int(row["request_count"]):,} requests · {row["dominant_category"]}',
        ).add_to(fmap)

    add_header(
        fmap,
        city=city,
        start_date=start_date,
        end_date=end_date,
        resolution=resolution,
        source_points=len(city_df),
        displayed_hexes=len(hex_df),
    )
    add_legend(fmap, quantiles)
    add_caveat(fmap, min_hex_requests)

    safe_city = city.lower().replace(" ", "_")
    output_path = OUTPUT_DIR / f"{safe_city}_service_request_hex_map.html"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fmap.save(output_path)

    print(f"- wrote: {output_path}")
    print(f"  source points: {len(city_df):,}")
    print(f"  displayed hexes: {len(hex_df):,}")


def main() -> int:
    start_date = env_value("HEX_MAP_START_DATE", DEFAULT_START_DATE)
    end_date = env_value("HEX_MAP_END_DATE", DEFAULT_END_DATE)
    resolution = int(env_value("H3_RESOLUTION", str(DEFAULT_H3_RESOLUTION)))
    min_hex_requests = int(env_value("MIN_HEX_REQUESTS", str(DEFAULT_MIN_HEX_REQUESTS)))

    engine = build_engine()
    points = load_points(engine, start_date, end_date)

    if points.empty:
        raise SystemExit("No geocoded records found for the selected hex-map window.")

    print("H3 hex map export")
    print(f"- window: {start_date} to {end_date}")
    print(f"- H3 resolution: {resolution}")
    print(f"- min requests per hex: {min_hex_requests}")
    print(f"- total source points: {len(points):,}")

    for city, city_df in points.groupby("source_city"):
        print(f"\nExporting {city}")
        export_city_hex_map(
            city,
            city_df,
            start_date=start_date,
            end_date=end_date,
            resolution=resolution,
            min_hex_requests=min_hex_requests,
        )

    print("\nH3 hex map export complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
