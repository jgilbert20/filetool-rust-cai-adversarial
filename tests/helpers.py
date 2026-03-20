"""Shared helpers for the ft red-team test suite."""

import hashlib
import os
import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.text import Text

console = Console(highlight=False)

# ---------------------------------------------------------------------------
# Narration
# ---------------------------------------------------------------------------

_step_counter: dict[str, int] = {}


def narrate(title: str, detail: str = "", *, test_name: str = ""):
    """Print a narrated step to stdout for forensic paper-trail."""
    key = test_name or "global"
    _step_counter.setdefault(key, 0)
    _step_counter[key] += 1
    n = _step_counter[key]
    console.print(f"  [bold cyan][Step {n}][/bold cyan] {title}")
    if detail:
        for line in detail.strip().splitlines():
            console.print(f"           {line}")


def check(condition: bool, description: str, *, test_name: str = ""):
    """Assert with narrated pass/fail."""
    if condition:
        console.print(f"           [green]✓[/green] {description}")
    else:
        console.print(f"           [red]✗[/red] {description}")
        raise AssertionError(description)


class AssertionError(AssertionError if False else AssertionError):
    """Alias so we raise the real AssertionError for pytest."""
    pass


# Actually just use the builtin
def check(condition: bool, description: str, *, test_name: str = ""):
    if condition:
        console.print(f"           [green]✓[/green] {description}")
    else:
        console.print(f"           [red]✗[/red] {description}")
        assert False, description


# ---------------------------------------------------------------------------
# Running ft
# ---------------------------------------------------------------------------

@dataclass
class FtResult:
    stdout: str
    stderr: str
    exit_code: int
    cmd: list[str]


def run_ft(
    binary: Path,
    args: list[str],
    *,
    cwd: Optional[Path] = None,
    env: Optional[dict] = None,
    timeout: int = 30,
    stdin_data: Optional[str] = None,
) -> FtResult:
    """Run the ft binary and return captured output."""
    cmd = [str(binary)] + args
    run_env = dict(env) if env else {"HOME": os.environ.get("HOME", "/tmp"), "PATH": os.environ.get("PATH", "")}

    result = subprocess.run(
        cmd,
        cwd=cwd,
        env=run_env,
        capture_output=True,
        text=True,
        timeout=timeout,
        input=stdin_data,
    )
    return FtResult(
        stdout=result.stdout,
        stderr=result.stderr,
        exit_code=result.returncode,
        cmd=cmd,
    )


# ---------------------------------------------------------------------------
# File creation
# ---------------------------------------------------------------------------

def make_file(path: Path, content: bytes = b"", *, mtime: Optional[float] = None):
    """Create a file with given content and optional mtime."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    if mtime is not None:
        os.utime(path, (mtime, mtime))


def make_files(base: Path, spec: dict[str, bytes]):
    """Bulk-create files from {relative_path: content} dict."""
    for rel, content in spec.items():
        make_file(base / rel, content)


# ---------------------------------------------------------------------------
# Independent verification
# ---------------------------------------------------------------------------

def compute_sha256(path: Path) -> str:
    """Compute SHA-256 hex digest independently."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def compute_sha256_bytes(data: bytes) -> str:
    """Compute SHA-256 hex digest of raw bytes."""
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------
# Output parsers
# ---------------------------------------------------------------------------

@dataclass
class LsEntry:
    hash: str
    size_str: str
    tags: str
    path: str


def parse_ls_output(stdout: str) -> list[LsEntry]:
    """Parse ft ls output lines into structured entries."""
    entries = []
    for line in stdout.strip().splitlines():
        if not line.strip():
            continue
        # Format: <hash>  <size>  [tags]  <path>
        # Columns are aligned with variable whitespace
        # Size can be "12 B", "1.0 kB", "1.0 MB" etc.
        m = re.match(r"(\S+)\s+([\d.]+\s+\S+)\s+\[([^\]]*)\]\s+(.+)", line)
        if m:
            entries.append(LsEntry(
                hash=m.group(1),
                size_str=m.group(2).strip(),
                tags=m.group(3),
                path=m.group(4).strip(),
            ))
    return entries


@dataclass
class SnapRow:
    path: str
    dev: str
    ino: str
    size: str
    mtime_nsec: str
    ctime_nsec: str
    sha256: str
    tags: str
    imprinted_at: str


def parse_snap_tsv(stdout: str) -> list[SnapRow]:
    """Parse ft snap TSV output into structured rows."""
    rows = []
    lines = stdout.strip().splitlines()
    for line in lines:
        if line.startswith("#") or line.startswith("path\t"):
            continue
        fields = line.split("\t")
        if len(fields) >= 9:
            rows.append(SnapRow(*fields[:9]))
    return rows


@dataclass
class DiffEntry:
    status: str
    path_a: str
    path_b: str = ""
    detail: str = ""


def parse_diff_output(stdout: str) -> list[DiffEntry]:
    """Parse ft diff output into structured entries."""
    entries = []
    for line in stdout.strip().splitlines():
        if not line.strip():
            continue
        # Formats:
        #   new       path
        #   deleted   path
        #   renamed   old  →  new
        #   moved     old  →  new
        #   relocated old  →  new
        #   modified  path
        parts = line.split()
        if not parts:
            continue
        status = parts[0]
        if "→" in parts:
            arrow_idx = parts.index("→")
            path_a = " ".join(parts[1:arrow_idx])
            path_b = " ".join(parts[arrow_idx + 1:])
            entries.append(DiffEntry(status=status, path_a=path_a, path_b=path_b))
        else:
            path_a = " ".join(parts[1:])
            entries.append(DiffEntry(status=status, path_a=path_a))
    return entries


def parse_diff_tsv(stdout: str) -> list[dict]:
    """Parse ft diff --tsv output."""
    rows = []
    for line in stdout.strip().splitlines():
        if not line.strip():
            continue
        fields = line.split("\t")
        rows.append({
            "status": fields[0] if len(fields) > 0 else "",
            "path_a": fields[1] if len(fields) > 1 else "",
            "path_b": fields[2] if len(fields) > 2 else "",
            "detail": fields[3] if len(fields) > 3 else "",
        })
    return rows


def parse_stats(stderr: str) -> dict:
    """Parse -Q stats line from stderr."""
    for line in stderr.splitlines():
        if line.startswith("stats:"):
            pairs = re.findall(r"(\w[\w()]+)=(\S+)", line)
            return {k: v for k, v in pairs}
    return {}


def parse_diag(stderr: str) -> dict:
    """Parse FT_DIAG_SUMMARY line from stderr."""
    for line in stderr.splitlines():
        if "ft: diag:" in line:
            pairs = re.findall(r"(\w+)=(\d+)", line)
            return {k: int(v) for k, v in pairs}
    return {}


def get_file_paths_from_output(stdout: str) -> set[str]:
    """Extract just file paths from ls/lsdup/lsuniq output."""
    paths = set()
    for line in stdout.strip().splitlines():
        if not line.strip():
            continue
        # lsdup/lsuniq output is just paths, one per line
        # ls output has columns before the path
        # Try to parse as ls first
        entry = parse_ls_output(line)
        if entry:
            paths.add(entry[0].path)
        else:
            paths.add(line.strip())
    return paths


def get_paths_from_lines(stdout: str) -> list[str]:
    """Get simple path lines (for lsdup/lsuniq output)."""
    return [line.strip() for line in stdout.strip().splitlines() if line.strip()]
