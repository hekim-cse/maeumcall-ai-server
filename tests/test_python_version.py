import sys

import pytest

from scripts.check_python_version import required_python_version

pytestmark = pytest.mark.unit


def test_runtime_matches_repository_python_version():
    assert sys.version_info[:2] == required_python_version()
