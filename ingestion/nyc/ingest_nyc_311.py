import os
from datetime import datetime, timezone

import pandas as pd
import requests
from dotenv import load_dotenv
from sqlalchemy import create_engine, text


SELECT_COLUMNS = [
    "unique_key",
    "created_date",
    "closed_date",
    "agency",
    "agency_name",
    "complaint_type",
    "descriptor",
    "location_type",
    "incident_zip",
    "incident_address",
    "street_name",
    "cross_street_1",
    "cross_street_2",
    "address_type",
    "city",
    "status",
    "resolution_description",
    "borough",
    "latitude",
    "longitude",
    "open_data_channel_type",
]


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
    password = get_env_value("POSTGRES_PASSWORD", "urban_admin_password")

    url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"
    return create_engine(url)


def fetch_nyc_311_sample() -> pd.DataFrame:
    dataset_id = get_env_value("NYC_311_DATASET_ID", "erm2-nwe9")
    base_url = get_env_value("NYC_311_API_BASE_URL", "https://data.cityofnewyork.us/resource")
    limit = int(get_env_value("NYC_311_SAMPLE_LIMIT", "5000"))
    app_token = os.getenv("NYC_311_APP_TOKEN", "")

    endpoint = f"{base_url}/{dataset_id}.json"

    params = {
        "$select": ", ".join(SELECT_COLUMNS),
        "$limit": limit,
        "$order": "created_date DESC",
    }

    headers = {}
    if app_token:
        headers["X-App-Token"] = app_token

    response = requests.get(endpoint, params=params, headers=headers, timeout=120)
    response.raise_for_status()

    records = response.json()
    if not records:
        raise RuntimeError("NYC 311 API returned no records.")

    df = pd.DataFrame(records)

    df["ingested_at_utc"] = datetime.now(timezone.utc)
    df["source_system"] = "nyc_311"
    df["source_dataset_id"] = dataset_id

    return df


def clean_types(df: pd.DataFrame) -> pd.DataFrame:
    for col in ["created_date", "closed_date", "ingested_at_utc"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce", utc=True)

    for col in ["latitude", "longitude"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def load_to_postgres(df: pd.DataFrame) -> None:
    engine = build_engine()

    with engine.begin() as conn:
        conn.execute(text("create schema if not exists raw_nyc;"))

    df.to_sql(
        name="nyc_311_requests",
        con=engine,
        schema="raw_nyc",
        if_exists="replace",
        index=False,
        method="multi",
        chunksize=1000,
    )


def main() -> None:
    print("Fetching NYC 311 sample...")
    df = fetch_nyc_311_sample()
    df = clean_types(df)

    print(f"Fetched {len(df):,} rows and {len(df.columns):,} columns.")
    print("Loading to raw_nyc.nyc_311_requests...")
    load_to_postgres(df)

    print("NYC 311 sample ingestion complete.")


if __name__ == "__main__":
    main()
