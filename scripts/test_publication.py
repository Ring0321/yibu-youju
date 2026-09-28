import contextlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import check_publication


class PublicationTests(unittest.TestCase):
    def setUp(self):
        local = Path(__file__).resolve().parents[1] / ".local"
        local.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="publication-test-", dir=local)
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        subprocess.run(["git", "init", "--quiet", str(self.root)], check=True)
        (self.root / ".gitignore").write_text(".env.*\nevidence/\n", encoding="utf-8")
        (self.root / "SOURCE_MANIFEST.json").write_text(json.dumps({"files": []}), encoding="utf-8")

    def check(self):
        with patch.object(check_publication, "ROOT", self.root), contextlib.redirect_stdout(io.StringIO()) as output:
            result = check_publication.main()
        return result, output.getvalue()

    def test_ignored_local_config_is_not_publication_content(self):
        (self.root / ".env.g0").write_text("TEST_ONLY=value\n", encoding="utf-8")
        self.assertEqual(self.check()[0], 0)

    def test_force_staged_config_is_still_rejected(self):
        (self.root / ".env.g0").write_text("TEST_ONLY=value\n", encoding="utf-8")
        subprocess.run(["git", "add", "--force", ".env.g0"], cwd=self.root, check=True)
        code, output = self.check()
        self.assertEqual(code, 1)
        self.assertIn("environment-file", output)

    def test_new_untracked_source_is_scanned(self):
        token = "sk-" + "x" * 30
        (self.root / "leak.py").write_text(f"test_value = {token!r}\n", encoding="utf-8")
        code, output = self.check()
        self.assertEqual(code, 1)
        self.assertIn("api-token", output)
        self.assertNotIn(token, output)

    def test_import_hash_mismatch_fails(self):
        (self.root / "imported.md").write_text("changed", encoding="utf-8")
        (self.root / "SOURCE_MANIFEST.json").write_text(json.dumps({"files": [
            {"destination": "imported.md", "published_sha256": "0" * 64}
        ]}), encoding="utf-8")
        code, output = self.check()
        self.assertEqual(code, 1)
        self.assertIn("export-hash-mismatch", output)

    def test_missing_relative_link_is_rejected(self):
        (self.root / "README.md").write_text("[missing](absent.md)", encoding="utf-8")
        code, output = self.check()
        self.assertEqual(code, 1)
        self.assertIn("missing-local-link", output)


if __name__ == "__main__":
    unittest.main()
