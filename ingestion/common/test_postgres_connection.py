import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

host = os.getenv("POSTGRES_HOST", "localhost")
port = os.getenv("POSTGRES_PORT", "5433")
db = os.getenv("POSTGRES_DB", "urban_service_equity")
user = os.getenv("POSTGRES_USER", "urban_admin")
password = os.getenv("POSTGRES_PASSWORD", "urban_admin_password")

connection_url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"

engine = create_engine(connection_url)

with engine.connect() as conn:
    result = conn.execute(
        text("""
            SELECT schema_name
            FROM information_schema.schemata
            WHERE schema_name IN ('raw_nyc', 'raw_barcelona', 'analytics', 'public')
            ORDER BY schema_name;
        """)
    )

    print("Connected successfully.")
    print("Available project schemas:")
    for row in result:
        print(f"- {row.schema_name}")
