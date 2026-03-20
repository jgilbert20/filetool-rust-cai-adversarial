"""Tests for ls option flags: --full-hash, --no-hash, -l, -Q, --no-cache, --no-dotfile-writes."""

import os

from tests.helpers import (
    check,
    make_file,
    make_files,
    narrate,
    parse_ls_output,
    parse_stats,
    run_ft,
)


def test_ls_full_hash_64_chars(ft_binary, isolated_env):
    """--full-hash produces 64-character hex strings."""
    make_file(isolated_env.work / "f.txt", b"full hash test\n")
    r = run_ft(ft_binary, ["ls", "--full-hash", str(isolated_env.work)],
               cwd=isolated_env.work, env=isolated_env.env)
    entries = parse_ls_output(r.stdout)
    check(len(entries) == 1, "one entry")
    check(len(entries[0].hash) == 64, f"hash is 64 chars (got {len(entries[0].hash)})")
    # Must be valid hex
    try:
        int(entries[0].hash, 16)
        check(True, "hash is valid hex")
    except ValueError:
        check(False, "hash is valid hex")


def test_ls_no_hash_shows_dashes_when_uncached(ft_binary, isolated_env):
    """--no-hash with --no-cache shows dashes (no cached hash available)."""
    make_file(isolated_env.work / "f.txt", b"no hash test\n")

    narrate("Running with --no-cache --no-hash (no prior cache)")
    # First clear any cache, then run with --no-hash
    r = run_ft(ft_binary, ["--no-cache", "ls", "--no-hash", str(isolated_env.work)],
               cwd=isolated_env.work, env=isolated_env.env)
    check(r.exit_code == 0, f"exit code 0 (got {r.exit_code})")
    entries = parse_ls_output(r.stdout)
    if entries:
        check(set(entries[0].hash) <= set("-"), f"hash is dashes when uncached (got '{entries[0].hash}')")


def test_ls_no_hash_shows_cached_hash(ft_binary, isolated_env):
    """--no-hash shows cached hash when cache exists from prior run."""
    make_file(isolated_env.work / "f.txt", b"cached hash\n")

    narrate("First run: populate cache")
    r1 = run_ft(ft_binary, ["ls", "--full-hash", str(isolated_env.work)],
                cwd=isolated_env.work, env=isolated_env.env)
    full_hash = parse_ls_output(r1.stdout)[0].hash

    narrate("Second run: --no-hash should show cached hash")
    r2 = run_ft(ft_binary, ["ls", "--no-hash", str(isolated_env.work)],
                cwd=isolated_env.work, env=isolated_env.env)
    entries = parse_ls_output(r2.stdout)
    check(len(entries) == 1, "one entry")
    # Should show the cached hash (12-char prefix or full)
    check(entries[0].hash != "------------",
          f"hash is not dashes (got '{entries[0].hash}'), cache was used")


def test_ls_no_recurse(ft_binary, isolated_env):
    """-l on a directory prints 'is a directory' message and lists no files."""
    narrate("Creating nested directory structure")
    make_file(isolated_env.work / "top.txt", b"top\n")
    make_file(isolated_env.work / "sub" / "deep.txt", b"deep\n")

    r = run_ft(ft_binary, ["ls", "-l", str(isolated_env.work)],
               cwd=isolated_env.work, env=isolated_env.env)
    check(r.exit_code == 0, f"exit code 0 (got {r.exit_code})")

    narrate("Checking -l on directory shows skip message")
    check("is a directory" in r.stderr, "stderr mentions 'is a directory'")

    entries = parse_ls_output(r.stdout)
    check(len(entries) == 0, f"-l on directory: no files listed (got {len(entries)})")

    narrate("Checking -l on a single file works")
    r2 = run_ft(ft_binary, ["ls", "-l", str(isolated_env.work / "top.txt")],
                cwd=isolated_env.work, env=isolated_env.env)
    entries2 = parse_ls_output(r2.stdout)
    check(len(entries2) == 1, f"-l on single file: 1 entry (got {len(entries2)})")
    check("top.txt" in entries2[0].path, "top.txt listed when passed as file arg")


def test_ls_stats_output(ft_binary, isolated_env):
    """-Q produces stats on stderr with expected counters."""
    make_files(isolated_env.work, {
        "a.txt": b"aaa\n",
        "b.txt": b"bbb\n",
    })

    narrate("Running ft ls -Q (first run, uncached)")
    # Clear cache first
    run_ft(ft_binary, ["rmdotfiles", str(isolated_env.work)],
           cwd=isolated_env.work, env=isolated_env.env)
    run_ft(ft_binary, ["clear-db"],
           cwd=isolated_env.work, env=isolated_env.env)

    r = run_ft(ft_binary, ["ls", "-Q", str(isolated_env.work)],
               cwd=isolated_env.work, env=isolated_env.env)
    stats = parse_stats(r.stderr)
    check("stat()" in stats, "stat() counter present")
    check("readdir()" in stats, "readdir() counter present")
    check("checksums" in stats, "checksums counter present")
    check("bytes_checksummed" in stats, "bytes_checksummed counter present")

    narrate("Checking first-run stats make sense")
    checksums = int(stats.get("checksums", 0))
    check(checksums > 0, f"first run: checksums={checksums} > 0 (files were hashed)")

    narrate("Running ft ls -Q again (cached)")
    r2 = run_ft(ft_binary, ["ls", "-Q", str(isolated_env.work)],
                cwd=isolated_env.work, env=isolated_env.env)
    stats2 = parse_stats(r2.stderr)
    checksums2 = int(stats2.get("checksums", 0))
    check(checksums2 == 0, f"cached run: checksums={checksums2} == 0 (cache hit)")


def test_ls_no_cache_always_hashes(ft_binary, isolated_env):
    """--no-cache forces re-hashing every time."""
    make_file(isolated_env.work / "f.txt", b"no cache test\n")

    narrate("First run to populate cache")
    run_ft(ft_binary, ["ls", str(isolated_env.work)],
           cwd=isolated_env.work, env=isolated_env.env)

    narrate("Second run with --no-cache -Q: should still hash")
    r = run_ft(ft_binary, ["--no-cache", "ls", "-Q", str(isolated_env.work)],
               cwd=isolated_env.work, env=isolated_env.env)
    stats = parse_stats(r.stderr)
    checksums = int(stats.get("checksums", 0))
    check(checksums > 0, f"--no-cache: checksums={checksums} > 0 (forced re-hash)")


def test_ls_no_dotfile_writes(ft_binary, isolated_env):
    """--no-dotfile-writes should not create .filetool files."""
    make_file(isolated_env.work / "f.txt", b"no dotfile\n")

    narrate("Running with --no-dotfile-writes")
    r = run_ft(ft_binary, ["--no-dotfile-writes", "ls", str(isolated_env.work)],
               cwd=isolated_env.work, env=isolated_env.env)
    check(r.exit_code == 0, f"exit code 0 (got {r.exit_code})")

    narrate("Checking no .filetool file was created")
    dotfile = isolated_env.work / ".filetool"
    check(not dotfile.exists(), f".filetool does not exist (exists={dotfile.exists()})")
