"""Report command tests — per-file dup/unique report."""

import re

from tests.helpers import (
    check,
    make_files,
    narrate,
    run_ft,
)


def _parse_report(stdout):
    """Parse report output into list of (status, target_path, source_paths)."""
    entries = []
    current = None
    for line in stdout.strip().splitlines():
        if not line.strip():
            continue
        # Match: [N  dup] or [unique] at start
        m = re.match(r"\[(\S+(?:\s+\S+)?)\]\s+\[([^\]]*)\]\s+(.+)", line)
        if m:
            if current:
                entries.append(current)
            status = m.group(1).strip()
            target = m.group(3).strip()
            current = {"status": status, "target": target, "sources": []}
        elif current and line.startswith(" "):
            # Indented source line
            sm = re.match(r"\s+\[([^\]]*)\]\s+(.+)", line)
            if sm:
                current["sources"].append(sm.group(2).strip())
    if current:
        entries.append(current)
    return entries


def test_report_all_files_covered(ft_binary, isolated_env):
    """Every target file appears in report output."""
    make_files(isolated_env.work / "src", {"s.txt": b"source\n"})
    make_files(isolated_env.work / "tgt", {
        "dup.txt": b"source\n",
        "uniq.txt": b"unique\n",
    })

    r = run_ft(ft_binary, ["report", "-S", str(isolated_env.work / "src"),
                           str(isolated_env.work / "tgt")],
               cwd=isolated_env.work, env=isolated_env.env)
    check(r.exit_code == 0, f"exit code 0 (got {r.exit_code})")

    entries = _parse_report(r.stdout)
    targets = {e["target"].split("/")[-1] for e in entries}
    check("dup.txt" in targets, "dup.txt appears in report")
    check("uniq.txt" in targets, "uniq.txt appears in report")


def test_report_dup_format(ft_binary, isolated_env):
    """Dup entries show [N dup] with indented source paths."""
    make_files(isolated_env.work / "src", {
        "orig1.txt": b"shared content\n",
        "orig2.txt": b"shared content\n",
    })
    make_files(isolated_env.work / "tgt", {"match.txt": b"shared content\n"})

    r = run_ft(ft_binary, ["report", "-S", str(isolated_env.work / "src"),
                           str(isolated_env.work / "tgt")],
               cwd=isolated_env.work, env=isolated_env.env)
    entries = _parse_report(r.stdout)
    dup_entries = [e for e in entries if "dup" in e["status"]]
    check(len(dup_entries) >= 1, "at least one dup entry")
    for e in dup_entries:
        check(len(e["sources"]) >= 1,
              f"dup entry has source paths listed (got {len(e['sources'])})")


def test_report_unique_format(ft_binary, isolated_env):
    """Unique entries show [unique] with no indented sources."""
    make_files(isolated_env.work / "src", {"s.txt": b"src only\n"})
    make_files(isolated_env.work / "tgt", {"novel.txt": b"target only\n"})

    r = run_ft(ft_binary, ["report", "-S", str(isolated_env.work / "src"),
                           str(isolated_env.work / "tgt")],
               cwd=isolated_env.work, env=isolated_env.env)
    entries = _parse_report(r.stdout)
    unique_entries = [e for e in entries if "unique" in e["status"]]
    check(len(unique_entries) >= 1, "at least one unique entry")
    for e in unique_entries:
        check(len(e["sources"]) == 0,
              f"unique entry has no sources (got {len(e['sources'])})")


def test_report_target_included(ft_binary, isolated_env):
    """-A makes intra-target dups show in report."""
    make_files(isolated_env.work / "src", {"base.txt": b"base\n"})
    make_files(isolated_env.work / "tgt", {
        "twin1.txt": b"twins\n",
        "twin2.txt": b"twins\n",
        "solo.txt": b"unique solo\n",
    })

    r = run_ft(ft_binary, ["report", "-A", "-S", str(isolated_env.work / "src"),
                           str(isolated_env.work / "tgt")],
               cwd=isolated_env.work, env=isolated_env.env)
    entries = _parse_report(r.stdout)

    narrate("With -A, twins should be reported as dups of each other")
    dup_targets = {e["target"].split("/")[-1] for e in entries if "dup" in e["status"]}
    check("twin1.txt" in dup_targets or "twin2.txt" in dup_targets,
          "at least one twin reported as dup")
    unique_targets = {e["target"].split("/")[-1] for e in entries if "unique" in e["status"]}
    check("solo.txt" in unique_targets, "solo.txt is unique")


def test_report_source_count_matches(ft_binary, isolated_env):
    """Number N in [N dup] matches actual count of source paths listed."""
    make_files(isolated_env.work / "src", {
        "copy1.txt": b"content\n",
        "copy2.txt": b"content\n",
        "copy3.txt": b"content\n",
    })
    make_files(isolated_env.work / "tgt", {"match.txt": b"content\n"})

    r = run_ft(ft_binary, ["report", "-S", str(isolated_env.work / "src"),
                           str(isolated_env.work / "tgt")],
               cwd=isolated_env.work, env=isolated_env.env)
    entries = _parse_report(r.stdout)
    dup_entries = [e for e in entries if "dup" in e["status"]]
    for e in dup_entries:
        # Extract N from "N  dup" or "N dup"
        m = re.match(r"(\d+)\s+dup", e["status"])
        if m:
            n = int(m.group(1))
            check(n == len(e["sources"]),
                  f"[{n} dup] matches {len(e['sources'])} listed sources")
