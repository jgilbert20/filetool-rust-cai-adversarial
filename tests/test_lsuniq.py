"""Unique file detection tests — lsuniq correctness."""

from tests.helpers import (
    check,
    get_paths_from_lines,
    make_file,
    make_files,
    narrate,
    run_ft,
)


def test_lsuniq_basic(ft_binary, isolated_env):
    """Files with no content match in source are listed as unique."""
    narrate("Creating source and target with one match, one unique")
    make_files(isolated_env.work / "src", {"shared.txt": b"shared\n"})
    make_files(isolated_env.work / "tgt", {
        "copy.txt": b"shared\n",
        "novel.txt": b"only in target\n",
    })

    r = run_ft(ft_binary, ["lsuniq", "-S", str(isolated_env.work / "src"),
                           str(isolated_env.work / "tgt")],
               cwd=isolated_env.work, env=isolated_env.env)
    check(r.exit_code == 0, f"exit code 0 (got {r.exit_code})")
    paths = get_paths_from_lines(r.stdout)
    check(any("novel.txt" in p for p in paths), "novel.txt listed as unique")
    check(not any("copy.txt" in p for p in paths), "copy.txt NOT listed as unique")


def test_lsuniq_no_false_positives(ft_binary, isolated_env):
    """Duplicate files must NOT appear in lsuniq output."""
    make_files(isolated_env.work / "src", {"orig.txt": b"same content\n"})
    make_files(isolated_env.work / "tgt", {"dup.txt": b"same content\n"})

    r = run_ft(ft_binary, ["lsuniq", "-S", str(isolated_env.work / "src"),
                           str(isolated_env.work / "tgt")],
               cwd=isolated_env.work, env=isolated_env.env)
    paths = get_paths_from_lines(r.stdout)
    check(len(paths) == 0, f"no unique files (all are dups) — got {len(paths)}")


def test_lsuniq_zero_length_excluded(ft_binary, isolated_env):
    """Zero-length files should not appear in lsuniq output."""
    make_file(isolated_env.work / "src" / "x.txt", b"something\n")
    make_file(isolated_env.work / "tgt" / "empty.txt", b"")

    r = run_ft(ft_binary, ["lsuniq", "-S", str(isolated_env.work / "src"),
                           str(isolated_env.work / "tgt")],
               cwd=isolated_env.work, env=isolated_env.env)
    paths = get_paths_from_lines(r.stdout)
    check(not any("empty.txt" in p for p in paths),
          "zero-length file excluded from lsuniq output")


def test_lsuniq_self_overlap_all_unique(ft_binary, isolated_env):
    """Same dir as source+target without -A: all files are unique (no self-match)."""
    make_files(isolated_env.work / "dir", {
        "a.txt": b"aaa\n",
        "b.txt": b"bbb\n",
    })

    r = run_ft(ft_binary, ["lsuniq", "-S", str(isolated_env.work / "dir"),
                           str(isolated_env.work / "dir")],
               cwd=isolated_env.work, env=isolated_env.env)
    paths = get_paths_from_lines(r.stdout)
    check(any("a.txt" in p for p in paths), "a.txt is unique (no self-match)")
    check(any("b.txt" in p for p in paths), "b.txt is unique (no self-match)")


def test_lsuniq_target_included_filters(ft_binary, isolated_env):
    """-A makes intra-target dups disappear from unique list."""
    narrate("Creating target with twin files and one loner")
    make_files(isolated_env.work / "src", {"unrelated.txt": b"unrelated\n"})
    make_files(isolated_env.work / "tgt", {
        "twin1.txt": b"identical\n",
        "twin2.txt": b"identical\n",
        "loner.txt": b"unique loner\n",
    })

    r = run_ft(ft_binary, ["lsuniq", "-A", "-S", str(isolated_env.work / "src"),
                           str(isolated_env.work / "tgt")],
               cwd=isolated_env.work, env=isolated_env.env)
    paths = get_paths_from_lines(r.stdout)
    narrate("With -A, twins are dups of each other → only loner is unique")
    check(any("loner.txt" in p for p in paths), "loner.txt is unique")
    # Twins should NOT appear since they dup each other
    twin_count = sum(1 for p in paths if "twin" in p)
    check(twin_count == 0, f"twins not listed as unique with -A (got {twin_count})")


def test_lsuniq_missing_target_nonfatal(ft_binary, isolated_env):
    """Missing target path is non-fatal (error on stderr, exit 0)."""
    make_files(isolated_env.work / "src", {"x.txt": b"x\n"})

    r = run_ft(ft_binary, ["lsuniq", "-S", str(isolated_env.work / "src"),
                           str(isolated_env.work / "nonexistent")],
               cwd=isolated_env.work, env=isolated_env.env)
    check(r.exit_code == 0, f"exit code 0 for missing target (got {r.exit_code})")
    check("nonexistent" in r.stderr or len(r.stderr) > 0,
          "error message on stderr for missing target")
