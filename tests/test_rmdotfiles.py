"""Tests for rmdotfiles and clear-db commands."""

import os
import time

from tests.helpers import (
    check,
    make_file,
    make_files,
    narrate,
    run_ft,
)


def test_rmdotfiles_removes_all_dotfiles(ft_binary, isolated_env):
    """rmdotfiles removes all .filetool files recursively."""
    make_files(isolated_env.work, {
        "a.txt": b"a\n",
        "sub/b.txt": b"b\n",
        "sub/deep/c.txt": b"c\n",
    })

    narrate("Populating caches")
    run_ft(ft_binary, ["ls", str(isolated_env.work)],
           cwd=isolated_env.work, env=isolated_env.env)

    narrate("Verifying .filetool files exist")
    dotfiles_before = list(isolated_env.work.rglob(".filetool"))
    check(len(dotfiles_before) > 0, f"dotfiles exist before cleanup ({len(dotfiles_before)} found)")

    narrate("Running rmdotfiles")
    r = run_ft(ft_binary, ["rmdotfiles", str(isolated_env.work)],
               cwd=isolated_env.work, env=isolated_env.env)
    check(r.exit_code == 0, f"exit code 0 (got {r.exit_code})")

    narrate("Verifying all .filetool files removed")
    dotfiles_after = list(isolated_env.work.rglob(".filetool"))
    check(len(dotfiles_after) == 0, f"no dotfiles remain (found {len(dotfiles_after)})")


def test_rmdotfiles_removes_tmp_files(ft_binary, isolated_env):
    """rmdotfiles also removes .filetool.tmp.* files."""
    make_file(isolated_env.work / "f.txt", b"test\n")
    run_ft(ft_binary, ["ls", str(isolated_env.work)],
           cwd=isolated_env.work, env=isolated_env.env)

    narrate("Creating fake .filetool.tmp.xxx files")
    make_file(isolated_env.work / ".filetool.tmp.12345", b"temp cache\n")
    make_file(isolated_env.work / ".filetool.tmp.67890", b"another temp\n")

    r = run_ft(ft_binary, ["rmdotfiles", str(isolated_env.work)],
               cwd=isolated_env.work, env=isolated_env.env)

    tmp_files = list(isolated_env.work.rglob(".filetool.tmp.*"))
    check(len(tmp_files) == 0, f"no .filetool.tmp.* files remain (found {len(tmp_files)})")


def test_rmdotfiles_restores_parent_mtime(ft_binary, isolated_env):
    """After removing .filetool, parent dir mtime is restored."""
    make_file(isolated_env.work / "f.txt", b"mtime test\n")

    narrate("Populating cache")
    run_ft(ft_binary, ["ls", str(isolated_env.work)],
           cwd=isolated_env.work, env=isolated_env.env)

    narrate("Recording directory mtime before rmdotfiles")
    # Set a known mtime on the directory
    known_mtime = 1700000000.0
    os.utime(isolated_env.work, (known_mtime, known_mtime))
    mtime_before = os.stat(isolated_env.work).st_mtime

    narrate("Running rmdotfiles")
    r = run_ft(ft_binary, ["rmdotfiles", str(isolated_env.work)],
               cwd=isolated_env.work, env=isolated_env.env)

    mtime_after = os.stat(isolated_env.work).st_mtime
    check(abs(mtime_after - mtime_before) < 1.0,
          f"dir mtime restored: before={mtime_before}, after={mtime_after}")


def test_rmdotfiles_exit_zero_always(ft_binary, isolated_env):
    """rmdotfiles always exits 0, even with no dotfiles to remove."""
    make_file(isolated_env.work / "f.txt", b"test\n")

    r = run_ft(ft_binary, ["rmdotfiles", str(isolated_env.work)],
               cwd=isolated_env.work, env=isolated_env.env)
    check(r.exit_code == 0, f"exit code 0 with no dotfiles (got {r.exit_code})")
    check("no dotfiles found" in r.stdout.lower() or "0 dotfiles" in r.stdout.lower(),
          "output indicates no dotfiles found")


def test_clear_db_removes_lmdb(ft_binary, isolated_env):
    """clear-db removes LMDB cache files and reports paths."""
    make_file(isolated_env.work / "f.txt", b"lmdb test\n")

    narrate("Populating LMDB cache")
    run_ft(ft_binary, ["ls", str(isolated_env.work)],
           cwd=isolated_env.work, env=isolated_env.env)

    lmdb_dir = isolated_env.home / ".filetool" / "cache"
    check(lmdb_dir.exists(), "LMDB cache directory exists")

    narrate("Running clear-db")
    r = run_ft(ft_binary, ["clear-db"],
               cwd=isolated_env.work, env=isolated_env.env)
    check(r.exit_code == 0, f"exit code 0 (got {r.exit_code})")

    narrate("Verifying LMDB files removed")
    if lmdb_dir.exists():
        remaining = list(lmdb_dir.iterdir())
        check(len(remaining) == 0, f"LMDB dir empty (found {len(remaining)} files)")
    else:
        check(True, "LMDB dir removed entirely")

    check(len(r.stdout) > 0, "clear-db prints removed file paths")
