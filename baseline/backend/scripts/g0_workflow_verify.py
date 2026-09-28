"""Real PostgreSQL/API/Worker tests, kept separate from template and model tests."""

import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from xml.etree import ElementTree

from g0_verify import redact

from g0.database import database_url


def main() -> int:
    database_url()
    run = Path("/evidence") / (
        "workflow-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    )
    run.mkdir(parents=True)
    os.environ["G0_REPORT_DIR"] = str(run)
    commands = [
        [sys.executable, "-m", "g0.migrate"],
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "integration_tests",
            "-o",
            "junit_family=xunit1",
            f"--junitxml={run}/tests.xml",
        ],
    ]
    records = []
    code = 1
    for index, command in enumerate(commands):
        try:
            result = subprocess.run(
                command, capture_output=True, text=True, timeout=180
            )
            log, code = redact(result.stdout + result.stderr), result.returncode
        except subprocess.TimeoutExpired:
            log, code = "G0 process deadline exceeded", 124
        (run / f"step-{index}.log").write_text(log, encoding="utf-8")
        print(log, flush=True)  # noqa: T201 - redacted test output.
        records.append({"command": command, "exit_code": code})
        if code:
            break
    counts = {}
    observations = []
    xml = run / "tests.xml"
    if xml.exists():
        clean = redact(xml.read_text(encoding="utf-8"))
        xml.write_text(clean, encoding="utf-8")
        suites = ElementTree.fromstring(clean)
        counts = {
            key: sum(
                int(suite.attrib.get(key, 0)) for suite in suites.iter("testsuite")
            )
            for key in ("tests", "failures", "errors", "skipped")
        }
        allowed = {
            "waiting_seconds",
            "worker_processes",
            "saved_checkpoint",
            "resumed_checkpoint",
            "original_command",
        }
        observations = [
            {
                "test": case.attrib["name"],
                "name": item.attrib["name"],
                "value": item.attrib["value"],
            }
            for case in suites.iter("testcase")
            for item in case.findall("properties/property")
            if item.attrib.get("name") in allowed
        ]
    report = {
        "kind": "isolated_infrastructure_integration",
        "passed": code == 0,
        "completed_at": datetime.now(UTC).isoformat(),
        "counts": counts,
        "observations": observations,
        "versions": {
            name: version(name)
            for name in (
                "langgraph",
                "langgraph-checkpoint-postgres",
                "procrastinate",
                "psycopg",
                "fastapi",
            )
        },
        "python": sys.version.split()[0],
        "commands": records,
        "live_model_tested": False,
        "physical_device_tested": False,
        "crash_window_tested": False,
        "generation_fencing_tested": False,
        "persistent_call_budget_tested": False,
        "product_acceptance": False,
    }
    for destination in (run / "report.json", Path("/evidence/workflow-report.json")):
        destination.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report), flush=True)  # noqa: T201 - safe summary.
    return code


if __name__ == "__main__":
    raise SystemExit(main())
