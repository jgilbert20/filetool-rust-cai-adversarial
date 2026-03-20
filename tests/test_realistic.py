"""Realistic user scenarios — photo library, backup workflows, reorganization."""

import os
import time

from tests.helpers import (
    check,
    get_paths_from_lines,
    make_file,
    make_files,
    narrate,
    parse_diff_output,
    parse_ls_output,
    parse_snap_tsv,
    run_ft,
)


def test_realistic_photo_library_dedup(ft_binary, isolated_env):
    """Simulate photo library with duplicates across dated folders."""
    narrate("Creating photo library with duplicates across date folders")
    # Simulate camera roll organized by date
    make_files(isolated_env.work / "photos", {
        "2024-01/IMG_001.jpg": b"photo content alpha\n",
        "2024-01/IMG_002.jpg": b"photo content beta\n",
        "2024-02/IMG_003.jpg": b"photo content gamma\n",
        "2024-02/IMG_001_copy.jpg": b"photo content alpha\n",  # dup of IMG_001
        "2024-03/vacation_001.jpg": b"photo content beta\n",   # dup of IMG_002
        "2024-03/unique_shot.jpg": b"unique vacation photo\n",
    })

    narrate("Creating backup folder with some already-backed-up photos")
    make_files(isolated_env.work / "backup", {
        "IMG_001.jpg": b"photo content alpha\n",
        "IMG_002.jpg": b"photo content beta\n",
    })

    narrate("Finding photos already backed up")
    r = run_ft(ft_binary, ["lsdup", "-S", str(isolated_env.work / "backup"),
                           str(isolated_env.work / "photos")],
               cwd=isolated_env.work, env=isolated_env.env)
    dup_paths = get_paths_from_lines(r.stdout)

    narrate("Verifying correct duplicates found")
    # IMG_001, IMG_001_copy, IMG_002, vacation_001 should all be dups
    dup_basenames = {os.path.basename(p) for p in dup_paths}
    check("IMG_001.jpg" in dup_basenames, "IMG_001 found as dup")
    check("IMG_001_copy.jpg" in dup_basenames, "IMG_001_copy found as dup")
    check("IMG_002.jpg" in dup_basenames, "IMG_002 found as dup")
    check("vacation_001.jpg" in dup_basenames, "vacation_001 (same content as IMG_002) found as dup")

    narrate("Finding photos NOT yet backed up")
    r2 = run_ft(ft_binary, ["lsuniq", "-S", str(isolated_env.work / "backup"),
                            str(isolated_env.work / "photos")],
                cwd=isolated_env.work, env=isolated_env.env)
    uniq_paths = get_paths_from_lines(r2.stdout)
    uniq_basenames = {os.path.basename(p) for p in uniq_paths}
    check("IMG_003.jpg" in uniq_basenames, "IMG_003 is unique (not backed up)")
    check("unique_shot.jpg" in uniq_basenames, "unique_shot is unique")


def test_realistic_backup_workflow(ft_binary, isolated_env):
    """Snap → modify files → diff shows exactly what changed."""
    narrate("Setting up project directory")
    make_files(isolated_env.work / "project", {
        "README.md": b"# My Project\n",
        "src/main.py": b"print('hello')\n",
        "src/utils.py": b"def helper(): pass\n",
        "data/config.json": b'{"key": "value"}\n',
    })

    narrate("Taking baseline snapshot from inside the project directory")
    project_dir = isolated_env.work / "project"
    snap_r = run_ft(ft_binary, ["snap", "."],
                    cwd=project_dir, env=isolated_env.env)
    snap_file = isolated_env.root / "baseline.snap"
    snap_file.write_text(snap_r.stdout)

    narrate("Simulating a day of work: modify, add, delete files")
    time.sleep(0.05)
    make_file(project_dir / "src" / "main.py",
              b"print('hello world')\n")  # modified
    make_file(project_dir / "src" / "new_module.py",
              b"class NewFeature: pass\n")  # new
    os.remove(project_dir / "data" / "config.json")  # deleted

    narrate("Diffing against baseline")
    diff_r = run_ft(ft_binary, ["diff", str(snap_file), "."],
                    cwd=project_dir, env=isolated_env.env)
    entries = parse_diff_output(diff_r.stdout)
    statuses = {e.status for e in entries}

    check("modified" in statuses, "diff detects modification")
    check("new" in statuses, "diff detects new file")
    check("deleted" in statuses, "diff detects deletion")

    modified = [e for e in entries if e.status == "modified"]
    check(any("main.py" in e.path_a for e in modified), "main.py modification detected")

    new = [e for e in entries if e.status == "new"]
    check(any("new_module.py" in e.path_a for e in new), "new_module.py detected")

    deleted = [e for e in entries if e.status == "deleted"]
    check(any("config.json" in e.path_a for e in deleted), "config.json deletion detected")


def test_realistic_incremental_backup_check(ft_binary, isolated_env):
    """Use lsuniq against a backup snapshot to find unbacked files."""
    narrate("Creating 'backed up' state via snapshot")
    make_files(isolated_env.work / "docs", {
        "report.pdf": b"PDF content v1\n",
        "notes.txt": b"meeting notes\n",
    })
    snap_r = run_ft(ft_binary, ["snap", str(isolated_env.work / "docs")],
                    cwd=isolated_env.work, env=isolated_env.env)
    snap_file = isolated_env.root / "backup.snap"
    snap_file.write_text(snap_r.stdout)

    narrate("Adding new files (simulating new work since backup)")
    make_file(isolated_env.work / "docs" / "new_doc.txt", b"brand new\n")
    time.sleep(0.05)
    make_file(isolated_env.work / "docs" / "report.pdf", b"PDF content v2\n")  # modified

    narrate("Finding files not in backup snapshot")
    r = run_ft(ft_binary, ["lsuniq", "-S", str(snap_file),
                           str(isolated_env.work / "docs")],
               cwd=isolated_env.work, env=isolated_env.env)
    uniq_paths = get_paths_from_lines(r.stdout)
    uniq_basenames = {os.path.basename(p) for p in uniq_paths}

    check("new_doc.txt" in uniq_basenames, "new file needs backup")
    check("report.pdf" in uniq_basenames, "modified file needs backup")
    check("notes.txt" not in uniq_basenames, "unchanged file already backed up")


def test_realistic_multiple_snapshots_over_time(ft_binary, isolated_env):
    """Take multiple snapshots over time, diff between them."""
    narrate("Creating initial file set")
    make_files(isolated_env.work / "evolving", {
        "stable.txt": b"never changes\n",
        "volatile.txt": b"version 1\n",
    })

    snap1_r = run_ft(ft_binary, ["snap", str(isolated_env.work / "evolving")],
                     cwd=isolated_env.work, env=isolated_env.env)
    snap1_file = isolated_env.root / "snap1.snap"
    snap1_file.write_text(snap1_r.stdout)

    narrate("Evolving the tree")
    time.sleep(0.05)
    make_file(isolated_env.work / "evolving" / "volatile.txt", b"version 2\n")
    make_file(isolated_env.work / "evolving" / "newcomer.txt", b"appeared\n")

    snap2_r = run_ft(ft_binary, ["snap", str(isolated_env.work / "evolving")],
                     cwd=isolated_env.work, env=isolated_env.env)
    snap2_file = isolated_env.root / "snap2.snap"
    snap2_file.write_text(snap2_r.stdout)

    narrate("Diffing snap1 vs snap2 (pure snapshot diff, no disk I/O)")
    diff_r = run_ft(ft_binary, ["diff", str(snap1_file), str(snap2_file)],
                    cwd=isolated_env.work, env=isolated_env.env)
    entries = parse_diff_output(diff_r.stdout)

    modified = [e for e in entries if e.status == "modified"]
    new = [e for e in entries if e.status == "new"]
    check(any("volatile.txt" in e.path_a for e in modified), "volatile.txt modified between snaps")
    check(any("newcomer.txt" in e.path_a for e in new), "newcomer.txt new between snaps")

    # stable.txt should NOT appear in diff
    stable_entries = [e for e in entries if "stable.txt" in e.path_a]
    check(len(stable_entries) == 0, "stable.txt not in diff (unchanged)")


def test_realistic_reorganization_detection(ft_binary, isolated_env):
    """Move files between directories, diff detects as moved/relocated."""
    narrate("Creating organized directory structure")
    make_files(isolated_env.work / "tree", {
        "inbox/doc1.txt": b"document one\n",
        "inbox/doc2.txt": b"document two\n",
        "archive/old.txt": b"archived\n",
    })

    tree_dir = isolated_env.work / "tree"
    snap = run_ft(ft_binary, ["snap", "."],
                  cwd=tree_dir, env=isolated_env.env)
    snap_file = isolated_env.root / "before.snap"
    snap_file.write_text(snap.stdout)

    narrate("Reorganizing: moving doc1 from inbox to archive")
    os.rename(tree_dir / "inbox" / "doc1.txt",
              tree_dir / "archive" / "doc1.txt")

    diff_r = run_ft(ft_binary, ["diff", str(snap_file), "."],
                    cwd=tree_dir, env=isolated_env.env)
    entries = parse_diff_output(diff_r.stdout)

    narrate("Checking move/relocation was detected")
    move_statuses = {"moved", "relocated", "renamed"}
    moves = [e for e in entries if e.status in move_statuses]
    check(len(moves) >= 1,
          f"at least one move/relocation detected (got statuses: {[e.status for e in entries]})")
    check(any("doc1.txt" in (e.path_a + e.path_b) for e in moves),
          "doc1.txt move detected")


def test_realistic_large_mixed_tree(ft_binary, isolated_env):
    """Large directory tree with varied file types and sizes."""
    narrate("Creating mixed tree with 50 files across subdirs")
    files = {}
    for i in range(10):
        subdir = f"category_{i}"
        for j in range(5):
            ext = [".txt", ".py", ".json", ".md", ".bin"][j]
            content = f"file {i}-{j} content\n".encode() * (i + 1)
            files[f"{subdir}/file_{j}{ext}"] = content
    make_files(isolated_env.work / "mixed", files)

    narrate("Running ls on entire tree")
    r = run_ft(ft_binary, ["ls", str(isolated_env.work / "mixed")],
               cwd=isolated_env.work, env=isolated_env.env)
    entries = parse_ls_output(r.stdout)
    check(len(entries) == 50, f"all 50 files listed (got {len(entries)})")

    narrate("Running snap on entire tree")
    snap_r = run_ft(ft_binary, ["snap", str(isolated_env.work / "mixed")],
                    cwd=isolated_env.work, env=isolated_env.env)
    rows = parse_snap_tsv(snap_r.stdout)
    check(len(rows) == 50, f"all 50 files in snap (got {len(rows)})")
