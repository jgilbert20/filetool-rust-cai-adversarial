"""Diff detection tests — new, deleted, renamed, moved, modified."""

import os
import time

from tests.helpers import (
    check,
    make_file,
    make_files,
    narrate,
    parse_diff_output,
    parse_diff_tsv,
    run_ft,
)


def _snap(ft_binary, env, cwd, target):
    """Take a snapshot and return the TSV content as a string."""
    r = run_ft(ft_binary, ["snap", str(target)], cwd=cwd, env=env)
    assert r.exit_code == 0, f"snap failed: {r.stderr}"
    return r.stdout


def test_diff_no_changes(ft_binary, isolated_env):
    """Diff of identical trees produces empty output."""
    make_files(isolated_env.work, {"a.txt": b"stable\n", "b.txt": b"also stable\n"})

    narrate("Snapping tree then diffing against itself")
    snap = _snap(ft_binary, isolated_env.env, isolated_env.work, isolated_env.work)
    snap_file = isolated_env.root / "baseline.snap"
    snap_file.write_text(snap)

    r = run_ft(ft_binary, ["diff", str(snap_file), str(isolated_env.work)],
               cwd=isolated_env.work, env=isolated_env.env)
    entries = parse_diff_output(r.stdout)
    check(len(entries) == 0, f"no diff entries for identical tree (got {len(entries)})")


def test_diff_new_file(ft_binary, isolated_env):
    """File in B not in A is reported as 'new'."""
    make_file(isolated_env.work / "existing.txt", b"original\n")
    snap = _snap(ft_binary, isolated_env.env, isolated_env.work, isolated_env.work)
    snap_file = isolated_env.root / "baseline.snap"
    snap_file.write_text(snap)

    narrate("Adding a new file after snapshot")
    make_file(isolated_env.work / "brand_new.txt", b"I am new\n")

    r = run_ft(ft_binary, ["diff", str(snap_file), str(isolated_env.work)],
               cwd=isolated_env.work, env=isolated_env.env)
    entries = parse_diff_output(r.stdout)
    new_entries = [e for e in entries if e.status == "new"]
    check(any("brand_new.txt" in e.path_a for e in new_entries),
          "brand_new.txt reported as 'new'")


def test_diff_deleted_file(ft_binary, isolated_env):
    """File in A not in B is reported as 'deleted'."""
    make_file(isolated_env.work / "doomed.txt", b"goodbye\n")
    make_file(isolated_env.work / "keeper.txt", b"staying\n")
    snap = _snap(ft_binary, isolated_env.env, isolated_env.work, isolated_env.work)
    snap_file = isolated_env.root / "baseline.snap"
    snap_file.write_text(snap)

    narrate("Deleting a file after snapshot")
    os.remove(isolated_env.work / "doomed.txt")

    r = run_ft(ft_binary, ["diff", str(snap_file), str(isolated_env.work)],
               cwd=isolated_env.work, env=isolated_env.env)
    entries = parse_diff_output(r.stdout)
    deleted = [e for e in entries if e.status == "deleted"]
    check(any("doomed.txt" in e.path_a for e in deleted),
          "doomed.txt reported as 'deleted'")


def test_diff_renamed_file(ft_binary, isolated_env):
    """Same content, different name → 'renamed'."""
    make_file(isolated_env.work / "old_name.txt", b"rename me\n")
    snap = _snap(ft_binary, isolated_env.env, isolated_env.work, isolated_env.work)
    snap_file = isolated_env.root / "baseline.snap"
    snap_file.write_text(snap)

    narrate("Renaming file (same content, different name)")
    os.rename(isolated_env.work / "old_name.txt",
              isolated_env.work / "new_name.txt")

    r = run_ft(ft_binary, ["diff", str(snap_file), str(isolated_env.work)],
               cwd=isolated_env.work, env=isolated_env.env)
    entries = parse_diff_output(r.stdout)
    renamed = [e for e in entries if e.status == "renamed"]
    check(len(renamed) >= 1, f"at least one rename detected (got {len(renamed)})")
    check(any("old_name.txt" in e.path_a and "new_name.txt" in e.path_b
              for e in renamed),
          "old_name.txt → new_name.txt rename detected")


def test_diff_moved_file(ft_binary, isolated_env):
    """Same name+content, different directory → 'moved'."""
    make_file(isolated_env.work / "dirA" / "movable.txt", b"move me\n")
    snap = _snap(ft_binary, isolated_env.env, isolated_env.work, isolated_env.work)
    snap_file = isolated_env.root / "baseline.snap"
    snap_file.write_text(snap)

    narrate("Moving file to different directory (same name)")
    (isolated_env.work / "dirB").mkdir(parents=True, exist_ok=True)
    os.rename(isolated_env.work / "dirA" / "movable.txt",
              isolated_env.work / "dirB" / "movable.txt")
    # Remove dirA (may have .filetool cache left behind)
    import shutil
    shutil.rmtree(isolated_env.work / "dirA")

    r = run_ft(ft_binary, ["diff", str(snap_file), str(isolated_env.work)],
               cwd=isolated_env.work, env=isolated_env.env)
    entries = parse_diff_output(r.stdout)
    moved = [e for e in entries if e.status == "moved"]
    check(len(moved) >= 1, f"move detected (got {len(moved)} moved entries)")


def test_diff_modified_file(ft_binary, isolated_env):
    """Same path, different content → 'modified'."""
    make_file(isolated_env.work / "mutable.txt", b"version 1\n")
    snap = _snap(ft_binary, isolated_env.env, isolated_env.work, isolated_env.work)
    snap_file = isolated_env.root / "baseline.snap"
    snap_file.write_text(snap)

    narrate("Modifying file content")
    time.sleep(0.05)  # ensure mtime changes
    make_file(isolated_env.work / "mutable.txt", b"version 2\n")

    r = run_ft(ft_binary, ["diff", str(snap_file), str(isolated_env.work)],
               cwd=isolated_env.work, env=isolated_env.env)
    entries = parse_diff_output(r.stdout)
    modified = [e for e in entries if e.status == "modified"]
    check(any("mutable.txt" in e.path_a for e in modified),
          "mutable.txt reported as 'modified'")


def test_diff_no_renames_flag(ft_binary, isolated_env):
    """--no-renames reports renames as deleted+new instead."""
    make_file(isolated_env.work / "before.txt", b"rename test\n")
    snap = _snap(ft_binary, isolated_env.env, isolated_env.work, isolated_env.work)
    snap_file = isolated_env.root / "baseline.snap"
    snap_file.write_text(snap)

    os.rename(isolated_env.work / "before.txt",
              isolated_env.work / "after.txt")

    r = run_ft(ft_binary, ["diff", "--no-renames", str(snap_file), str(isolated_env.work)],
               cwd=isolated_env.work, env=isolated_env.env)
    entries = parse_diff_output(r.stdout)

    narrate("With --no-renames, should be deleted+new, not renamed")
    statuses = {e.status for e in entries}
    check("renamed" not in statuses, "no 'renamed' status with --no-renames")
    check("deleted" in statuses, "has 'deleted' entry")
    check("new" in statuses, "has 'new' entry")


def test_diff_tsv_output(ft_binary, isolated_env):
    """--tsv produces machine-readable tab-separated output."""
    make_file(isolated_env.work / "f.txt", b"tsv test\n")
    snap = _snap(ft_binary, isolated_env.env, isolated_env.work, isolated_env.work)
    snap_file = isolated_env.root / "baseline.snap"
    snap_file.write_text(snap)

    make_file(isolated_env.work / "new_file.txt", b"new\n")

    r = run_ft(ft_binary, ["diff", "--tsv", str(snap_file), str(isolated_env.work)],
               cwd=isolated_env.work, env=isolated_env.env)
    narrate("Checking TSV format")
    for line in r.stdout.strip().splitlines():
        fields = line.split("\t")
        check(len(fields) >= 2, f"TSV line has >=2 tab-separated fields: {line[:60]}")


def test_diff_snap_vs_snap(ft_binary, isolated_env):
    """Diff between two snapshot files (no disk I/O for content)."""
    make_files(isolated_env.work, {"a.txt": b"version1\n"})
    snap1 = _snap(ft_binary, isolated_env.env, isolated_env.work, isolated_env.work)
    snap1_file = isolated_env.root / "snap1.snap"
    snap1_file.write_text(snap1)

    time.sleep(0.05)
    make_file(isolated_env.work / "a.txt", b"version2\n")
    snap2 = _snap(ft_binary, isolated_env.env, isolated_env.work, isolated_env.work)
    snap2_file = isolated_env.root / "snap2.snap"
    snap2_file.write_text(snap2)

    r = run_ft(ft_binary, ["diff", str(snap1_file), str(snap2_file)],
               cwd=isolated_env.work, env=isolated_env.env)
    entries = parse_diff_output(r.stdout)
    modified = [e for e in entries if e.status == "modified"]
    check(any("a.txt" in e.path_a for e in modified),
          "a.txt modification detected between two snaps")


def test_diff_ambiguous_rename(ft_binary, isolated_env):
    """Multiple files with same hash → no rename, reported as deleted+new."""
    narrate("Creating two files with identical content (ambiguous for rename matching)")
    make_file(isolated_env.work / "dup1.txt", b"ambiguous content\n")
    make_file(isolated_env.work / "dup2.txt", b"ambiguous content\n")
    snap = _snap(ft_binary, isolated_env.env, isolated_env.work, isolated_env.work)
    snap_file = isolated_env.root / "baseline.snap"
    snap_file.write_text(snap)

    narrate("Removing both, adding two new files with same content")
    os.remove(isolated_env.work / "dup1.txt")
    os.remove(isolated_env.work / "dup2.txt")
    make_file(isolated_env.work / "new1.txt", b"ambiguous content\n")
    make_file(isolated_env.work / "new2.txt", b"ambiguous content\n")

    r = run_ft(ft_binary, ["diff", str(snap_file), str(isolated_env.work)],
               cwd=isolated_env.work, env=isolated_env.env)
    entries = parse_diff_output(r.stdout)
    statuses = {e.status for e in entries}
    narrate("Ambiguous rename: should be deleted+new, not renamed")
    check("renamed" not in statuses and "moved" not in statuses,
          "no rename/move for ambiguous hash match")


def test_diff_empty_files_no_rename(ft_binary, isolated_env):
    """Empty files are excluded from rename matching."""
    make_file(isolated_env.work / "empty_old.txt", b"")
    make_file(isolated_env.work / "nonempty.txt", b"content\n")
    snap = _snap(ft_binary, isolated_env.env, isolated_env.work, isolated_env.work)
    snap_file = isolated_env.root / "baseline.snap"
    snap_file.write_text(snap)

    os.rename(isolated_env.work / "empty_old.txt",
              isolated_env.work / "empty_new.txt")

    r = run_ft(ft_binary, ["diff", str(snap_file), str(isolated_env.work)],
               cwd=isolated_env.work, env=isolated_env.env)
    entries = parse_diff_output(r.stdout)
    renamed = [e for e in entries if e.status == "renamed"]
    empty_renames = [e for e in renamed if "empty" in e.path_a or "empty" in e.path_b]
    check(len(empty_renames) == 0,
          "empty files excluded from rename matching")


def test_diff_stdin_pipe(ft_binary, isolated_env):
    """Pipe snapshot via stdin with '-'."""
    make_files(isolated_env.work / "tree", {"f.txt": b"pipe test\n"})
    snap = _snap(ft_binary, isolated_env.env, isolated_env.work,
                 isolated_env.work / "tree")

    narrate("Adding file, then piping snapshot to diff via stdin")
    make_file(isolated_env.work / "tree" / "new.txt", b"new via pipe\n")

    r = run_ft(ft_binary, ["diff", "-", str(isolated_env.work / "tree")],
               cwd=isolated_env.work, env=isolated_env.env,
               stdin_data=snap)
    entries = parse_diff_output(r.stdout)
    new_entries = [e for e in entries if e.status == "new"]
    check(any("new.txt" in e.path_a for e in new_entries),
          "new file detected via stdin pipe")
