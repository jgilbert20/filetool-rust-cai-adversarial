"""Root conftest — provides the --ft-binary option and core fixtures."""

import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--ft-binary",
        action="store",
        default=None,
        help="Absolute or relative path to the ft binary under test",
    )


@dataclass
class IsolatedEnv:
    """A fully-isolated environment for one test."""

    root: Path  # top-level temp dir
    home: Path  # fake $HOME
    work: Path  # default CWD for ft invocations
    env: dict  # minimal env dict (HOME + PATH only)


@pytest.fixture(scope="session")
def ft_binary(request):
    raw = request.config.getoption("--ft-binary")
    if raw is None:
        # Auto-detect: look next to this conftest
        candidate = Path(__file__).resolve().parent / "binaries-to-test" / "ft-linux-cai"
        if candidate.exists():
            raw = str(candidate)
        else:
            pytest.skip("--ft-binary not provided and no default binary found")
    p = Path(raw).resolve()
    if not p.exists():
        pytest.fail(f"ft binary not found: {p}")
    if not os.access(p, os.X_OK):
        pytest.fail(f"ft binary not executable: {p}")
    return p


@pytest.fixture
def isolated_env(tmp_path):
    """Create a fully-isolated env: fake HOME, work dir, clean env dict."""
    home = tmp_path / "home"
    home.mkdir()
    work = tmp_path / "work"
    work.mkdir()

    env = {
        "HOME": str(home),
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
    }

    yield IsolatedEnv(root=tmp_path, home=home, work=work, env=env)
