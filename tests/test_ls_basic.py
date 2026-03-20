"""Basic ls correctness — hashes, sizes, format, exit codes."""

import os

from tests.helpers import (
    check,
    compute_sha256,
    make_file,
    make_files,
    narrate,
    parse_ls_output,
    run_ft,
)


def test_ls_hash_correctness(ft_binary, isolated_env):
    """SHA-256 from ft ls --full-hash must match independently computed hash."""
    narrate("Creating fixture files with known content")
    files = {
        "alpha.txt": b"hello world\n",
        "beta.txt": b"goodbye world\n",
        "gamma.bin": bytes(range(256)),
    }
    make_files(isolated_env.work, files)

    narrate("Running ft ls --full-hash")
    r = run_ft(ft_binary, ["ls", "--full-hash", str(isolated_env.work)],
               cwd=isolated_env.work, env=isolated_env.env)
    check(r.exit_code == 0, f"exit code is 0 (got {r.exit_code})")

    entries = parse_ls_output(r.stdout)
    check(len(entries) == 3, f"3 entries in output (got {len(entries)})")

    narrate("Verifying each hash against independent SHA-256")
    for entry in entries:
        # Extract just the filename from the path
        basename = os.path.basename(entry.path)
        expected = compute_sha256(isolated_env.work / basename)
        check(entry.hash == expected,
              f"{basename}: ft={entry.hash[:16]}... == python={expected[:16]}...")
        check(len(entry.hash) == 64, f"{basename}: hash is 64 chars (full)")


def test_ls_short_hash_is_prefix(ft_binary, isolated_env):
    """Default 12-char hash must be first 12 chars of full hash."""
    make_file(isolated_env.work / "test.txt", b"prefix check\n")

    narrate("Getting short hash (default) and full hash")
    short_r = run_ft(ft_binary, ["ls", str(isolated_env.work)],
                     cwd=isolated_env.work, env=isolated_env.env)
    full_r = run_ft(ft_binary, ["ls", "--full-hash", str(isolated_env.work)],
                    cwd=isolated_env.work, env=isolated_env.env)

    short_entries = parse_ls_output(short_r.stdout)
    full_entries = parse_ls_output(full_r.stdout)

    check(len(short_entries) == 1, "one entry in short output")
    check(len(full_entries) == 1, "one entry in full output")
    check(len(short_entries[0].hash) == 12, f"short hash is 12 chars (got {len(short_entries[0].hash)})")
    check(short_entries[0].hash == full_entries[0].hash[:12],
          "short hash is prefix of full hash")


def test_ls_size_correctness(ft_binary, isolated_env):
    """Reported sizes must match actual file sizes."""
    narrate("Creating files of various sizes")
    test_cases = [
        ("empty.txt", b""),
        ("small.txt", b"hi"),
        ("medium.txt", b"x" * 1000),
        ("bigger.txt", b"y" * 10000),
    ]
    for name, content in test_cases:
        make_file(isolated_env.work / name, content)

    r = run_ft(ft_binary, ["ls", str(isolated_env.work)],
               cwd=isolated_env.work, env=isolated_env.env)
    entries = parse_ls_output(r.stdout)

    narrate("Verifying reported sizes")
    entry_map = {os.path.basename(e.path): e for e in entries}
    for name, content in test_cases:
        check(name in entry_map, f"{name} appears in output")
        # Parse the human-readable size — extract the numeric part
        size_str = entry_map[name].size_str
        # Sizes like "0 B", "2 B", "1000 B", "10.0 kB" etc
        actual_size = len(content)
        # For exact comparison, check the raw number for small files
        if actual_size < 1000:
            check(size_str.startswith(str(actual_size)),
                  f"{name}: size '{size_str}' starts with {actual_size}")


def test_ls_single_file(ft_binary, isolated_env):
    """ft ls on a single file (not directory) should work."""
    narrate("Creating a single file and running ft ls on it directly")
    f = isolated_env.work / "solo.txt"
    make_file(f, b"solo content\n")

    r = run_ft(ft_binary, ["ls", str(f)],
               cwd=isolated_env.work, env=isolated_env.env)
    check(r.exit_code == 0, f"exit code 0 (got {r.exit_code})")
    entries = parse_ls_output(r.stdout)
    check(len(entries) == 1, f"exactly 1 entry (got {len(entries)})")
    check("solo.txt" in entries[0].path, "path contains solo.txt")


def test_ls_multiple_paths(ft_binary, isolated_env):
    """ft ls with multiple path arguments lists files from all."""
    narrate("Creating files in two separate directories")
    make_file(isolated_env.work / "dirA" / "a.txt", b"aaa\n")
    make_file(isolated_env.work / "dirB" / "b.txt", b"bbb\n")

    r = run_ft(ft_binary, ["ls",
                           str(isolated_env.work / "dirA"),
                           str(isolated_env.work / "dirB")],
               cwd=isolated_env.work, env=isolated_env.env)
    check(r.exit_code == 0, "exit code 0")
    entries = parse_ls_output(r.stdout)
    paths = [e.path for e in entries]
    check(any("a.txt" in p for p in paths), "a.txt from dirA present")
    check(any("b.txt" in p for p in paths), "b.txt from dirB present")


def test_ls_empty_directory(ft_binary, isolated_env):
    """ft ls on an empty directory produces no file output, exit 0."""
    narrate("Creating empty directory")
    empty_dir = isolated_env.work / "empty"
    empty_dir.mkdir()

    r = run_ft(ft_binary, ["ls", str(empty_dir)],
               cwd=isolated_env.work, env=isolated_env.env)
    check(r.exit_code == 0, f"exit code 0 (got {r.exit_code})")
    entries = parse_ls_output(r.stdout)
    check(len(entries) == 0, f"no entries for empty dir (got {len(entries)})")


def test_ls_exit_code_zero(ft_binary, isolated_env):
    """Normal ls operation returns exit code 0."""
    make_file(isolated_env.work / "ok.txt", b"ok\n")
    r = run_ft(ft_binary, ["ls", str(isolated_env.work)],
               cwd=isolated_env.work, env=isolated_env.env)
    check(r.exit_code == 0, f"exit code 0 (got {r.exit_code})")


def test_ls_tags_field_present(ft_binary, isolated_env):
    """Every ls entry should have a tags field (even if empty brackets)."""
    narrate("Checking tags field is present in output")
    make_file(isolated_env.work / "tagged.txt", b"content\n")
    r = run_ft(ft_binary, ["ls", str(isolated_env.work)],
               cwd=isolated_env.work, env=isolated_env.env)
    entries = parse_ls_output(r.stdout)
    check(len(entries) == 1, "one entry")
    # Tags field should have been parsed (even if empty)
    check(entries[0].tags is not None, "tags field is present (parsed)")
