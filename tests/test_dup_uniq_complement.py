"""Complement invariant: lsdup ∪ lsuniq = all non-zero-length target files."""

from tests.helpers import (
    check,
    get_paths_from_lines,
    make_file,
    make_files,
    narrate,
    run_ft,
    parse_ls_output,
)


def _get_all_nonzero_target_files(ft_binary, env, target_dir):
    """Get all non-zero-length files in target via ft ls."""
    r = run_ft(ft_binary, ["ls", str(target_dir)],
               cwd=target_dir.parent, env=env)
    entries = parse_ls_output(r.stdout)
    # Filter out zero-length
    return {e.path for e in entries if not e.size_str.startswith("0")}


def test_complement_union_equals_all(ft_binary, isolated_env):
    """lsdup paths ∪ lsuniq paths = all non-zero-length target files."""
    narrate("Creating mixed source and target")
    make_files(isolated_env.work / "src", {
        "shared1.txt": b"content A\n",
        "shared2.txt": b"content B\n",
    })
    make_files(isolated_env.work / "tgt", {
        "dup1.txt": b"content A\n",
        "dup2.txt": b"content B\n",
        "unique1.txt": b"only here 1\n",
        "unique2.txt": b"only here 2\n",
        "empty.txt": b"",
    })

    src = str(isolated_env.work / "src")
    tgt = str(isolated_env.work / "tgt")

    narrate("Running lsdup and lsuniq")
    dup_r = run_ft(ft_binary, ["lsdup", "-S", src, tgt],
                   cwd=isolated_env.work, env=isolated_env.env)
    uniq_r = run_ft(ft_binary, ["lsuniq", "-S", src, tgt],
                    cwd=isolated_env.work, env=isolated_env.env)

    dup_paths = set(get_paths_from_lines(dup_r.stdout))
    uniq_paths = set(get_paths_from_lines(uniq_r.stdout))

    narrate("Checking union = all non-empty target files")
    all_files = _get_all_nonzero_target_files(ft_binary, isolated_env.env,
                                               isolated_env.work / "tgt")
    union = dup_paths | uniq_paths
    # Normalize paths for comparison (extract basenames)
    union_basenames = {p.split("/")[-1] for p in union}
    all_basenames = {p.split("/")[-1] for p in all_files}
    check(union_basenames == all_basenames,
          f"union ({len(union_basenames)}) = all non-empty ({len(all_basenames)})")


def test_complement_no_intersection(ft_binary, isolated_env):
    """lsdup ∩ lsuniq = empty set (no file in both)."""
    make_files(isolated_env.work / "src", {"s.txt": b"source\n"})
    make_files(isolated_env.work / "tgt", {
        "d.txt": b"source\n",
        "u.txt": b"unique\n",
    })

    src = str(isolated_env.work / "src")
    tgt = str(isolated_env.work / "tgt")

    dup_r = run_ft(ft_binary, ["lsdup", "-S", src, tgt],
                   cwd=isolated_env.work, env=isolated_env.env)
    uniq_r = run_ft(ft_binary, ["lsuniq", "-S", src, tgt],
                    cwd=isolated_env.work, env=isolated_env.env)

    dup_paths = set(get_paths_from_lines(dup_r.stdout))
    uniq_paths = set(get_paths_from_lines(uniq_r.stdout))

    intersection = dup_paths & uniq_paths
    check(len(intersection) == 0,
          f"intersection is empty (got {intersection})")


def test_complement_with_target_included(ft_binary, isolated_env):
    """Complement holds even with -A flag."""
    make_files(isolated_env.work / "src", {"base.txt": b"base\n"})
    make_files(isolated_env.work / "tgt", {
        "twin1.txt": b"twin\n",
        "twin2.txt": b"twin\n",
        "solo.txt": b"solo content\n",
        "base_dup.txt": b"base\n",
    })

    src = str(isolated_env.work / "src")
    tgt = str(isolated_env.work / "tgt")

    dup_r = run_ft(ft_binary, ["lsdup", "-A", "-S", src, tgt],
                   cwd=isolated_env.work, env=isolated_env.env)
    uniq_r = run_ft(ft_binary, ["lsuniq", "-A", "-S", src, tgt],
                    cwd=isolated_env.work, env=isolated_env.env)

    dup_paths = set(get_paths_from_lines(dup_r.stdout))
    uniq_paths = set(get_paths_from_lines(uniq_r.stdout))

    intersection = dup_paths & uniq_paths
    check(len(intersection) == 0, f"no intersection with -A (got {intersection})")

    union_basenames = {p.split("/")[-1] for p in dup_paths | uniq_paths}
    expected = {"twin1.txt", "twin2.txt", "solo.txt", "base_dup.txt"}
    check(union_basenames == expected,
          f"union = all target files with -A: {union_basenames} == {expected}")
