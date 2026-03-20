"""CWD sensitivity tests — path consistency across working directories."""

import os

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


def test_cwd_absolute_path_consistent(ft_binary, isolated_env):
    """Running with absolute paths from different CWDs produces same hashes."""
    make_files(isolated_env.work / "target", {
        "a.txt": b"consistent\n",
        "b.txt": b"hashes\n",
    })
    target_abs = str(isolated_env.work / "target")

    narrate("Running from work/")
    r1 = run_ft(ft_binary, ["ls", "--full-hash", target_abs],
                cwd=isolated_env.work, env=isolated_env.env)

    narrate("Running from root/")
    r2 = run_ft(ft_binary, ["ls", "--full-hash", target_abs],
                cwd=isolated_env.root, env=isolated_env.env)

    entries1 = {os.path.basename(e.path): e.hash for e in parse_ls_output(r1.stdout)}
    entries2 = {os.path.basename(e.path): e.hash for e in parse_ls_output(r2.stdout)}
    check(entries1 == entries2, "same hashes regardless of CWD")


def test_cwd_ls_dot(ft_binary, isolated_env):
    """ft ls . from inside directory lists its files."""
    make_file(isolated_env.work / "inside.txt", b"cwd test\n")

    r = run_ft(ft_binary, ["ls", "."],
               cwd=isolated_env.work, env=isolated_env.env)
    check(r.exit_code == 0, f"exit code 0 (got {r.exit_code})")
    entries = parse_ls_output(r.stdout)
    check(len(entries) >= 1, "files found with ft ls .")
    check(any("inside.txt" in e.path for e in entries), "inside.txt found")


def test_cwd_snap_path_relativity(ft_binary, isolated_env):
    """Snap paths are relative to snap file location (or CWD when piping)."""
    make_files(isolated_env.work / "project", {
        "src/main.py": b"print('hello')\n",
        "src/util.py": b"def helper(): pass\n",
    })

    narrate("Snapping from inside the project directory")
    r1 = run_ft(ft_binary, ["snap", "."],
                cwd=isolated_env.work / "project", env=isolated_env.env)
    rows1 = parse_snap_tsv(r1.stdout)

    narrate("Snapping from parent with explicit path")
    r2 = run_ft(ft_binary, ["snap", str(isolated_env.work / "project")],
                cwd=isolated_env.work, env=isolated_env.env)
    rows2 = parse_snap_tsv(r2.stdout)

    narrate("Checking paths are relative in both cases")
    for row in rows1:
        check(not row.path.startswith("/"), f"snap from inside: '{row.path}' is relative")
    for row in rows2:
        check(not row.path.startswith("/"), f"snap from outside: '{row.path}' is relative")

    # Hashes should be identical even if paths differ
    hashes1 = {os.path.basename(r.path): r.sha256 for r in rows1}
    hashes2 = {os.path.basename(r.path): r.sha256 for r in rows2}
    check(hashes1 == hashes2, "hashes identical regardless of snap CWD")


def test_cwd_diff_single_arg_compares_cwd(ft_binary, isolated_env):
    """ft diff snap.snap (single arg) compares against CWD."""
    make_file(isolated_env.work / "f.txt", b"original\n")

    narrate("Taking snapshot from CWD")
    snap_r = run_ft(ft_binary, ["snap", "."],
                    cwd=isolated_env.work, env=isolated_env.env)
    # Store snap OUTSIDE the work dir so it doesn't appear as a new file
    snap_file = isolated_env.root / "baseline.snap"
    snap_file.write_text(snap_r.stdout)

    narrate("Adding new file")
    make_file(isolated_env.work / "new.txt", b"new file\n")

    narrate("Running diff with single arg (should compare against CWD)")
    r = run_ft(ft_binary, ["diff", str(snap_file)],
               cwd=isolated_env.work, env=isolated_env.env)
    check("new.txt" in r.stdout, "new file detected in single-arg diff against CWD")
