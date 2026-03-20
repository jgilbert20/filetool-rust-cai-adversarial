"""Adversarial cache manipulation — corrupt, truncate, bitflip dotfiles."""

import os
import time

from tests.helpers import (
    check,
    compute_sha256,
    make_file,
    make_files,
    narrate,
    parse_ls_output,
    run_ft,
)


def test_cache_corrupt_dotfile_garbage(ft_binary, isolated_env):
    """Write garbage to .filetool → tool should recover gracefully."""
    make_file(isolated_env.work / "f.txt", b"recover from garbage\n")
    expected = compute_sha256(isolated_env.work / "f.txt")

    narrate("Populating cache normally")
    run_ft(ft_binary, ["ls", str(isolated_env.work)],
           cwd=isolated_env.work, env=isolated_env.env)

    narrate("Corrupting .filetool with garbage bytes")
    dotfile = isolated_env.work / ".filetool"
    check(dotfile.exists(), ".filetool exists after ls")
    dotfile.write_bytes(b"\x00\xff\xfe GARBAGE CONTENT \x01\x02\x03\n" * 5)

    narrate("Re-running: should recover and produce correct hash")
    r = run_ft(ft_binary, ["ls", "--full-hash", str(isolated_env.work)],
               cwd=isolated_env.work, env=isolated_env.env)
    check(r.exit_code == 0, f"exit code 0 (got {r.exit_code})")
    entries = parse_ls_output(r.stdout)
    check(len(entries) >= 1, f"at least 1 entry (got {len(entries)})")
    check(entries[0].hash == expected, "hash correct after corrupt cache recovery")


def test_cache_truncated_dotfile(ft_binary, isolated_env):
    """Truncate .filetool to 0 bytes → graceful recovery."""
    make_file(isolated_env.work / "f.txt", b"truncation test\n")
    expected = compute_sha256(isolated_env.work / "f.txt")

    run_ft(ft_binary, ["ls", str(isolated_env.work)],
           cwd=isolated_env.work, env=isolated_env.env)

    narrate("Truncating .filetool to 0 bytes")
    dotfile = isolated_env.work / ".filetool"
    dotfile.write_bytes(b"")

    r = run_ft(ft_binary, ["ls", "--full-hash", str(isolated_env.work)],
               cwd=isolated_env.work, env=isolated_env.env)
    check(r.exit_code == 0, f"exit code 0 (got {r.exit_code})")
    entries = parse_ls_output(r.stdout)
    check(len(entries) >= 1, "file still listed")
    check(entries[0].hash == expected, "correct hash after truncated cache")


def test_cache_bitflip_in_hash(ft_binary, isolated_env):
    """Flip one character in cached hash → tool produces correct hash."""
    make_file(isolated_env.work / "f.txt", b"bitflip test\n")
    expected = compute_sha256(isolated_env.work / "f.txt")

    run_ft(ft_binary, ["ls", str(isolated_env.work)],
           cwd=isolated_env.work, env=isolated_env.env)

    narrate("Bitflipping one character in cached hash")
    dotfile = isolated_env.work / ".filetool"
    content = dotfile.read_text()
    # Find a hex char in a hash and flip it
    lines = content.split("\n")
    modified_lines = []
    for line in lines:
        if line.startswith("#") or line.startswith("filename") or not line.strip():
            modified_lines.append(line)
            continue
        fields = line.split("\t")
        if len(fields) >= 7 and len(fields[6]) == 64:
            # Flip first char of hash
            h = fields[6]
            flipped = chr(ord(h[0]) ^ 0x01) + h[1:]
            fields[6] = flipped
        modified_lines.append("\t".join(fields))
    dotfile.write_text("\n".join(modified_lines))

    narrate("Re-running: must detect staleness and re-hash correctly")
    # Touch the file so mtime is newer than the corrupted cache
    time.sleep(0.05)
    os.utime(isolated_env.work / "f.txt", None)

    r = run_ft(ft_binary, ["ls", "--full-hash", str(isolated_env.work)],
               cwd=isolated_env.work, env=isolated_env.env)
    entries = parse_ls_output(r.stdout)
    check(len(entries) >= 1, "file listed")
    check(entries[0].hash == expected, "correct hash after bitflipped cache")


def test_cache_wrong_mtime_in_dotfile(ft_binary, isolated_env):
    """Edit cached mtime to be far in the past → forces re-hash."""
    make_file(isolated_env.work / "f.txt", b"mtime perturb\n")
    expected = compute_sha256(isolated_env.work / "f.txt")

    run_ft(ft_binary, ["ls", str(isolated_env.work)],
           cwd=isolated_env.work, env=isolated_env.env)

    narrate("Setting cached mtime to far past (epoch)")
    dotfile = isolated_env.work / ".filetool"
    content = dotfile.read_text()
    lines = content.split("\n")
    modified_lines = []
    for line in lines:
        if line.startswith("#") or line.startswith("filename") or not line.strip():
            modified_lines.append(line)
            continue
        fields = line.split("\t")
        if len(fields) >= 5:
            fields[4] = "1000000000000000000"  # far past mtime_nsec
        modified_lines.append("\t".join(fields))
    dotfile.write_text("\n".join(modified_lines))

    r = run_ft(ft_binary, ["ls", "--full-hash", str(isolated_env.work)],
               cwd=isolated_env.work, env=isolated_env.env)
    entries = parse_ls_output(r.stdout)
    check(len(entries) >= 1, "file listed")
    check(entries[0].hash == expected,
          "correct hash after mtime perturbation in cache")


def test_cache_delete_lmdb_between_runs(ft_binary, isolated_env):
    """Remove LMDB cache between runs → graceful fallback."""
    make_file(isolated_env.work / "f.txt", b"lmdb delete test\n")
    expected = compute_sha256(isolated_env.work / "f.txt")

    narrate("First run to populate both tiers")
    run_ft(ft_binary, ["ls", str(isolated_env.work)],
           cwd=isolated_env.work, env=isolated_env.env)

    narrate("Also clearing dotfile cache to force LMDB usage")
    run_ft(ft_binary, ["rmdotfiles", str(isolated_env.work)],
           cwd=isolated_env.work, env=isolated_env.env)

    narrate("Deleting LMDB cache")
    run_ft(ft_binary, ["clear-db"],
           cwd=isolated_env.work, env=isolated_env.env)

    narrate("Re-running: should work fine (re-hash from scratch)")
    r = run_ft(ft_binary, ["ls", "--full-hash", str(isolated_env.work)],
               cwd=isolated_env.work, env=isolated_env.env)
    check(r.exit_code == 0, f"exit code 0 (got {r.exit_code})")
    entries = parse_ls_output(r.stdout)
    check(entries[0].hash == expected, "correct hash after both caches cleared")


def test_cache_header_only_dotfile(ft_binary, isolated_env):
    """Dotfile with only header line (no data rows) → re-hashes gracefully."""
    make_file(isolated_env.work / "f.txt", b"header only\n")
    expected = compute_sha256(isolated_env.work / "f.txt")

    run_ft(ft_binary, ["ls", str(isolated_env.work)],
           cwd=isolated_env.work, env=isolated_env.env)

    narrate("Replacing dotfile with header-only content")
    dotfile = isolated_env.work / ".filetool"
    dotfile.write_text("# ft v2\nfilename\tdev\tino\tsize\tmtime_nsec\tctime_nsec\tsha256\ttags\timprinted_at\n")

    r = run_ft(ft_binary, ["ls", "--full-hash", str(isolated_env.work)],
               cwd=isolated_env.work, env=isolated_env.env)
    check(r.exit_code == 0, f"exit code 0 (got {r.exit_code})")
    entries = parse_ls_output(r.stdout)
    check(len(entries) >= 1, "file still listed")
    check(entries[0].hash == expected, "correct hash with header-only dotfile")
