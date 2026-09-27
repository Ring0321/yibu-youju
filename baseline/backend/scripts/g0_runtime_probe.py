"""Exercise upstream HTTP CRUD across separate API and database starts."""

import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from sqlmodel import Session, text

from app.core.db import engine, init_db


def main() -> None:
    phase = sys.argv[1]
    if phase not in {"write", "read"}:
        raise ValueError("Expected write or read phase")
    target = urlsplit(os.environ["DATABASE_URL"])
    if target.hostname != "db" or target.path != "/yibu_g0_test":
        raise RuntimeError("Refusing probe outside isolated G0 database")
    evidence = Path("/evidence")
    with Session(engine) as session:
        init_db(session)
        database_version = session.exec(text("select version()")).one()[0]
    process = subprocess.Popen(
        [
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
            "--no-access-log",
            "--log-level",
            "warning",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    report = {"kind": "upstream_http_persistence_only", "phase": phase, "passed": False}
    try:
        with httpx.Client(base_url="http://127.0.0.1:8000", timeout=10) as client:
            for _ in range(60):
                if process.poll() is not None:
                    raise RuntimeError("API process exited before ready")
                try:
                    health = client.get("/api/v1/utils/health-check/")
                    if health.status_code == 200:
                        break
                except httpx.TransportError:
                    pass
                time.sleep(0.5)
            else:
                raise RuntimeError("API health deadline exceeded")
            assert health.json() is True
            page = client.get("/")
            assert page.status_code == 200 and '<div id="root">' in page.text
            login = client.post(
                "/api/v1/login/access-token",
                data={
                    "username": os.environ["FIRST_SUPERUSER"],
                    "password": os.environ["FIRST_SUPERUSER_PASSWORD"],
                },
            )
            login.raise_for_status()
            headers = {"Authorization": "Bearer " + login.json()["access_token"]}
            marker = evidence / "runtime-marker.json"
            if phase == "write":
                response = client.post(
                    "/api/v1/items/",
                    headers=headers,
                    json={
                        "title": "G0 persistence marker",
                        "description": "Template probe only",
                    },
                )
                response.raise_for_status()
                item = response.json()
                marker.write_text(
                    json.dumps({"item_id": item["id"], "title": item["title"]}),
                    encoding="utf-8",
                )
            expected = json.loads(marker.read_text(encoding="utf-8"))
            response = client.get(
                "/api/v1/items/" + expected["item_id"], headers=headers
            )
            response.raise_for_status()
            assert response.json()["title"] == expected["title"]
            report.update(
                {
                    "passed": True,
                    "item_id": expected["item_id"],
                    "health_http": health.status_code,
                    "static_http": page.status_code,
                    "read_http": response.status_code,
                    "database_version": database_version,
                }
            )
    finally:
        process.terminate()
        try:
            output, _ = process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            output, _ = process.communicate()
        for key in ("G0_DB_PASSWORD", "SECRET_KEY", "FIRST_SUPERUSER_PASSWORD"):
            if os.environ.get(key):
                output = output.replace(os.environ[key], "[REDACTED]")
        (evidence / f"runtime-{phase}.log").write_text(output, encoding="utf-8")
        report["completed_at"] = datetime.now(UTC).isoformat()
        (evidence / f"runtime-{phase}.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        print(json.dumps(report), flush=True)  # noqa: T201 - CLI validation result.


if __name__ == "__main__":
    main()
