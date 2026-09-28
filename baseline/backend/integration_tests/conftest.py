import os
import subprocess
import sys
import time

import httpx
import pytest
from sqlmodel import Session

from g0.database import database_url

database_url()

from app.core.db import engine, init_db  # noqa: E402
from g0.migrate import migrate  # noqa: E402


@pytest.fixture(scope="session")
def api(tmp_path_factory):
    migrate()
    with Session(engine) as session:
        init_db(session)
    log_path = tmp_path_factory.mktemp("g0-http") / "api.log"
    with log_path.open("w+") as log:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "g0.api:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8091",
                "--no-access-log",
                "--log-level",
                "warning",
            ],
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            with httpx.Client(base_url="http://127.0.0.1:8091", timeout=10) as client:
                deadline = time.monotonic() + 20
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        log.seek(0)
                        pytest.fail("G0 API exited: " + log.read())
                    try:
                        if client.get("/health").status_code == 200:
                            break
                    except httpx.TransportError:
                        pass
                    time.sleep(0.1)
                else:
                    pytest.fail("G0 API did not become healthy")
                response = client.post(
                    "/api/v1/login/access-token",
                    data={
                        "username": os.environ["FIRST_SUPERUSER"],
                        "password": os.environ["FIRST_SUPERUSER_PASSWORD"],
                    },
                )
                response.raise_for_status()
                client.headers["Authorization"] = (
                    "Bearer " + response.json()["access_token"]
                )
                yield client
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


@pytest.fixture
def worker():
    def run() -> int:
        process = subprocess.Popen(
            [sys.executable, "-m", "g0.queue"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        try:
            output, _ = process.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate(timeout=5)
            pytest.fail("Worker did not release its slot")
        assert process.returncode == 0, output
        return process.pid

    return run
