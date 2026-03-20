"""Duplicate detection tests — lsdup correctness."""

from tests.helpers import (
    check,
    get_paths_from_lines,
    make_file,
    make_files,
    narrate,
    run_ft,
)


def test_lsdup_basic_duplicates(ft_binary, isolated_env):
    """Files in target with identical content in source are listed as dups."""
    narrate("Creating source with originals and target with copies")
    make_files(isolated_env.work / "source", {
        "original.txt": b"shared content\n",
        "unique_src.txt": b"only in source\n",
    })
    make_files(isolated_env.work / "target", {
        "copy.txt": b"shared content\n",
        "unique_tgt.txt": b"only in target\n",
    })

    r = run_ft(ft_binary, ["lsdup", "-S", str(isolated_env.work / "source"),
                           str(isolated_env.work / "target")],
               cwd=isolated_env.work, env=isolated_env.env)
    check(r.exit_code == 0, f"exit code 0 (got {r.exit_code})")

    paths = get_paths_from_lines(r.stdout)
    narrate("Verifying duplicate detection")
    check(any("copy.txt" in p for p in paths), "copy.txt listed as dup")
    check(not any("unique_tgt.txt" in p for p in paths), "unique_tgt.txt NOT listed as dup")


def test_lsdup_no_false_positives(ft_binary, isolated_env):
    """Files with unique content must not appear in lsdup output."""
    make_files(isolated_env.work / "src", {"s.txt": b"source\n"})
    make_files(isolated_env.work / "tgt", {
        "different1.txt": b"unique content 1\n",
        "different2.txt": b"unique content 2\n",
    })

    r = run_ft(ft_binary, ["lsdup", "-S", str(isolated_env.work / "src"),
                           str(isolated_env.work / "tgt")],
               cwd=isolated_env.work, env=isolated_env.env)
    paths = get_paths_from_lines(r.stdout)
    check(len(paths) == 0, f"no dups found (got {len(paths)} paths)")


def test_lsdup_zero_length_excluded(ft_binary, isolated_env):
    """Zero-length files must never appear as duplicates."""
    narrate("Creating empty files in source and target")
    make_file(isolated_env.work / "src" / "empty.txt", b"")
    make_file(isolated_env.work / "tgt" / "also_empty.txt", b"")

    r = run_ft(ft_binary, ["lsdup", "-S", str(isolated_env.work / "src"),
                           str(isolated_env.work / "tgt")],
               cwd=isolated_env.work, env=isolated_env.env)
    paths = get_paths_from_lines(r.stdout)
    check(len(paths) == 0, f"zero-length files excluded from dups (got {len(paths)})")


def test_lsdup_multi_source(ft_binary, isolated_env):
    """Multiple -S sources are aggregated for matching."""
    narrate("Creating two source dirs and one target")
    make_files(isolated_env.work / "src1", {"a.txt": b"content A\n"})
    make_files(isolated_env.work / "src2", {"b.txt": b"content B\n"})
    make_files(isolated_env.work / "tgt", {
        "match_a.txt": b"content A\n",
        "match_b.txt": b"content B\n",
        "unique.txt": b"no match\n",
    })

    r = run_ft(ft_binary, ["lsdup",
                           "-S", str(isolated_env.work / "src1"),
                           "-S", str(isolated_env.work / "src2"),
                           str(isolated_env.work / "tgt")],
               cwd=isolated_env.work, env=isolated_env.env)
    paths = get_paths_from_lines(r.stdout)
    narrate("Checking both source pools contributed")
    check(any("match_a.txt" in p for p in paths), "match_a found via src1")
    check(any("match_b.txt" in p for p in paths), "match_b found via src2")
    check(not any("unique.txt" in p for p in paths), "unique.txt not a dup")


def test_lsdup_target_included_flag(ft_binary, isolated_env):
    """-A counts target files as part of source pool (intra-target dups)."""
    narrate("Creating target with two identical files")
    make_files(isolated_env.work / "src", {"unrelated.txt": b"unrelated\n"})
    make_files(isolated_env.work / "tgt", {
        "twin1.txt": b"identical twins\n",
        "twin2.txt": b"identical twins\n",
        "loner.txt": b"unique loner\n",
    })

    narrate("Without -A: twins should not be dups (only source checked)")
    r1 = run_ft(ft_binary, ["lsdup", "-S", str(isolated_env.work / "src"),
                            str(isolated_env.work / "tgt")],
                cwd=isolated_env.work, env=isolated_env.env)
    paths1 = get_paths_from_lines(r1.stdout)
    check(not any("twin" in p for p in paths1), "without -A: twins not dups")

    narrate("With -A: twins should be dups (target included in source pool)")
    r2 = run_ft(ft_binary, ["lsdup", "-A", "-S", str(isolated_env.work / "src"),
                            str(isolated_env.work / "tgt")],
                cwd=isolated_env.work, env=isolated_env.env)
    paths2 = get_paths_from_lines(r2.stdout)
    check(any("twin1.txt" in p for p in paths2) or any("twin2.txt" in p for p in paths2),
          "with -A: at least one twin listed as dup")


def test_lsdup_self_overlap_no_self_match(ft_binary, isolated_env):
    """When source=target without -A, files don't match themselves."""
    narrate("Using same directory as source and target")
    make_files(isolated_env.work / "dir", {
        "a.txt": b"unique A\n",
        "b.txt": b"unique B\n",
    })

    r = run_ft(ft_binary, ["lsdup", "-S", str(isolated_env.work / "dir"),
                           str(isolated_env.work / "dir")],
               cwd=isolated_env.work, env=isolated_env.env)
    paths = get_paths_from_lines(r.stdout)
    check(len(paths) == 0, f"self-overlap without -A: no dups (got {len(paths)})")


def test_lsdup_source_is_snapshot(ft_binary, isolated_env):
    """Source can be a .snap file instead of a directory."""
    narrate("Creating source dir and snapping it")
    make_files(isolated_env.work / "src", {"orig.txt": b"snap source\n"})
    snap_r = run_ft(ft_binary, ["snap", str(isolated_env.work / "src")],
                    cwd=isolated_env.work, env=isolated_env.env)
    snap_file = isolated_env.work / "source.snap"
    snap_file.write_text(snap_r.stdout)

    narrate("Creating target with duplicate content")
    make_files(isolated_env.work / "tgt", {"dup.txt": b"snap source\n"})

    r = run_ft(ft_binary, ["lsdup", "-S", str(snap_file),
                           str(isolated_env.work / "tgt")],
               cwd=isolated_env.work, env=isolated_env.env)
    paths = get_paths_from_lines(r.stdout)
    check(any("dup.txt" in p for p in paths), "dup found via snapshot source")


def test_lsdup_large_identical_files(ft_binary, isolated_env):
    """Large files (1MB+) correctly detected as duplicates."""
    narrate("Creating 1MB identical files")
    big_content = b"x" * (1024 * 1024)
    make_file(isolated_env.work / "src" / "big.bin", big_content)
    make_file(isolated_env.work / "tgt" / "big_copy.bin", big_content)

    r = run_ft(ft_binary, ["lsdup", "-S", str(isolated_env.work / "src"),
                           str(isolated_env.work / "tgt")],
               cwd=isolated_env.work, env=isolated_env.env)
    paths = get_paths_from_lines(r.stdout)
    check(any("big_copy.bin" in p for p in paths), "1MB dup detected")
