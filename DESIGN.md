# Red Team Test Design

## Philosophy

This is **outside-in, black-box adversarial testing**. We have zero knowledge of
the `ft` tool's internals. Our goal is to find **incorrect behavior** — wrong
output, incomplete results, stale caches, ungraceful error handling — not crashes
or security vulnerabilities.

We approach this as a hostile user who trusts nothing: we verify every hash
independently, perturb mtimes, corrupt caches, feed bad input, and check that
every documented invariant actually holds.

## Threat Model (Correctness Bugs)

### 1. Cache Staleness
The tool uses a two-tier cache (per-directory `.filetool` dotfiles + global LMDB).
Caches can become stale when:
- File content changes but mtime is preserved (e.g., `cp --preserve=timestamps`)
- File is replaced with different content at the exact same byte length
- `.filetool` is carried to a different machine (different inode numbers)
- LMDB is out of sync with dotfiles
- Multiple files change simultaneously

**Tests**: Modify content after caching, touch mtime without changing content,
replace file atomically, corrupt dotfile, delete LMDB between runs.

### 2. Duplicate/Unique Set Integrity
`lsdup` and `lsuniq` must be exact complements. Violations include:
- A file appearing in both sets
- A file appearing in neither set
- Zero-length files leaking into either set
- `-A` (target-included) miscounting self-matches

**Tests**: Verify union = all non-empty files, intersection = empty, test with
and without `-A`, test with overlapping source/target paths.

### 3. Snapshot Fidelity
Snapshots must faithfully capture file state. Risks:
- Hash in snap disagrees with `ft ls --full-hash`
- Paths not properly relativized
- Fields missing or in wrong order
- Re-snapping unchanged tree produces different output

**Tests**: Cross-check snap hashes against ls and independent SHA-256, verify
path relativity from different CWDs, validate TSV structure.

### 4. Diff Accuracy
Diff must correctly categorize changes. Risks:
- Rename detection false positives (two unrelated files with same content)
- Missed modifications (stale cache serves old hash)
- Metadata-only changes misclassified
- Ambiguous renames (multiple files with same hash) not handled correctly

**Tests**: Create controlled rename/move/modify/delete scenarios, test ambiguous
cases, verify `--no-renames` disables detection.

### 5. Path Handling
Path-related bugs are common in file tools:
- CWD affects output paths unexpectedly
- Snap path relativity breaks with unusual CWD
- Spaces, unicode, dots in filenames cause parsing issues
- Very long paths truncated or mangled

**Tests**: Run same commands from different CWDs, use adversarial filenames,
deeply nested structures.

### 6. Error Gracelessness
Non-fatal errors should be reported but not halt processing:
- Permission-denied files should be skipped with stderr message
- Missing target paths for lsuniq should be non-fatal
- Missing -S source paths should be fatal (exit 1)
- Unknown flags/verbs should exit 1 with clear message

**Tests**: Create unreadable files, pass bad arguments, mix valid and invalid paths.

## Test Isolation Architecture

```
/tmp/pytest-XXXXX/
  test_foo/
    home/                  ← $HOME for this test
      .filetool/
        cache/             ← LMDB lives here
    work/                  ← CWD for ft invocations
      <fixture files>
```

Each test gets a completely fresh filesystem tree. No test can affect another.
No test touches the real `$HOME` or any host directory.

## Narration Protocol

Every test step prints to stdout via `rich`:
```
[Step 1] Creating fixture files
         a.txt (12 bytes): "hello world\n"
         b.txt (12 bytes): "hello world\n"  (duplicate of a.txt)
         c.txt (15 bytes): "unique content\n"

[Step 2] Running: ft ls --full-hash work/
         Exit code: 0
         stdout (3 lines)

[Step 3] Verifying hashes against independent SHA-256
         ✓ a.txt: a948904f2f0f... matches
         ✓ b.txt: a948904f2f0f... matches
         ✓ c.txt: 5b6f32614d97... matches
```

This creates a forensic paper trail that makes test failures immediately
diagnosable without re-running in debug mode.

## Key Invariants Under Test

1. `ft ls --full-hash` SHA-256 = `hashlib.sha256(content).hexdigest()`
2. `ft ls` 12-char prefix = first 12 chars of full hash
3. `set(lsdup) | set(lsuniq) == set(all non-empty files in target)`
4. `set(lsdup) & set(lsuniq) == set()` (empty intersection)
5. Zero-length files never appear in lsdup or lsuniq output
6. `ft snap` hash field matches `ft ls --full-hash`
7. `ft diff A A` produces empty output (identical trees)
8. `ft rmdotfiles` leaves no `.filetool` files and restores parent mtime
9. `ft clear-db` removes all files under `~/.filetool/cache/`
10. `--no-cache` and cached run produce identical hash output
11. After content change, next `ft ls` reflects new hash (no stale cache)
12. Symlinks are always skipped, never followed
13. Per-file errors are non-fatal (exit 0), missing -S is fatal (exit 1)

## Test Naming Convention

Tests follow: `test_<verb>_<scenario>[_<variant>]`

Examples:
- `test_ls_hash_correctness`
- `test_lsdup_zero_length_excluded`
- `test_diff_rename_ambiguous_same_hash`
- `test_cache_corrupt_dotfile_graceful_recovery`
