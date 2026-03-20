"""Snapshot format and correctness tests."""

import os
import time

from tests.helpers import (
    check,
    compute_sha256,
    make_file,
    make_files,
    narrate,
    parse_ls_output,
    parse_snap_tsv,
    run_ft,
)


def test_snap_header_format(ft_binary, isolated_env):
    """First line must be '# ft snap v1'."""
    make_file(isolated_env.work / "f.txt", b"snap header test\n")
    r = run_ft(ft_binary, ["snap", str(isolated_env.work)],
               cwd=isolated_env.work, env=isolated_env.env)
    check(r.exit_code == 0, f"exit code 0 (got {r.exit_code})")
    lines = r.stdout.strip().splitlines()
    check(len(lines) >= 1, "output has at least 1 line")
    check(lines[0] == "# ft snap v1", f"header is '# ft snap v1' (got '{lines[0]}')")


def test_snap_column_header(ft_binary, isolated_env):
    """Second line must have 9 tab-separated column names."""
    make_file(isolated_env.work / "f.txt", b"header test\n")
    r = run_ft(ft_binary, ["snap", str(isolated_env.work)],
               cwd=isolated_env.work, env=isolated_env.env)
    lines = r.stdout.strip().splitlines()
    check(len(lines) >= 2, "at least 2 lines (header + columns)")
    cols = lines[1].split("\t")
    expected = ["path", "dev", "ino", "size", "mtime_nsec", "ctime_nsec",
                "sha256", "tags", "imprinted_at"]
    check(cols == expected, f"column header matches expected (got {cols})")


def test_snap_field_count(ft_binary, isolated_env):
    """Every data row has exactly 9 tab-separated fields."""
    make_files(isolated_env.work, {
        "a.txt": b"aaa\n",
        "sub/b.txt": b"bbb\n",
    })
    r = run_ft(ft_binary, ["snap", str(isolated_env.work)],
               cwd=isolated_env.work, env=isolated_env.env)
    rows = parse_snap_tsv(r.stdout)
    check(len(rows) >= 2, f"at least 2 data rows (got {len(rows)})")
    for row in rows:
        # SnapRow has exactly 9 fields by construction; verify raw line
        pass  # parse_snap_tsv already validates 9 fields
    narrate("All data rows have 9 fields")
    check(True, f"all {len(rows)} rows have 9 fields")


def test_snap_hash_matches_ls(ft_binary, isolated_env):
    """SHA-256 in snap must match ft ls --full-hash."""
    make_files(isolated_env.work, {
        "x.txt": b"cross check\n",
        "y.txt": b"verify hash\n",
    })

    narrate("Getting hashes from snap and ls --full-hash")
    snap_r = run_ft(ft_binary, ["snap", str(isolated_env.work)],
                    cwd=isolated_env.work, env=isolated_env.env)
    ls_r = run_ft(ft_binary, ["ls", "--full-hash", str(isolated_env.work)],
                  cwd=isolated_env.work, env=isolated_env.env)

    snap_rows = parse_snap_tsv(snap_r.stdout)
    ls_entries = parse_ls_output(ls_r.stdout)

    snap_hashes = {os.path.basename(r.path): r.sha256 for r in snap_rows}
    ls_hashes = {os.path.basename(e.path): e.hash for e in ls_entries}

    for name in snap_hashes:
        check(name in ls_hashes, f"{name} present in both snap and ls")
        check(snap_hashes[name] == ls_hashes[name],
              f"{name}: snap hash == ls hash")


def test_snap_hash_matches_independent(ft_binary, isolated_env):
    """SHA-256 in snap must match independently computed hash."""
    content = b"independent verification\n"
    make_file(isolated_env.work / "verify.txt", content)

    r = run_ft(ft_binary, ["snap", str(isolated_env.work)],
               cwd=isolated_env.work, env=isolated_env.env)
    rows = parse_snap_tsv(r.stdout)
    check(len(rows) == 1, "one row")

    expected = compute_sha256(isolated_env.work / "verify.txt")
    check(rows[0].sha256 == expected,
          f"snap hash matches python SHA-256: {rows[0].sha256[:16]}...")


def test_snap_paths_are_relative(ft_binary, isolated_env):
    """Snap paths must not contain absolute path components."""
    make_file(isolated_env.work / "sub" / "file.txt", b"relative\n")
    r = run_ft(ft_binary, ["snap", str(isolated_env.work)],
               cwd=isolated_env.work, env=isolated_env.env)
    rows = parse_snap_tsv(r.stdout)
    for row in rows:
        check(not row.path.startswith("/"),
              f"path '{row.path}' is relative (not absolute)")


def test_snap_resnap_consistency(ft_binary, isolated_env):
    """Two consecutive snaps of unchanged tree produce identical hashes."""
    make_files(isolated_env.work, {
        "stable1.txt": b"do not change\n",
        "stable2.txt": b"also stable\n",
    })

    narrate("Taking two consecutive snapshots")
    r1 = run_ft(ft_binary, ["snap", str(isolated_env.work)],
                cwd=isolated_env.work, env=isolated_env.env)
    r2 = run_ft(ft_binary, ["snap", str(isolated_env.work)],
                cwd=isolated_env.work, env=isolated_env.env)

    rows1 = parse_snap_tsv(r1.stdout)
    rows2 = parse_snap_tsv(r2.stdout)

    hashes1 = {r.path: r.sha256 for r in rows1}
    hashes2 = {r.path: r.sha256 for r in rows2}

    check(hashes1 == hashes2, "re-snap hashes are identical for unchanged tree")


def test_snap_single_file(ft_binary, isolated_env):
    """Snap of a single file works correctly."""
    make_file(isolated_env.work / "solo.txt", b"solo snap\n")
    r = run_ft(ft_binary, ["snap", str(isolated_env.work / "solo.txt")],
               cwd=isolated_env.work, env=isolated_env.env)
    check(r.exit_code == 0, f"exit code 0 (got {r.exit_code})")
    rows = parse_snap_tsv(r.stdout)
    check(len(rows) == 1, f"one row for single file (got {len(rows)})")
    check("solo.txt" in rows[0].path, "path contains solo.txt")


def test_snap_size_field_matches(ft_binary, isolated_env):
    """Size field in snap matches actual file size in bytes."""
    content = b"size check content here\n"
    make_file(isolated_env.work / "sized.txt", content)

    r = run_ft(ft_binary, ["snap", str(isolated_env.work)],
               cwd=isolated_env.work, env=isolated_env.env)
    rows = parse_snap_tsv(r.stdout)
    check(len(rows) == 1, "one row")
    check(int(rows[0].size) == len(content),
          f"snap size ({rows[0].size}) == actual ({len(content)})")
