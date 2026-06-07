import os
from pathlib import Path
import subprocess

import pytest


pytestmark = pytest.mark.integration


def _run_psql(db_user: str, db_name: str, sql: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
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
            "-tAc",
            sql,
        ],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )


def _nonempty_stdout_lines(output: str) -> list[str]:
    return [line.strip() for line in output.splitlines() if line.strip()]


def test_core_entities_tables_geometry_and_foreign_keys_exist() -> None:
    db_user = os.getenv("POSTGRES_USER", "postgres")
    db_name = os.getenv("POSTGRES_DB", "agro_insight")
    migrations_dir = Path(__file__).resolve().parents[1] / "database" / "migrations"
    migration_paths = sorted(migrations_dir.glob("*.sql"))

    reset_schema_result = _run_psql(
        db_user,
        db_name,
        "DROP SCHEMA IF EXISTS core CASCADE;",
    )
    assert reset_schema_result.returncode == 0, (
        reset_schema_result.stdout + reset_schema_result.stderr
    )

    migration_sql = "\n".join(
        migration_path.read_text(encoding="utf-8") for migration_path in migration_paths
    )
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
        timeout=20,
        check=False,
    )
    assert migration_result.returncode == 0, (
        migration_result.stdout + migration_result.stderr
    )

    table_check = _run_psql(
        db_user,
        db_name,
        """
        SELECT COUNT(*)
        FROM information_schema.tables
        WHERE table_schema = 'core'
          AND table_name IN ('users', 'farms', 'fields');
        """,
    )
    assert table_check.returncode == 0, table_check.stdout + table_check.stderr
    assert table_check.stdout.strip() == "3"

    geometry_check = _run_psql(
        db_user,
        db_name,
        """
        SELECT COUNT(*)
        FROM information_schema.columns
        WHERE table_schema = 'core'
          AND table_name IN ('farms', 'fields')
          AND column_name = 'geometry'
          AND udt_name = 'geometry';
        """,
    )
    assert geometry_check.returncode == 0, geometry_check.stdout + geometry_check.stderr
    assert geometry_check.stdout.strip() == "2"

    fk_check = _run_psql(
        db_user,
        db_name,
        """
        SELECT conname || '|' || conrelid::regclass::text || '|' || confrelid::regclass::text
        FROM pg_constraint
        WHERE contype = 'f'
          AND conrelid IN ('core.users'::regclass, 'core.farms'::regclass, 'core.fields'::regclass)
        ORDER BY conname;
        """,
    )
    assert fk_check.returncode == 0, fk_check.stdout + fk_check.stderr
    assert _nonempty_stdout_lines(fk_check.stdout) == [
        "farms_user_fk|core.farms|core.users",
        "fields_farm_fk|core.fields|core.farms",
        "users_parent_user_fk|core.users|core.users",
    ]
