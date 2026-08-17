from __future__ import annotations

import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYTHON_VERSION_FILE = PROJECT_ROOT / ".python-version"


def required_python_version() -> tuple[int, int]:
    configured = PYTHON_VERSION_FILE.read_text(encoding="utf-8").strip()
    if re.fullmatch(r"\d+\.\d+", configured) is None:
        raise RuntimeError(".python-version must contain an exact major.minor version")
    major, minor = configured.split(".")
    return int(major), int(minor)


def main() -> int:
    required = required_python_version()
    actual = sys.version_info[:2]
    if actual != required:
        print(
            "Python version mismatch: "
            f"required {required[0]}.{required[1]}, "
            f"running {actual[0]}.{actual[1]}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
