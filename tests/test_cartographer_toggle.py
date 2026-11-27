"""Include feature-local tests in the repository's standard unittest discovery."""

import importlib.util
import sys
from pathlib import Path


def load_tests(loader, tests, pattern):
    path = (
        Path(__file__).resolve().parents[1]
        / "features/cartographer-toggle/tests/test_toggle.py"
    )
    sys.path.insert(0, str(path.parents[3] / "backend"))
    sys.path.insert(0, str(path.parents[1]))
    spec = importlib.util.spec_from_file_location("cartographer_toggle_tests", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return loader.loadTestsFromModule(module)
