import os
import re
from datetime import datetime, timezone

import pandas as pd
from dotenv import load_dotenv
from pyproj import Transformer
from sqlalchemy import create_engine, text


SOURCE_CRS = "EPSG:25831"  # ETRS89 / UTM zone 31N
TARGET_CRS = "EPSG:4326"   # WGS84 longitude / latitude


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


def normalize_column_name(column_name: str) -> str:
    column_name = column_name.strip().lower()
    column_name = re.sub(r"[^a-z0-9]+", "_", column_name)
    column_name = re.sub(r"_+", "_", column_name)
    return column_name.strip("_")


def make_unique_columns(columns: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    output: list[str] = []

    for column in columns:
        base = normalize_column_name(column) or "unnamed_column"
        count = seen.get(base, 0)

        if count == 0:
            output.append(base)
        else:
            output.append(f"{base}_{count + 1}")

        seen[base] = count + 1

    return output


def clean_numeric_series(series: pd.Series) -> pd.Series:
    return pd.to_numeric(
        series.astype(str)
        .str.replace('"', "", regex=False)
        .str.replace(",", ".", regex=False)
        .str.strip()
        .replace({"": None, "nan": None, "None": None}),
        errors="coerce",
    )


def add_wgs84_coordinates(df: pd.DataFrame) -> pd.DataFrame:
    if "coordenada_x" not in df.columns or "coordenada_y" not in df.columns:
        df["coordinate_x_etrs89"] = pd.NA
        df["coordinate_y_etrs89"] = pd.NA
        df["longitude_derived"] = pd.NA
        df["latitude_derived"] = pd.NA
        df["coordinate_source_crs"] = SOURCE_CRS
        df["coordinate_target_crs"] = TARGET_CRS
        return df

    df["coordinate_x_etrs89"] = clean_numeric_series(df["coordenada_x"])
    df["coordinate_y_etrs89"] = clean_numeric_series(df["coordenada_y"])

    transformer = Transformer.from_crs(SOURCE_CRS, TARGET_CRS, always_xy=True)

    valid_mask = df["coordinate_x_etrs89"].notna() & df["coordinate_y_etrs89"].notna()

    df["longitude_derived"] = pd.NA
    df["latitude_derived"] = pd.NA

    if valid_mask.any():
        lon, lat = transformer.transform(
            df.loc[valid_mask, "coordinate_x_etrs89"].to_numpy(),
            df.loc[valid_mask, "coordinate_y_etrs89"].to_numpy(),
        )
        df.loc[valid_mask, "longitude_derived"] = lon
        df.loc[valid_mask, "latitude_derived"] = lat

    df["coordinate_source_crs"] = SOURCE_CRS
    df["coordinate_target_crs"] = TARGET_CRS

    return df


def fetch_barcelona_iris_sample() -> pd.DataFrame:
    source_url = get_env_value("BARCELONA_IRIS_SOURCE_URL")
    limit = int(get_env_value("BARCELONA_IRIS_SAMPLE_LIMIT", "5000"))

    print(f"Reading Barcelona IRIS CSV sample from: {source_url}")
    print(f"Sample limit: {limit:,} rows")

    df = pd.read_csv(
        source_url,
        sep=None,
        engine="python",
        nrows=limit,
        encoding="utf-8",
        on_bad_lines="warn",
    )

    if df.empty:
        raise RuntimeError("Barcelona IRIS CSV returned no records.")

    original_columns = list(df.columns)
    df.columns = make_unique_columns(original_columns)

    df = add_wgs84_coordinates(df)

    df["ingested_at_utc"] = datetime.now(timezone.utc)
    df["source_system"] = "barcelona_iris"
    df["source_url"] = source_url

    print("Original columns:")
    for col in original_columns:
        print(f"- {col}")

    print("Normalized columns:")
    for col in df.columns:
        print(f"- {col}")

    print("Coordinate conversion summary:")
    print(f"- rows with source coordinates: {df['coordinate_x_etrs89'].notna().sum():,}")
    print(f"- rows with derived longitude/latitude: {df['longitude_derived'].notna().sum():,}")

    return df


def load_to_postgres(df: pd.DataFrame) -> None:
    engine = build_engine()

    with engine.begin() as conn:
        conn.execute(text("create schema if not exists raw_barcelona;"))
        conn.execute(text("drop view if exists intermediate.int_service_requests_canonical cascade;"))
        conn.execute(text("drop view if exists staging.stg_barcelona_iris_requests cascade;"))
        conn.execute(text("drop table if exists raw_barcelona.barcelona_iris_requests cascade;"))

    df.to_sql(
        name="barcelona_iris_requests",
        con=engine,
        schema="raw_barcelona",
        if_exists="replace",
        index=False,
        method="multi",
        chunksize=1000,
    )


def main() -> None:
    load_dotenv()

    print("Fetching Barcelona IRIS sample...")
    df = fetch_barcelona_iris_sample()

    print(f"Fetched {len(df):,} rows and {len(df.columns):,} columns.")
    print("Loading to raw_barcelona.barcelona_iris_requests...")
    load_to_postgres(df)

    print("Barcelona IRIS sample ingestion complete.")


if __name__ == "__main__":
    main()
