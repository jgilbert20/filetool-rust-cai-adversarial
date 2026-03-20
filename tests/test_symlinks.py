"""Symlink handling — skipped, not followed, graceful on dangling."""

import os

from tests.helpers import (
    check,
    make_file,
    narrate,
    parse_ls_output,
    run_ft,
)


def test_symlink_to_file_skipped(ft_binary, isolated_env):
    """Symlink to a file is skipped during recursive listing."""
    make_file(isolated_env.work / "real.txt", b"real file\n")
    os.symlink(isolated_env.work / "real.txt",
               isolated_env.work / "link.txt")

    narrate("Recursive ls should silently skip symlinks")
    r = run_ft(ft_binary, ["ls", str(isolated_env.work)],
               cwd=isolated_env.work, env=isolated_env.env)
    check(r.exit_code == 0, f"exit code 0 (got {r.exit_code})")
    entries = parse_ls_output(r.stdout)
    paths = [e.path for e in entries]
    check(any("real.txt" in p for p in paths), "real file listed")
    check(not any("link.txt" in p for p in paths), "symlink NOT listed in output")

    narrate("Directly passing symlink as arg should produce stderr message")
    r2 = run_ft(ft_binary, ["ls", str(isolated_env.work / "link.txt")],
                cwd=isolated_env.work, env=isolated_env.env)
    check("symbolic link" in r2.stderr or "symlink" in r2.stderr.lower(),
          "stderr mentions symlink when passed directly")


def test_symlink_to_dir_not_followed(ft_binary, isolated_env):
    """Symlink to directory is not followed during recursion."""
    make_file(isolated_env.work / "real_dir" / "inside.txt", b"inside\n")
    os.symlink(isolated_env.work / "real_dir",
               isolated_env.work / "link_dir")

    r = run_ft(ft_binary, ["ls", str(isolated_env.work)],
               cwd=isolated_env.work, env=isolated_env.env)
    entries = parse_ls_output(r.stdout)
    # Should only see real_dir/inside.txt, not link_dir/inside.txt
    link_entries = [e for e in entries if "link_dir" in e.path]
    check(len(link_entries) == 0, "symlink directory not followed")
    real_entries = [e for e in entries if "real_dir" in e.path]
    check(len(real_entries) >= 1, "real directory files present")


def test_dangling_symlink_graceful(ft_binary, isolated_env):
    """Dangling symlink (target doesn't exist) handled gracefully."""
    make_file(isolated_env.work / "normal.txt", b"normal\n")
    os.symlink(isolated_env.work / "nonexistent_target",
               isolated_env.work / "dangling.txt")

    r = run_ft(ft_binary, ["ls", str(isolated_env.work)],
               cwd=isolated_env.work, env=isolated_env.env)
    check(r.exit_code == 0, f"exit code 0 even with dangling symlink (got {r.exit_code})")
    entries = parse_ls_output(r.stdout)
    paths = [e.path for e in entries]
    check(any("normal.txt" in p for p in paths), "normal file still listed")
    check(not any("dangling.txt" in p for p in paths), "dangling symlink not in output")


def test_symlink_only_real_files_in_output(ft_binary, isolated_env):
    """Mixed tree with real files and symlinks → only real files in output."""
    make_file(isolated_env.work / "a.txt", b"real a\n")
    make_file(isolated_env.work / "b.txt", b"real b\n")
    os.symlink(isolated_env.work / "a.txt",
               isolated_env.work / "sym_a.txt")
    os.symlink(isolated_env.work / "b.txt",
               isolated_env.work / "sym_b.txt")

    r = run_ft(ft_binary, ["ls", str(isolated_env.work)],
               cwd=isolated_env.work, env=isolated_env.env)
    entries = parse_ls_output(r.stdout)
    check(len(entries) == 2, f"exactly 2 entries (real files only), got {len(entries)}")
    paths = [e.path for e in entries]
    check(all("sym_" not in p for p in paths), "no symlinks in output")
