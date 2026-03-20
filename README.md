# ft Red Team Test Suite

Black-box adversarial test suite for the `ft` (filetool) CLI. Designed to expose
incorrect, incomplete, or ungraceful behavior through outside-in testing — no
source code required.

## Quick Start

```bash
pip install -r requirements.txt
pytest --ft-binary=binaries-to-test/ft-linux-cai -v
```

## What This Tests

The `ft` tool is a Rust CLI for listing files with SHA-256 checksums, sizes, and
macOS Finder tags, with a two-tier caching system. This suite verifies
correctness of every command (`ls`, `lsdup`, `lsuniq`, `snap`, `diff`, `report`,
`rmdotfiles`, `clear-db`) through ~100 independent scenarios.

### Test Categories

| Category | File | Focus |
|---|---|---|
| **ls basics** | `test_ls_basic.py` | Hash correctness, size, format, exit codes |
| **ls options** | `test_ls_options.py` | `--full-hash`, `--no-hash`, `-l`, `-Q`, `--no-cache` |
| **Duplicates** | `test_lsdup.py` | Dup detection, `-A`, zero-length exclusion |
| **Uniques** | `test_lsuniq.py` | Unique detection, complement of lsdup |
| **Complement** | `test_dup_uniq_complement.py` | lsdup ∪ lsuniq = all files |
| **Snapshots** | `test_snap.py` | TSV format, field count, hash agreement |
| **Diff** | `test_diff.py` | new/deleted/renamed/moved/modified detection |
| **Report** | `test_report.py` | Per-file dup/unique report format |
| **Cache** | `test_cache.py` | Staleness, mtime perturb, `--no-cache` |
| **Cache adversarial** | `test_cache_adversarial.py` | Corrupt/truncate/bitflip dotfiles |
| **Edge cases** | `test_edge_cases.py` | Spaces, unicode, binary, deep nesting |
| **Symlinks** | `test_symlinks.py` | Skipping, dangling, dir symlinks |
| **CWD** | `test_cwd.py` | Path consistency across working dirs |
| **Errors** | `test_error_conditions.py` | Bad args, missing paths, permissions |
| **rmdotfiles** | `test_rmdotfiles.py` | Cache removal, mtime restoration |
| **Stats** | `test_stats.py` | `-Q` counters, `FT_DIAG_SUMMARY` |
| **Realistic** | `test_realistic.py` | Photo library, backup workflow scenarios |

## Design Principles

- **Fully isolated**: Every test creates a fresh temp directory with its own `$HOME`
- **Narrated output**: Each step prints what it's doing and the pass/fail result
- **Binary-agnostic**: Pass `--ft-binary=/path/to/ft` to test any build
- **Independent verification**: Hashes computed independently via Python's hashlib
- **Adversarial mindset**: Tests actively try to break the tool, not just confirm happy paths

## For the Green Team

Run this suite in CI to catch regressions:

```bash
pytest --ft-binary=/path/to/your/ft -v --tb=short
```

The test suite never reads or decompiles the binary — it's pure behavioral testing.
