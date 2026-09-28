"""Read-only checks for common accidental disclosures and local Markdown links."""

import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", ".ruff_cache"}
TEXT_SUFFIXES = {".md", ".py", ".ps1", ".json", ".yaml", ".yml", ".toml", ".lock", ".ts", ".tsx", ".sh", ".puml", ".ini", ".html", ".svg"}
RULES = {
    "private-key": re.compile(r"-----BEGIN " + r"(?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "github-token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b"),
    "api-token": re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{24,}\b"),
    "aws-key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "jwt": re.compile(r"\beyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\b"),
    "machine-user-path": re.compile(r"[A-Za-z]:[/\\]Users[/\\](?!Public\b|Default\b|<)[A-Za-z0-9_.-]+[/\\]"),
}
LINK = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")


def publication_files():
    if (ROOT / ".git").exists():
        result = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            cwd=ROOT, check=True, capture_output=True,
        )
        return sorted({ROOT / name.decode("utf-8") for name in result.stdout.split(b"\0") if name})
    return sorted(ROOT.rglob("*"))


def main() -> int:
    issues = []
    scanned = 0
    for path in publication_files():
        relative = path.relative_to(ROOT)
        if any(part in SKIP_DIRS for part in relative.parts):
            continue
        if path.is_symlink():
            issues.append((str(relative), "symlink", 0))
            continue
        if not path.is_file():
            continue
        scanned += 1
        if path.name.startswith(".env") and not path.name.endswith(".example"):
            issues.append((str(relative), "environment-file", 0))
        if path.suffix.lower() in {".pem", ".key", ".p12", ".pfx", ".db", ".sqlite", ".log"}:
            issues.append((str(relative), "private-runtime-file", 0))
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in {"LICENSE", ".gitignore", ".dockerignore"}:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            issues.append((str(relative), "unexpected-non-utf8-text", 0))
            continue
        for rule, pattern in RULES.items():
            for match in pattern.finditer(content):
                issues.append((str(relative), rule, content.count("\n", 0, match.start()) + 1))
        # Imported upstream prose can refer to unbundled upstream deployment files.
        check_links = path.suffix == ".md" and (relative.parts[0] != "baseline" or relative.as_posix() == "baseline/README.md")
        if check_links:
            for match in LINK.finditer(content):
                raw = match.group(1).strip().strip("<>")
                if not raw or raw.startswith("#") or urlsplit(raw).scheme:
                    continue
                target = (path.parent / unquote(raw.split("#", 1)[0])).resolve()
                if not target.is_relative_to(ROOT) or not target.exists():
                    issues.append((str(relative), "missing-local-link", content.count("\n", 0, match.start()) + 1))
    manifest = json.loads((ROOT / "SOURCE_MANIFEST.json").read_text(encoding="utf-8"))
    for entry in manifest["files"]:
        path = ROOT / entry["destination"]
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != entry["published_sha256"]:
            issues.append((entry["destination"], "export-hash-mismatch", 0))
    for file, rule, line in issues:
        print(f"{file}:{line}: {rule}")
    print(json.dumps({"files_scanned": scanned, "issues": len(issues), "scope": "heuristic_publication_hygiene_not_full_security_audit"}))
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
