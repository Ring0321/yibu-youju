"""Versioned, repeatable setup only for the explicitly isolated G0 database."""

import hashlib
import json
from importlib.metadata import version
from pathlib import Path

from langgraph.checkpoint.postgres import PostgresSaver
from procrastinate.schema import SchemaManager
from psycopg import sql

from g0.database import CHECKPOINT_SCHEMA, QUEUE_SCHEMA, SERVICE_SCHEMA, connect


def migrate() -> dict:
    schema_sql = Path(__file__).with_name("schema_v1.sql").read_text(encoding="utf-8")
    queue_sql = SchemaManager.get_schema()
    versions = {
        name: version(name)
        for name in (
            "langgraph",
            "langgraph-checkpoint-postgres",
            "procrastinate",
            "psycopg",
        )
    }
    with connect(autocommit=True) as conn:
        # This session lock covers both transactional DDL and saver autocommit migrations.
        conn.execute("SELECT pg_advisory_lock(2040928001)")
        try:
            with conn.transaction():
                for schema in (SERVICE_SCHEMA, CHECKPOINT_SCHEMA, QUEUE_SCHEMA):
                    conn.execute(
                        sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(
                            sql.Identifier(schema)
                        )
                    )
                conn.execute("""CREATE TABLE IF NOT EXISTS g0_service.migrations (
                    component text PRIMARY KEY, version text NOT NULL, sha256 text NOT NULL
                )""")
                for component, revision, source in (
                    ("service", "1", schema_sql),
                    ("queue", versions["procrastinate"], queue_sql),
                ):
                    digest = hashlib.sha256(source.encode()).hexdigest()
                    previous = conn.execute(
                        "SELECT version, sha256 FROM g0_service.migrations WHERE component = %s",
                        (component,),
                    ).fetchone()
                    if previous:
                        if previous != {"version": revision, "sha256": digest}:
                            raise RuntimeError(
                                "An explicit versioned migration is required"
                            )
                        continue
                    if component == "queue":
                        conn.execute("SET LOCAL search_path TO g0_jobs")
                    conn.execute(source, prepare=False)
                    conn.execute("SET LOCAL search_path TO g0_service")
                    conn.execute(
                        "INSERT INTO g0_service.migrations VALUES (%s, %s, %s)",
                        (component, revision, digest),
                    )
            with connect(schema=CHECKPOINT_SCHEMA, autocommit=True) as checkpoint_conn:
                PostgresSaver(checkpoint_conn).setup()
            checkpoint_version = conn.execute(
                "SELECT max(v) AS version FROM g0_checkpoints.checkpoint_migrations"
            ).fetchone()["version"]
            return {"versions": versions, "checkpoint_migration": checkpoint_version}
        finally:
            conn.execute("SELECT pg_advisory_unlock(2040928001)")


if __name__ == "__main__":
    print(json.dumps(migrate()))  # noqa: T201 - safe migration metadata only.
