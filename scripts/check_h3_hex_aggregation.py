#!/usr/bin/env python3

from pathlib import Path
import os

import h3
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text


DEFAULT_START_DATE = "2024-01-01"
DEFAULT_END_DATE = "2025-01-01"
DEFAULT_H3_RESOLUTION = 8


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


def main():
    start_date = os.getenv("HEX_MAP_START_DATE", DEFAULT_START_DATE)
    end_date = os.getenv("HEX_MAP_END_DATE", DEFAULT_END_DATE)
    h3_resolution = int(os.getenv("H3_RESOLUTION", DEFAULT_H3_RESOLUTION))

    engine = build_engine()

    query = text("""
        select
            source_city,
            request_id,
            latitude,
            longitude
        from analytics.mart_request_map_points
        where created_date >= :start_date
          and created_date < :end_date
          and has_geo = true
          and latitude is not null
          and longitude is not null
    """)

    df = pd.read_sql(
        query,
        engine,
        params={"start_date": start_date, "end_date": end_date},
    )

    if df.empty:
        raise SystemExit("No geocoded records found for the selected window.")

    df["h3_cell"] = df.apply(
        lambda row: h3.latlng_to_cell(
            float(row["latitude"]),
            float(row["longitude"]),
            h3_resolution,
        ),
        axis=1,
    )

    print("H3 aggregation diagnostic")
    print(f"Window: {start_date} to {end_date}")
    print(f"H3 resolution: {h3_resolution}")
    print()

    for city, city_df in df.groupby("source_city"):
        hex_counts = (
            city_df.groupby("h3_cell")
            .size()
            .reset_index(name="request_count")
        )

        print(city)
        print(f"  source points: {len(city_df):,}")
        print(f"  hex cells: {len(hex_counts):,}")
        print(f"  min requests per hex: {hex_counts['request_count'].min():,}")
        print(f"  median requests per hex: {hex_counts['request_count'].median():.1f}")
        print(f"  max requests per hex: {hex_counts['request_count'].max():,}")
        print()


if __name__ == "__main__":
    main()
