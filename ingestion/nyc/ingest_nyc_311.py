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


def get_optional_env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name, default)
    if value is None:
        return None

    value = value.strip()
    if value == "":
        return None

    return value


def get_optional_int(name: str, default: str | None = None) -> int | None:
    value = get_optional_env(name, default)
    if value is None:
        return None

    return int(value)


def build_engine():
    host = get_env_value("POSTGRES_HOST", "localhost")
    port = get_env_value("POSTGRES_PORT", "5433")
    db = get_env_value("POSTGRES_DB", "urban_service_equity")
    user = get_env_value("POSTGRES_USER", "urban_admin")
    password = get_env_value("POSTGRES_PASSWORD")

    url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"
    return create_engine(url)


def build_where_clause(start_date: str | None, end_date: str | None) -> str | None:
    conditions: list[str] = []

    if start_date:
        conditions.append(f"created_date >= '{start_date}T00:00:00'")

    if end_date:
        conditions.append(f"created_date < '{end_date}T00:00:00'")

    if not conditions:
        return None

    return " AND ".join(conditions)


def clean_types(df: pd.DataFrame) -> pd.DataFrame:
    for col in ["created_date", "closed_date", "ingested_at_utc"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce", utc=True)

    for col in ["latitude", "longitude"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def prepare_raw_table(engine) -> None:
    with engine.begin() as conn:
        conn.execute(text("create schema if not exists raw_nyc;"))
        conn.execute(text("drop view if exists intermediate.int_service_requests_canonical cascade;"))
        conn.execute(text("drop view if exists staging.stg_nyc_311_requests cascade;"))
        conn.execute(text("drop table if exists raw_nyc.nyc_311_requests cascade;"))


def fetch_page(
    endpoint: str,
    dataset_id: str,
    headers: dict[str, str],
    where_clause: str | None,
    limit: int,
    offset: int,
) -> pd.DataFrame:
    params = {
        "$select": ", ".join(SELECT_COLUMNS),
        "$limit": limit,
        "$offset": offset,
        "$order": "created_date ASC",
    }

    if where_clause:
        params["$where"] = where_clause

    response = requests.get(endpoint, params=params, headers=headers, timeout=180)
    response.raise_for_status()

    records = response.json()
    df = pd.DataFrame(records)

    if df.empty:
        return df

    df["ingested_at_utc"] = datetime.now(timezone.utc)
    df["source_system"] = "nyc_311"
    df["source_dataset_id"] = dataset_id

    return clean_types(df)


def write_page(df: pd.DataFrame, engine, if_exists: str) -> None:
    df.to_sql(
        name="nyc_311_requests",
        con=engine,
        schema="raw_nyc",
        if_exists=if_exists,
        index=False,
        method="multi",
        chunksize=1000,
    )


def ingest_nyc_311() -> int:
    dataset_id = get_env_value("NYC_311_DATASET_ID", "fhrw-4uyv")
    base_url = get_env_value("NYC_311_API_BASE_URL", "https://data.cityofnewyork.us/resource")
    start_date = get_optional_env("NYC_311_START_DATE", "2024-01-01")
    end_date = get_optional_env("NYC_311_END_DATE", "2025-01-01")
    sample_limit = get_optional_int("NYC_311_SAMPLE_LIMIT", "5000")
    page_size = int(get_env_value("NYC_311_PAGE_SIZE", "50000"))
    app_token = get_optional_env("NYC_311_APP_TOKEN")

    if sample_limit is None and (start_date is None or end_date is None):
        raise ValueError(
            "Full NYC ingestion requires NYC_311_START_DATE and NYC_311_END_DATE "
            "to avoid accidentally loading an unbounded dataset."
        )

    endpoint = f"{base_url}/{dataset_id}.json"
    where_clause = build_where_clause(start_date, end_date)

    headers = {}
    if app_token:
        headers["X-App-Token"] = app_token

    print("NYC 311 ingestion configuration:")
    print(f"- endpoint: {endpoint}")
    print(f"- start_date: {start_date}")
    print(f"- end_date: {end_date}")
    print(f"- sample_limit: {sample_limit if sample_limit is not None else 'FULL WINDOW'}")
    print(f"- page_size: {page_size}")
    print(f"- where_clause: {where_clause}")

    engine = build_engine()
    prepare_raw_table(engine)

    total_rows = 0
    offset = 0
    first_write = True

    while True:
        remaining = None if sample_limit is None else sample_limit - total_rows
        if remaining is not None and remaining <= 0:
            break

        current_limit = page_size if remaining is None else min(page_size, remaining)

        print(f"Fetching NYC page: offset={offset:,}, limit={current_limit:,}")
        page_df = fetch_page(
            endpoint=endpoint,
            dataset_id=dataset_id,
            headers=headers,
            where_clause=where_clause,
            limit=current_limit,
            offset=offset,
        )

        if page_df.empty:
            if total_rows == 0:
                raise RuntimeError("NYC 311 API returned no records.")
            break

        write_page(page_df, engine, if_exists="replace" if first_write else "append")

        page_rows = len(page_df)
        total_rows += page_rows
        offset += page_rows
        first_write = False

        print(f"Loaded page rows: {page_rows:,}; total loaded: {total_rows:,}")

        if page_rows < current_limit:
            break

    return total_rows


def main() -> None:
    load_dotenv()

    total_rows = ingest_nyc_311()

    print(f"NYC 311 ingestion complete. Loaded {total_rows:,} rows.")


if __name__ == "__main__":
    main()
