"""Refresh explicitly named imported files while retaining their import fingerprints."""

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+")
    args = parser.parse_args()
    path = ROOT / "SOURCE_MANIFEST.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    entries = {entry["destination"]: entry for entry in manifest["files"]}
    if any(name not in entries for name in args.paths):
        parser.error("Only existing, explicitly named import records can be refreshed")
    for name in args.paths:
        entry = entries[name]
        digest = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        if digest != entry["published_sha256"]:
            entry.setdefault("exported_sha256", entry["published_sha256"])
            entry["published_sha256"] = digest
            entry["modified_after_export"] = True
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
