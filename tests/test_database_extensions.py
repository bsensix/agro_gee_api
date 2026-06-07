import os
from pathlib import Path
import subprocess

import pytest


pytestmark = pytest.mark.integration


def test_postgis_extension_is_enabled() -> None:
    db_user = os.getenv("POSTGRES_USER", "postgres")
    db_name = os.getenv("POSTGRES_DB", "agro_insight")
    migration_path = (
        Path(__file__).resolve().parents[1]
        / "database"
        / "migrations"
        / "0001_init.sql"
    )
    migration_sql = migration_path.read_text(encoding="utf-8")

    migration_result = subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "db",
            "psql",
            "-v",
            "ON_ERROR_STOP=1",
            "-U",
            db_user,
            "-d",
            db_name,
            "-f",
            "-",
        ],
        input=migration_sql,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    extension_result = subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "db",
            "psql",
            "-U",
            db_user,
            "-d",
            db_name,
            "-tAc",
            "SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'postgis');",
        ],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    schema_result = subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "db",
            "psql",
            "-U",
            db_user,
            "-d",
            db_name,
            "-tAc",
            "SELECT EXISTS(SELECT 1 FROM information_schema.schemata WHERE schema_name = 'core');",
        ],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    assert migration_result.returncode == 0, (
        migration_result.stdout + migration_result.stderr
    )
    assert extension_result.returncode == 0, (
        extension_result.stdout + extension_result.stderr
    )
    assert extension_result.stdout.strip() == "t"
    assert schema_result.returncode == 0, schema_result.stdout + schema_result.stderr
    assert schema_result.stdout.strip() == "t"
