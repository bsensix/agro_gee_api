import os
from contextlib import contextmanager
from typing import Iterator

import psycopg
from psycopg.rows import dict_row


def _db_config() -> dict[str, str | int]:
    return {
        "host": os.getenv("POSTGRES_HOST", "127.0.0.1"),
        "port": int(os.getenv("POSTGRES_PORT", "15432")),
        "user": os.getenv("POSTGRES_USER", "postgres"),
        "password": os.getenv("POSTGRES_PASSWORD", "postgres"),
        "dbname": os.getenv("POSTGRES_DB", "agro_insight"),
        "connect_timeout": int(os.getenv("POSTGRES_CONNECT_TIMEOUT", "5")),
    }


@contextmanager
def get_connection() -> Iterator[psycopg.Connection]:
    with psycopg.connect(**_db_config(), row_factory=dict_row) as connection:
        yield connection
