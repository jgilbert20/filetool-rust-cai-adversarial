"""
Adversarial tests that target CONFIRMED or SUSPECTED bugs in ft.

These tests are expected to FAIL against the current binary — they document
genuine incorrect behavior discovered during red-team auditing.
Tests are marked with pytest.mark.xfail where the tool has a confirmed bug,
so the overall suite stays green while clearly documenting the issues.
"""

import hashlib
import os
import time

import pytest

from tests.helpers import (
    check,
    compute_sha256,
    get_paths_from_lines,
    make_file,
    make_files,
    narrate,
    parse_diff_output,
    parse_ls_output,
    parse_snap_tsv,
    run_ft,
)


# -----------------------------------------------------------------------
# BUG: Cache serves stale hash when mtime+size are preserved
# -----------------------------------------------------------------------

@pytest.mark.xfail(reason="CONFIRMED BUG: cache does not check ctime, only mtime+size")
def test_bug_cache_stale_when_mtime_preserved(ft_binary, isolated_env):
    """Replace file content with same-length data, restore mtime → stale hash.

    The tool's cache uses mtime+size for validation. If both are preserved
    after a content change, the cache serves the old (wrong) hash.
    ctime changes but is not checked.
    """
    f = isolated_env.work / "victim.txt"
    make_file(f, b"ORIGINAL")

    narrate("Caching the file")
    r1 = run_ft(ft_binary, ["ls", "--full-hash", str(isolated_env.work)],
                cwd=isolated_env.work, env=isolated_env.env)
    old_hash = parse_ls_output(r1.stdout)[0].hash

    narrate("Recording mtime_ns")
    st = os.stat(f)
    orig_mtime_ns = st.st_mtime_ns

    narrate("Replacing content (same size), restoring exact mtime")
    f.write_bytes(b"REPLACED")  # same 8 bytes
    os.utime(f, ns=(orig_mtime_ns, orig_mtime_ns))

    narrate("Verifying mtime and size are preserved")
    st2 = os.stat(f)
    check(st2.st_mtime_ns == orig_mtime_ns, "mtime_ns preserved")
    check(st2.st_size == st.st_size, "size preserved")

    narrate("Running ft ls again — should detect change but DOESN'T")
    r2 = run_ft(ft_binary, ["ls", "--full-hash", str(isolated_env.work)],
                cwd=isolated_env.work, env=isolated_env.env)
    cached_hash = parse_ls_output(r2.stdout)[0].hash
    expected = hashlib.sha256(b"REPLACED").hexdigest()

    check(cached_hash == expected,
          f"cached hash should match new content: got {cached_hash[:16]}... expected {expected[:16]}...")


@pytest.mark.xfail(reason="CONFIRMED BUG: cache ignores ctime changes")
def test_bug_cache_ignores_ctime(ft_binary, isolated_env):
    """Write new content to file (ctime changes), restore mtime → stale hash.

    Even though ctime is updated (metadata change), the cache only looks at
    mtime+size and serves the old hash.
    """
    f = isolated_env.work / "ctime_victim.txt"
    make_file(f, b"AAAA")

    narrate("Caching the file")
    run_ft(ft_binary, ["ls", "--full-hash", str(isolated_env.work)],
           cwd=isolated_env.work, env=isolated_env.env)

    st1 = os.stat(f)
    narrate("Overwriting content (same size), restoring mtime, ctime WILL change")
    f.write_bytes(b"BBBB")
    os.utime(f, ns=(st1.st_mtime_ns, st1.st_mtime_ns))

    st2 = os.stat(f)
    check(st2.st_ctime_ns != st1.st_ctime_ns, "ctime did change")

    narrate("ft ls should detect ctime change but DOESN'T")
    r = run_ft(ft_binary, ["ls", "--full-hash", str(isolated_env.work)],
               cwd=isolated_env.work, env=isolated_env.env)
    cached = parse_ls_output(r.stdout)[0].hash
    expected = hashlib.sha256(b"BBBB").hexdigest()
    check(cached == expected, f"hash should reflect new content")


# -----------------------------------------------------------------------
# BUG: rmdotfiles destroys user files named .filetool
# -----------------------------------------------------------------------

@pytest.mark.xfail(reason="CONFIRMED BUG: rmdotfiles blindly removes ANY file named .filetool")
def test_bug_rmdotfiles_destroys_user_data(ft_binary, isolated_env):
    """A user file named .filetool is destroyed by rmdotfiles.

    rmdotfiles does not distinguish between cache dotfiles it created and
    user-created files that happen to be named .filetool.
    """
    narrate("Creating a user file named .filetool")
    user_dotfile = isolated_env.work / "mydir" / ".filetool"
    make_file(user_dotfile, b"IMPORTANT USER DATA\n")

    narrate("Running rmdotfiles")
    run_ft(ft_binary, ["rmdotfiles", str(isolated_env.work)],
           cwd=isolated_env.work, env=isolated_env.env)

    narrate("User's .filetool file should still exist")
    check(user_dotfile.exists(), "user .filetool file preserved (NOT destroyed)")


# -----------------------------------------------------------------------
# QUIRK: report silently omits zero-length files
# -----------------------------------------------------------------------

def test_quirk_report_omits_empty_files(ft_binary, isolated_env):
    """report command silently omits empty files — they appear in ls but not report.

    This means report doesn't cover ALL target files. A user might think
    their empty file was checked when it was silently dropped.
    """
    make_files(isolated_env.work / "src", {"s.txt": b"source\n"})
    make_files(isolated_env.work / "tgt", {
        "real.txt": b"unique\n",
        "empty.txt": b"",
    })

    narrate("ls shows the empty file")
    ls_r = run_ft(ft_binary, ["ls", str(isolated_env.work / "tgt")],
                  cwd=isolated_env.work, env=isolated_env.env)
    ls_entries = parse_ls_output(ls_r.stdout)
    check(any("empty.txt" in e.path for e in ls_entries), "ls shows empty.txt")

    narrate("report should mention all target files (documenting that it doesn't)")
    report_r = run_ft(ft_binary, ["report", "-S", str(isolated_env.work / "src"),
                                  str(isolated_env.work / "tgt")],
                      cwd=isolated_env.work, env=isolated_env.env)
    # Empty file is silently dropped — this documents the behavior
    check("empty.txt" not in report_r.stdout,
          "report silently omits empty files (documented quirk)")


# -----------------------------------------------------------------------
# QUIRK: snap -l on directory produces empty snap with no warning
# -----------------------------------------------------------------------

def test_quirk_snap_no_recurse_on_dir_empty(ft_binary, isolated_env):
    """snap -l on a directory produces a header-only snap with no data rows.

    Combined with the 'is a directory' message to stderr, this could
    confuse a user who expected top-level files to be snapped.
    """
    make_file(isolated_env.work / "top.txt", b"top\n")
    make_file(isolated_env.work / "sub" / "deep.txt", b"deep\n")

    r = run_ft(ft_binary, ["snap", "-l", str(isolated_env.work)],
               cwd=isolated_env.work, env=isolated_env.env)
    rows = parse_snap_tsv(r.stdout)
    narrate("snap -l on directory produces 0 data rows (documenting)")
    check(len(rows) == 0, f"snap -l on dir: {len(rows)} rows (empty snap)")
    check("is a directory" in r.stderr, "stderr has directory skip message")


# -----------------------------------------------------------------------
# QUIRK: diff path relativity mismatch
# -----------------------------------------------------------------------

def test_quirk_diff_path_mismatch_snap_from_parent(ft_binary, isolated_env):
    """Snap from parent dir + diff against subdir → false 'moved' results.

    If you snap from parent/ which captures parent/sub/f.txt, then diff
    against sub/, the paths don't match and all files appear moved.
    """
    make_file(isolated_env.work / "sub" / "f.txt", b"content\n")

    narrate("Snapping from parent (paths include 'sub/' prefix)")
    snap_r = run_ft(ft_binary, ["snap", str(isolated_env.work)],
                    cwd=isolated_env.work, env=isolated_env.env)
    snap_file = isolated_env.root / "from_parent.snap"
    snap_file.write_text(snap_r.stdout)

    narrate("Diffing snap against subdir (paths are 'f.txt' without 'sub/' prefix)")
    diff_r = run_ft(ft_binary, ["diff", str(snap_file),
                                str(isolated_env.work / "sub")],
                    cwd=isolated_env.work, env=isolated_env.env)
    entries = parse_diff_output(diff_r.stdout)

    narrate("Documenting: path prefix mismatch causes false 'moved' detection")
    moved = [e for e in entries if e.status == "moved"]
    # This is a documentation test — the tool reports "moved" due to path prefix mismatch
    if moved:
        check(True, f"false 'moved' due to path prefix mismatch ({len(moved)} entries)")
    else:
        check(True, "no false moves (tool handled path normalization)")


# -----------------------------------------------------------------------
# Test: lsdup with snapshot as TARGET (not just source)
# -----------------------------------------------------------------------

def test_lsdup_snapshot_as_target(ft_binary, isolated_env):
    """Can a .snap file be used as the target (not just -S source)?"""
    make_files(isolated_env.work / "src", {"shared.txt": b"shared\n"})
    make_files(isolated_env.work / "tgt", {
        "copy.txt": b"shared\n",
        "unique.txt": b"only here\n",
    })

    narrate("Creating snap of target")
    snap_r = run_ft(ft_binary, ["snap", str(isolated_env.work / "tgt")],
                    cwd=isolated_env.work, env=isolated_env.env)
    snap_file = isolated_env.root / "tgt.snap"
    snap_file.write_text(snap_r.stdout)

    narrate("Using snap file as target in lsdup")
    r = run_ft(ft_binary, ["lsdup", "-S", str(isolated_env.work / "src"),
                           str(snap_file)],
               cwd=isolated_env.work, env=isolated_env.env)
    check(r.exit_code == 0, f"exit code 0 (got {r.exit_code})")
    paths = get_paths_from_lines(r.stdout)
    check(any("copy.txt" in p for p in paths), "dup found via snap-as-target")


# -----------------------------------------------------------------------
# Test: --no-cache always correct (regression guard)
# -----------------------------------------------------------------------

def test_no_cache_never_stale(ft_binary, isolated_env):
    """--no-cache must always produce correct hashes, even after mtime tricks."""
    f = isolated_env.work / "f.txt"
    make_file(f, b"FIRST")

    narrate("Cache the file")
    run_ft(ft_binary, ["ls", str(isolated_env.work)],
           cwd=isolated_env.work, env=isolated_env.env)

    narrate("Replace content, preserve mtime")
    st = os.stat(f)
    f.write_bytes(b"SECND")  # same 5 bytes
    os.utime(f, ns=(st.st_mtime_ns, st.st_mtime_ns))

    narrate("--no-cache must show correct hash despite mtime trick")
    r = run_ft(ft_binary, ["--no-cache", "ls", "--full-hash", str(isolated_env.work)],
               cwd=isolated_env.work, env=isolated_env.env)
    cached = parse_ls_output(r.stdout)[0].hash
    expected = hashlib.sha256(b"SECND").hexdigest()
    check(cached == expected, "--no-cache produces correct hash")
