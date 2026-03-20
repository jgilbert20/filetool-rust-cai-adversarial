"""Cache integrity tests — staleness, mtime perturb, --no-cache consistency."""

import os
import time

from tests.helpers import (
    check,
    compute_sha256,
    make_file,
    make_files,
    narrate,
    parse_ls_output,
    parse_stats,
    run_ft,
)


def test_cache_content_change_detected(ft_binary, isolated_env):
    """After modifying file content, next run reflects new hash."""
    f = isolated_env.work / "mutable.txt"
    make_file(f, b"original content\n")

    narrate("First run to populate cache")
    r1 = run_ft(ft_binary, ["ls", "--full-hash", str(isolated_env.work)],
                cwd=isolated_env.work, env=isolated_env.env)
    hash1 = parse_ls_output(r1.stdout)[0].hash

    narrate("Modifying file content")
    time.sleep(0.05)
    make_file(f, b"modified content\n")
    expected_hash = compute_sha256(f)

    narrate("Second run: cache must detect change")
    r2 = run_ft(ft_binary, ["ls", "--full-hash", str(isolated_env.work)],
                cwd=isolated_env.work, env=isolated_env.env)
    hash2 = parse_ls_output(r2.stdout)[0].hash

    check(hash2 != hash1, "hash changed after content modification")
    check(hash2 == expected_hash, f"new hash matches independent SHA-256")


def test_cache_mtime_only_change(ft_binary, isolated_env):
    """Touch file (mtime change, same content) → hash still correct."""
    f = isolated_env.work / "touched.txt"
    content = b"stable content\n"
    make_file(f, content)
    expected = compute_sha256(f)

    narrate("First run to cache")
    run_ft(ft_binary, ["ls", str(isolated_env.work)],
           cwd=isolated_env.work, env=isolated_env.env)

    narrate("Touching file (mtime changes, content unchanged)")
    time.sleep(0.05)
    os.utime(f, None)  # update mtime to now

    narrate("Re-running: hash should still be correct")
    r = run_ft(ft_binary, ["ls", "--full-hash", str(isolated_env.work)],
               cwd=isolated_env.work, env=isolated_env.env)
    entry = parse_ls_output(r.stdout)[0]
    check(entry.hash == expected, "hash unchanged after mtime-only change")


def test_cache_file_deletion(ft_binary, isolated_env):
    """Deleted file disappears from output on rerun."""
    make_files(isolated_env.work, {
        "keep.txt": b"keep\n",
        "remove.txt": b"remove\n",
    })

    narrate("First run")
    r1 = run_ft(ft_binary, ["ls", str(isolated_env.work)],
                cwd=isolated_env.work, env=isolated_env.env)
    check(len(parse_ls_output(r1.stdout)) == 2, "two files initially")

    narrate("Deleting one file")
    os.remove(isolated_env.work / "remove.txt")

    narrate("Re-running: deleted file must be gone")
    r2 = run_ft(ft_binary, ["ls", str(isolated_env.work)],
                cwd=isolated_env.work, env=isolated_env.env)
    entries = parse_ls_output(r2.stdout)
    paths = [e.path for e in entries]
    check(not any("remove.txt" in p for p in paths), "removed file gone from output")
    check(any("keep.txt" in p for p in paths), "kept file still present")


def test_cache_file_addition(ft_binary, isolated_env):
    """New file appears in output on rerun."""
    make_file(isolated_env.work / "existing.txt", b"existing\n")

    narrate("First run")
    run_ft(ft_binary, ["ls", str(isolated_env.work)],
           cwd=isolated_env.work, env=isolated_env.env)

    narrate("Adding a new file")
    make_file(isolated_env.work / "newcomer.txt", b"new arrival\n")

    narrate("Re-running: new file must appear")
    r = run_ft(ft_binary, ["ls", str(isolated_env.work)],
               cwd=isolated_env.work, env=isolated_env.env)
    entries = parse_ls_output(r.stdout)
    paths = [e.path for e in entries]
    check(any("newcomer.txt" in p for p in paths), "new file appears in output")


def test_cache_no_cache_same_hashes(ft_binary, isolated_env):
    """--no-cache and normal run produce identical hashes."""
    make_files(isolated_env.work, {
        "a.txt": b"hash consistency\n",
        "b.txt": b"also check\n",
    })

    narrate("Normal run (with cache)")
    r1 = run_ft(ft_binary, ["ls", "--full-hash", str(isolated_env.work)],
                cwd=isolated_env.work, env=isolated_env.env)

    narrate("--no-cache run")
    r2 = run_ft(ft_binary, ["--no-cache", "ls", "--full-hash", str(isolated_env.work)],
                cwd=isolated_env.work, env=isolated_env.env)

    entries1 = {os.path.basename(e.path): e.hash for e in parse_ls_output(r1.stdout)}
    entries2 = {os.path.basename(e.path): e.hash for e in parse_ls_output(r2.stdout)}
    check(entries1 == entries2, "cached and --no-cache produce identical hashes")


def test_cache_rmdotfiles_then_rerun(ft_binary, isolated_env):
    """After rmdotfiles, rerun still produces correct output."""
    make_file(isolated_env.work / "f.txt", b"cache then clear\n")
    expected = compute_sha256(isolated_env.work / "f.txt")

    narrate("First run to populate cache")
    run_ft(ft_binary, ["ls", str(isolated_env.work)],
           cwd=isolated_env.work, env=isolated_env.env)

    narrate("Clearing cache with rmdotfiles")
    run_ft(ft_binary, ["rmdotfiles", str(isolated_env.work)],
           cwd=isolated_env.work, env=isolated_env.env)

    narrate("Re-running: should still produce correct hash")
    r = run_ft(ft_binary, ["ls", "--full-hash", str(isolated_env.work)],
               cwd=isolated_env.work, env=isolated_env.env)
    entry = parse_ls_output(r.stdout)[0]
    check(entry.hash == expected, "hash correct after cache clear")


def test_cache_cross_command_reuse(ft_binary, isolated_env):
    """Cache populated by ls is reused by snap (checksums=0 on second run)."""
    make_file(isolated_env.work / "f.txt", b"cross command\n")

    narrate("Populating cache with ls")
    run_ft(ft_binary, ["ls", str(isolated_env.work)],
           cwd=isolated_env.work, env=isolated_env.env)

    narrate("Running snap -Q: should reuse cache (checksums=0)")
    r = run_ft(ft_binary, ["snap", "-Q", str(isolated_env.work)],
               cwd=isolated_env.work, env=isolated_env.env)
    stats = parse_stats(r.stderr)
    checksums = int(stats.get("checksums", -1))
    check(checksums == 0, f"snap reused ls cache: checksums={checksums}")


def test_cache_same_content_different_size_file(ft_binary, isolated_env):
    """Replace file with same-length but different content → new hash."""
    f = isolated_env.work / "sneaky.txt"
    make_file(f, b"AAAA")  # 4 bytes

    narrate("First run to cache")
    r1 = run_ft(ft_binary, ["ls", "--full-hash", str(isolated_env.work)],
                cwd=isolated_env.work, env=isolated_env.env)
    hash1 = parse_ls_output(r1.stdout)[0].hash

    narrate("Replacing with same-length different content")
    time.sleep(0.05)
    make_file(f, b"BBBB")  # still 4 bytes
    expected = compute_sha256(f)

    r2 = run_ft(ft_binary, ["ls", "--full-hash", str(isolated_env.work)],
                cwd=isolated_env.work, env=isolated_env.env)
    hash2 = parse_ls_output(r2.stdout)[0].hash
    check(hash2 != hash1, "hash changed even though file size stayed same")
    check(hash2 == expected, "new hash is correct")
