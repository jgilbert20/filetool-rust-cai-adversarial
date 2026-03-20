"""Edge case tests — special filenames, empty files, binary content, deep nesting."""

import os

from tests.helpers import (
    check,
    compute_sha256,
    make_file,
    narrate,
    parse_ls_output,
    run_ft,
)


def test_edge_files_with_spaces(ft_binary, isolated_env):
    """Filenames with spaces are handled correctly."""
    make_file(isolated_env.work / "my file.txt", b"space in name\n")
    make_file(isolated_env.work / "no spaces.txt", b"normal\n")

    r = run_ft(ft_binary, ["ls", "--full-hash", str(isolated_env.work)],
               cwd=isolated_env.work, env=isolated_env.env)
    entries = parse_ls_output(r.stdout)
    paths = [e.path for e in entries]
    check(any("my file.txt" in p for p in paths), "file with spaces listed")

    # Verify hash is correct
    for e in entries:
        if "my file.txt" in e.path:
            expected = compute_sha256(isolated_env.work / "my file.txt")
            check(e.hash == expected, "hash correct for file with spaces")


def test_edge_unicode_filenames(ft_binary, isolated_env):
    """Unicode filenames are handled correctly."""
    narrate("Creating files with unicode names")
    make_file(isolated_env.work / "café.txt", b"french\n")
    make_file(isolated_env.work / "naïve.txt", b"diacritics\n")

    r = run_ft(ft_binary, ["ls", str(isolated_env.work)],
               cwd=isolated_env.work, env=isolated_env.env)
    check(r.exit_code == 0, f"exit code 0 (got {r.exit_code})")
    entries = parse_ls_output(r.stdout)
    paths = " ".join(e.path for e in entries)
    check("café.txt" in paths, "café.txt listed")
    check("naïve.txt" in paths, "naïve.txt listed")


def test_edge_cjk_filenames(ft_binary, isolated_env):
    """CJK unicode filenames work."""
    make_file(isolated_env.work / "日本語.txt", b"japanese\n")
    r = run_ft(ft_binary, ["ls", str(isolated_env.work)],
               cwd=isolated_env.work, env=isolated_env.env)
    check(r.exit_code == 0, f"exit code 0 (got {r.exit_code})")
    entries = parse_ls_output(r.stdout)
    check(len(entries) >= 1, "CJK file listed")


def test_edge_deeply_nested(ft_binary, isolated_env):
    """20-level deep directory structure."""
    narrate("Creating 20-level deep directory")
    deep_path = isolated_env.work
    for i in range(20):
        deep_path = deep_path / f"level{i}"
    make_file(deep_path / "deep.txt", b"very deep\n")

    r = run_ft(ft_binary, ["ls", str(isolated_env.work)],
               cwd=isolated_env.work, env=isolated_env.env)
    entries = parse_ls_output(r.stdout)
    check(len(entries) == 1, f"found 1 file in deep tree (got {len(entries)})")
    check("deep.txt" in entries[0].path, "deep file path contains deep.txt")


def test_edge_binary_content(ft_binary, isolated_env):
    """Files with null bytes and binary content handled correctly."""
    binary_content = bytes(range(256)) + b"\x00" * 100
    make_file(isolated_env.work / "binary.bin", binary_content)

    r = run_ft(ft_binary, ["ls", "--full-hash", str(isolated_env.work)],
               cwd=isolated_env.work, env=isolated_env.env)
    entries = parse_ls_output(r.stdout)
    check(len(entries) == 1, "binary file listed")
    expected = compute_sha256(isolated_env.work / "binary.bin")
    check(entries[0].hash == expected, "binary file hash correct")


def test_edge_large_file(ft_binary, isolated_env):
    """1MB+ file produces correct hash."""
    content = os.urandom(1024 * 1024 + 37)  # 1MB + 37 bytes
    make_file(isolated_env.work / "large.bin", content)

    r = run_ft(ft_binary, ["ls", "--full-hash", str(isolated_env.work)],
               cwd=isolated_env.work, env=isolated_env.env)
    entries = parse_ls_output(r.stdout)
    check(len(entries) == 1, "large file listed")
    expected = compute_sha256(isolated_env.work / "large.bin")
    check(entries[0].hash == expected, "large file hash correct")


def test_edge_many_files(ft_binary, isolated_env):
    """Directory with 200+ files."""
    narrate("Creating 200 files")
    for i in range(200):
        make_file(isolated_env.work / f"file_{i:04d}.txt",
                  f"content {i}\n".encode())

    r = run_ft(ft_binary, ["ls", str(isolated_env.work)],
               cwd=isolated_env.work, env=isolated_env.env)
    entries = parse_ls_output(r.stdout)
    check(len(entries) == 200, f"all 200 files listed (got {len(entries)})")


def test_edge_dot_prefixed_files(ft_binary, isolated_env):
    """Hidden (dot-prefixed) files are listed."""
    make_file(isolated_env.work / ".hidden", b"hidden content\n")
    make_file(isolated_env.work / "visible.txt", b"visible\n")

    r = run_ft(ft_binary, ["ls", str(isolated_env.work)],
               cwd=isolated_env.work, env=isolated_env.env)
    entries = parse_ls_output(r.stdout)
    paths = [e.path for e in entries]
    check(any(".hidden" in p for p in paths), ".hidden file listed")
    check(any("visible.txt" in p for p in paths), "visible.txt listed")


def test_edge_file_named_like_snap(ft_binary, isolated_env):
    """A regular file named 'test.snap' treated as snapshot by ls."""
    narrate("Creating a .snap file with valid snap content")
    # Create a real snap first
    make_file(isolated_env.work / "real" / "f.txt", b"real content\n")
    snap_r = run_ft(ft_binary, ["snap", str(isolated_env.work / "real")],
                    cwd=isolated_env.work, env=isolated_env.env)
    snap_file = isolated_env.work / "test.snap"
    snap_file.write_text(snap_r.stdout)

    narrate("Running ls on the .snap file — should read snap entries")
    r = run_ft(ft_binary, ["ls", str(snap_file)],
               cwd=isolated_env.work, env=isolated_env.env)
    check(r.exit_code == 0, f"exit code 0 (got {r.exit_code})")
    entries = parse_ls_output(r.stdout)
    check(len(entries) >= 1, "entries read from snap file")


def test_edge_empty_file(ft_binary, isolated_env):
    """Zero-length files listed with correct empty-string SHA-256."""
    make_file(isolated_env.work / "empty.txt", b"")

    r = run_ft(ft_binary, ["ls", "--full-hash", str(isolated_env.work)],
               cwd=isolated_env.work, env=isolated_env.env)
    entries = parse_ls_output(r.stdout)
    check(len(entries) == 1, "empty file listed")
    # SHA-256 of empty string
    expected = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    check(entries[0].hash == expected, "empty file has correct SHA-256")
