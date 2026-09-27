"""Run unmodified upstream assertions with explicitly isolated mail delivery."""

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


def main() -> int:
    with patch("emails.message.Message.send", return_value="G0_CAPTURE_ONLY") as send:
        result = int(pytest.main(["-q", "tests/", *sys.argv[1:]]))
        report = {
            "mode": "transport_test_double",
            "send_calls": send.call_count,
            "external_delivery_tested": False,
        }
        Path(os.environ["G0_REPORT_DIR"], "mail-isolation.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        if result == 0 and send.call_count != 2:
            raise RuntimeError("Expected upstream account creation and recovery mail paths")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
