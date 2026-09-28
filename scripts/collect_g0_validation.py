"""Export allowlisted, verifiable G0 results from a successful GitHub Actions run."""

import argparse
import json
from pathlib import Path
import re
import subprocess

REPOSITORY = "Ring0321/yibu-youju"


def gh(*args):
    return subprocess.run(
        ["gh", *args], check=True, capture_output=True, encoding="utf-8", timeout=120
    ).stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_id", type=int)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    meta = json.loads(gh("run", "view", str(args.run_id), "--repo", REPOSITORY,
                         "--json", "status,conclusion,headSha,url,jobs"))
    if meta["status"] != "completed" or meta["conclusion"] != "success":
        raise RuntimeError("Cannot publish a passing record for an unfinished or unsuccessful run")
    logs = gh("run", "view", str(args.run_id), "--repo", REPOSITORY, "--log")
    runtime = {}
    workflow = None
    migration = None
    upstream_count = None
    for line in logs.splitlines():
        parts = line.split("\t", 2)
        if len(parts) != 3:
            continue
        step, content = parts[1], parts[2]
        if step == "Run migration and upstream regression tests":
            match = re.search(r"\b(\d+) passed\b", content)
            if match:
                upstream_count = int(match.group(1))
        brace = content.find("{")
        if brace < 0:
            continue
        try:
            record = json.loads(content[brace:])
        except json.JSONDecodeError:
            continue
        if step == "Verify HTTP assets and persistence across database restart" and record.get("kind") == "upstream_http_persistence_only":
            runtime[record["phase"]] = {key: record[key] for key in (
                "passed", "item_id", "health_http", "static_http", "javascript_assets_checked",
                "read_http", "database_version", "database_started", "database_restart_verified",
            )}
        if step == "Verify durable checkpoints and actual queue workers" and record.get("kind") == "isolated_infrastructure_integration":
            workflow = {key: record[key] for key in (
                "passed", "counts", "versions", "python", "observations", "live_model_tested",
                "physical_device_tested", "crash_window_tested", "generation_fencing_tested",
                "persistent_call_budget_tested", "product_acceptance",
            )}
        if step == "Verify durable checkpoints and actual queue workers" and "checkpoint_migration" in record:
            migration = {"versions": record["versions"], "checkpoint_migration": record["checkpoint_migration"]}
    if not upstream_count or not workflow or not migration or set(runtime) != {"write", "read"}:
        raise RuntimeError("Required structured results are missing")
    if not all(record["passed"] for record in (*runtime.values(), workflow)):
        raise RuntimeError("A sub-probe did not pass")
    if runtime["write"]["item_id"] != runtime["read"]["item_id"] or not runtime["read"]["database_restart_verified"]:
        raise RuntimeError("Persistence evidence does not match")
    result = {
        "source": {"repository": REPOSITORY, "run_id": args.run_id, "commit": meta["headSha"], "url": meta["url"]},
        "environment": "GitHub-hosted ubuntu-24.04; isolated Docker Linux containers",
        "upstream_tests_passed": upstream_count, "runtime": runtime, "workflow": workflow, "migration": migration,
        "steps": [{"name": step["name"], "conclusion": step["conclusion"]}
                  for job in meta["jobs"] for step in job["steps"]],
        "scope": "G0 infrastructure only; not product or physical-device acceptance",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"run_id": args.run_id, "upstream_tests": upstream_count, "integration": workflow["counts"]}))


if __name__ == "__main__":
    main()
