"""Stats and diagnostics tests — -Q counters, FT_DIAG_SUMMARY."""

from tests.helpers import (
    check,
    make_file,
    make_files,
    narrate,
    parse_diag,
    parse_stats,
    run_ft,
)


def test_stats_format(ft_binary, isolated_env):
    """-Q produces stats line with expected counters on stderr."""
    make_file(isolated_env.work / "f.txt", b"stats test\n")

    r = run_ft(ft_binary, ["ls", "-Q", str(isolated_env.work)],
               cwd=isolated_env.work, env=isolated_env.env)
    stats = parse_stats(r.stderr)
    expected_keys = {"stat()", "readdir()", "dir_entries", "checksums",
                     "bytes_checksummed", "xattr()", "time"}
    present = set(stats.keys())
    for key in expected_keys:
        check(key in present, f"stats has '{key}' counter")


def test_stats_first_run_checksums_positive(ft_binary, isolated_env):
    """First run (uncached) should have checksums > 0."""
    make_files(isolated_env.work, {"a.txt": b"aaa\n", "b.txt": b"bbb\n"})

    # Clear all caches
    run_ft(ft_binary, ["clear-db"], cwd=isolated_env.work, env=isolated_env.env)

    r = run_ft(ft_binary, ["--no-cache", "ls", "-Q", str(isolated_env.work)],
               cwd=isolated_env.work, env=isolated_env.env)
    stats = parse_stats(r.stderr)
    checksums = int(stats.get("checksums", 0))
    check(checksums > 0, f"uncached run: checksums={checksums} > 0")


def test_stats_cached_run_checksums_zero(ft_binary, isolated_env):
    """Cached run should have checksums = 0."""
    make_file(isolated_env.work / "f.txt", b"cache test\n")

    narrate("First run to populate cache")
    run_ft(ft_binary, ["ls", str(isolated_env.work)],
           cwd=isolated_env.work, env=isolated_env.env)

    narrate("Second run with -Q: checksums should be 0")
    r = run_ft(ft_binary, ["ls", "-Q", str(isolated_env.work)],
               cwd=isolated_env.work, env=isolated_env.env)
    stats = parse_stats(r.stderr)
    checksums = int(stats.get("checksums", 0))
    check(checksums == 0, f"cached run: checksums={checksums} == 0")


def test_diag_summary(ft_binary, isolated_env):
    """FT_DIAG_SUMMARY=1 appends diagnostic line to stderr."""
    make_file(isolated_env.work / "f.txt", b"diag test\n")

    env = dict(isolated_env.env)
    env["FT_DIAG_SUMMARY"] = "1"

    r = run_ft(ft_binary, ["ls", str(isolated_env.work)],
               cwd=isolated_env.work, env=env)
    diag = parse_diag(r.stderr)
    check("errors" in diag, "diag has 'errors' counter")
    check("warnings" in diag, "diag has 'warnings' counter")
    check("verbose" in diag, "diag has 'verbose' counter")
    check(diag["errors"] == 0, f"no errors in clean run (got {diag['errors']})")


def test_diag_summary_counts_errors(ft_binary, isolated_env):
    """FT_DIAG_SUMMARY reports errors when files can't be read."""
    import os
    import pytest
    if os.getuid() == 0:
        pytest.skip("root can read any file; permission test meaningless")
    make_file(isolated_env.work / "ok.txt", b"fine\n")
    bad = isolated_env.work / "unreadable.txt"
    make_file(bad, b"secret\n")
    os.chmod(bad, 0o000)

    env = dict(isolated_env.env)
    env["FT_DIAG_SUMMARY"] = "1"

    try:
        r = run_ft(ft_binary, ["ls", str(isolated_env.work)],
                   cwd=isolated_env.work, env=env)
        diag = parse_diag(r.stderr)
        check(diag.get("errors", 0) >= 1,
              f"diag reports errors for unreadable file (got {diag.get('errors', 0)})")
    finally:
        os.chmod(bad, 0o644)
