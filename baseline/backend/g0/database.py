import os
from urllib.parse import urlsplit

import psycopg
from psycopg.rows import dict_row

SERVICE_SCHEMA = "g0_service"
CHECKPOINT_SCHEMA = "g0_checkpoints"
QUEUE_SCHEMA = "g0_jobs"


def database_url() -> str:
    url = os.environ.get("DATABASE_URL", "")
    target = urlsplit(url)
    if (
        os.environ.get("YIBU_G0_PROBE") != "1"
        or target.scheme != "postgresql"
        or target.hostname != "db"
        or target.port not in (None, 5432)
        or target.path != "/yibu_g0_test"
        or target.username != "yibu_g0"
        or target.query
        or target.fragment
    ):
        raise RuntimeError("G0 requires explicit opt-in and its dedicated database")
    if any(
        os.environ.get(key, "").lower() not in ("", "false", "0")
        for key in ("LANGSMITH_TRACING", "LANGCHAIN_TRACING_V2")
    ):
        raise RuntimeError("External tracing must be disabled in G0")
    return url


def connect(*, schema: str = SERVICE_SCHEMA, autocommit: bool = False):
    if schema not in {SERVICE_SCHEMA, CHECKPOINT_SCHEMA, QUEUE_SCHEMA}:
        raise ValueError("Unexpected G0 schema")
    return psycopg.connect(
        database_url(),
        autocommit=autocommit,
        row_factory=dict_row,
        connect_timeout=5,
        options=f"-c search_path={schema} -c lock_timeout=5000 -c statement_timeout=15000",
    )
