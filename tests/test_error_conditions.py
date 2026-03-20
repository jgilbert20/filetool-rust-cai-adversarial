"""Error condition tests — bad input, missing args, permissions."""

import os
import stat

from tests.helpers import (
    check,
    make_file,
    narrate,
    run_ft,
)


def test_error_no_arguments(ft_binary, isolated_env):
    """No arguments → help or error, non-zero exit."""
    r = run_ft(ft_binary, [], cwd=isolated_env.work, env=isolated_env.env)
    # Should show help or error
    has_output = len(r.stdout) > 0 or len(r.stderr) > 0
    check(has_output, "some output produced (help or error)")


def test_error_unknown_verb(ft_binary, isolated_env):
    """Unknown verb → exit 1 with error."""
    r = run_ft(ft_binary, ["nonexistentverb"],
               cwd=isolated_env.work, env=isolated_env.env)
    check(r.exit_code == 1, f"exit code 1 for unknown verb (got {r.exit_code})")
    check(len(r.stderr) > 0, "error message on stderr")


def test_error_bad_flag(ft_binary, isolated_env):
    """Unknown flag → exit 1."""
    r = run_ft(ft_binary, ["ls", "--nonexistent-flag", "."],
               cwd=isolated_env.work, env=isolated_env.env)
    check(r.exit_code == 1, f"exit code 1 for bad flag (got {r.exit_code})")


def test_error_lsdup_missing_source(ft_binary, isolated_env):
    """lsdup without -S → exit 1."""
    make_file(isolated_env.work / "f.txt", b"test\n")
    r = run_ft(ft_binary, ["lsdup", str(isolated_env.work)],
               cwd=isolated_env.work, env=isolated_env.env)
    check(r.exit_code == 1, f"exit code 1 for missing -S (got {r.exit_code})")


def test_error_lsdup_unreadable_source(ft_binary, isolated_env):
    """lsdup with unreadable -S source → exit 1 (fatal)."""
    make_file(isolated_env.work / "f.txt", b"test\n")
    r = run_ft(ft_binary, ["lsdup", "-S", "/nonexistent/path",
                           str(isolated_env.work)],
               cwd=isolated_env.work, env=isolated_env.env)
    check(r.exit_code == 1, f"exit code 1 for unreadable -S source (got {r.exit_code})")


def test_error_lsuniq_unreadable_source(ft_binary, isolated_env):
    """lsuniq with unreadable -S source → exit 1 (fatal)."""
    make_file(isolated_env.work / "f.txt", b"test\n")
    r = run_ft(ft_binary, ["lsuniq", "-S", "/nonexistent/source",
                           str(isolated_env.work)],
               cwd=isolated_env.work, env=isolated_env.env)
    check(r.exit_code == 1, f"exit code 1 for unreadable -S (got {r.exit_code})")


def test_error_nonexistent_path_ls(ft_binary, isolated_env):
    """ls on nonexistent path → error on stderr, exit 0."""
    r = run_ft(ft_binary, ["ls", str(isolated_env.work / "nope")],
               cwd=isolated_env.work, env=isolated_env.env)
    check(r.exit_code == 0, f"exit code 0 for missing ls target (got {r.exit_code})")
    check("nope" in r.stderr or "No such file" in r.stderr,
          "error message references missing path")


def test_error_permission_denied_file(ft_binary, isolated_env):
    """Unreadable file → skipped, error on stderr, exit 0."""
    import pytest
    if os.getuid() == 0:
        pytest.skip("root can read any file; permission test meaningless")
    make_file(isolated_env.work / "readable.txt", b"ok\n")
    unreadable = isolated_env.work / "secret.txt"
    make_file(unreadable, b"forbidden\n")
    os.chmod(unreadable, 0o000)

    try:
        r = run_ft(ft_binary, ["ls", str(isolated_env.work)],
                   cwd=isolated_env.work, env=isolated_env.env)
        check(r.exit_code == 0,
              f"exit code 0 despite unreadable file (got {r.exit_code})")
        check(len(r.stderr) > 0, "error message on stderr for unreadable file")
    finally:
        os.chmod(unreadable, 0o644)  # restore for cleanup


def test_error_lsuniq_missing_target_nonfatal(ft_binary, isolated_env):
    """lsuniq with nonexistent target → non-fatal (exit 0)."""
    make_file(isolated_env.work / "src" / "s.txt", b"src\n")
    r = run_ft(ft_binary, ["lsuniq", "-S", str(isolated_env.work / "src"),
                           str(isolated_env.work / "missing_target")],
               cwd=isolated_env.work, env=isolated_env.env)
    check(r.exit_code == 0,
          f"exit code 0 for missing lsuniq target (got {r.exit_code})")
