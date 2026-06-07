import os
from pathlib import Path
import sys

import psycopg
import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _db_config() -> dict[str, str | int]:
    return {
        "host": os.getenv("POSTGRES_HOST", "127.0.0.1"),
        "port": int(os.getenv("POSTGRES_PORT", "15432")),
        "user": os.getenv("POSTGRES_USER", "postgres"),
        "password": os.getenv("POSTGRES_PASSWORD", "postgres"),
        "dbname": os.getenv("POSTGRES_DB", "agro_insight"),
    }


@pytest.fixture(scope="session")
def integration_db_ready() -> None:
    config = _db_config()
    migration_paths = sorted((ROOT / "database" / "migrations").glob("*.sql"))
    migration_sql = "\n".join(
        path.read_text(encoding="utf-8") for path in migration_paths
    )
    with psycopg.connect(**config) as conn:
        with conn.cursor() as cur:
            cur.execute("DROP SCHEMA IF EXISTS core CASCADE;")
            cur.execute(migration_sql)
            conn.commit()


@pytest.fixture()
def clean_core_tables(integration_db_ready: None) -> None:
    config = _db_config()
    with psycopg.connect(**config) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "TRUNCATE TABLE core.fields, core.farms, core.users RESTART IDENTITY CASCADE;"
            )
            conn.commit()
