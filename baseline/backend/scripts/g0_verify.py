"""Run upstream tests only against the explicitly isolated G0 database."""

import json
import os
import re
import subprocess
import sys
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from urllib.parse import urlsplit


def redact(value: str) -> str:
    for key in ("G0_DB_PASSWORD", "SECRET_KEY", "FIRST_SUPERUSER_PASSWORD"):
        if os.environ.get(key):
            value = value.replace(os.environ[key], "[REDACTED]")
    return re.sub(
        r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b",
        "[REDACTED_JWT]",
        value,
    )


def main() -> int:
    target = urlsplit(os.environ.get("DATABASE_URL", ""))
    if target.hostname != "db" or target.path != "/yibu_g0_test":
        raise RuntimeError("Refusing tests outside the isolated G0 database")
    evidence = Path("/evidence")
    evidence.mkdir(exist_ok=True)
    for path in evidence.rglob("*"):
        if path.is_file() and path.suffix in {".log", ".xml"}:
            old = path.read_text(encoding="utf-8")
            clean = redact(old)
            if old != clean:
                path.write_text(clean, encoding="utf-8")
    run = evidence / ("upstream-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ"))
    run.mkdir()
    os.environ["G0_REPORT_DIR"] = str(run)
    commands = [
        ["alembic", "upgrade", "head"],
        ["alembic", "current"],
        [
            sys.executable,
            "scripts/g0_pytest.py",
            f"--junitxml={run}/upstream-tests.xml",
        ],
    ]
    records = []
    status = 0
    for index, command in enumerate(commands, 1):
        result = subprocess.run(command, capture_output=True, text=True, timeout=600)
        log = redact(result.stdout + result.stderr)
        (run / f"upstream-{index}.log").write_text(log, encoding="utf-8")
        print(log, flush=True)  # noqa: T201 - Redacted CLI test output.
        records.append({"command": command, "exit_code": result.returncode})
        if result.returncode:
            status = result.returncode
            break
    report = {
        "kind": "upstream_baseline_only",
        "completed_at": datetime.now(UTC).isoformat(),
        "python": sys.version.split()[0],
        "dependency_versions": {
            name: version(name)
            for name in ("fastapi", "pydantic", "psycopg", "sqlmodel", "alembic", "pytest")
        },
        "commands": records,
        "passed": status == 0,
        "product_acceptance": False,
        "live_model_tested": False,
        "smtp_transport": "explicit_test_double_no_external_delivery",
        "evidence_directory": run.name,
    }
    xml = run / "upstream-tests.xml"
    if xml.exists():
        xml.write_text(redact(xml.read_text(encoding="utf-8")), encoding="utf-8")
    for destination in (run / "report.json", evidence / "upstream-report.json"):
        destination.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
