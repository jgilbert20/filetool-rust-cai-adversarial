# ft — file tool

> **Contributors and AI agents: read [`TOUR.md`](TOUR.md) before grepping.**
> It maps every source file, doc file, and test category so you can find
> anything in one lookup instead of searching blindly through a large codebase.

A command-line utility for listing files with SHA-256 checksums, Finder tags, and human-readable sizes. Results are cached so repeated invocations over large file trees are fast.

## Usage

```
ft [-v] [--debug=<category>] <verb> [options] [paths...]
```

### Global Options

```
  -v, --verbose         Enable all debug output (alias for --debug=all)
  --debug=<category>    Enable specific debug categories (comma-separated):
                          all      enable all categories below
                          verbose  per-file state (cache hit/miss, staleness)
                          tier1    each .filetool write (path + row count)
                          db       each LMDB read/write (key + operation)
                          stats    per-invocation counters at exit
  -h, --help            Show help
```

### `ls` — list files with metadata

```
ft ls IMG_4823.CR3 IMG_4823.jpg .DS_Store
```

```
e3b0c44298fc  4.2 MB   [vacation, raw, unreviewed]  IMG_4823.CR3
a1f7d9023bcc  812 KB   [processed]                  IMG_4823.jpg
9c2a1b3e0d44  39 B     []                            .DS_Store
```

Columns: SHA-256 (truncated), human-readable size, Finder tags, filename. All columns are aligned.

**Options:**

```
  --full-hash         Print full 64-char SHA-256 instead of 12-char prefix
  --no-hash           Skip hash computation; show cached value or dashes
  -l, --no-recurse    Do not recurse into directories (default is recursive)
  -Q, --stats         Print invocation statistics to stderr after the listing
```

**`--stats` / `-Q` output (stderr):**

```
stats: stat()=6 readdir()=2 dir_entries=10 checksums=4 xattr()=4 time=0.003s
```

| Counter | Meaning |
|---------|---------|
| `stat()` | Total `fs::metadata()` calls (once per arg for directory detection, once per file for staleness check) |
| `readdir()` | `read_dir()` calls — one per directory walked during recursive traversal |
| `dir_entries` | Total directory entries returned by all `readdir()` calls |
| `checksums` | SHA-256 computations — 0 on a warm cache, N on a cold run |
| `bytes_checksummed` | Total bytes consumed by SHA-256 computations |
| `xattr()` | Extended attribute reads — 0 on a warm cache, N on a cold run |
| `time` | Wall-clock elapsed time for the entire `ls` invocation (seconds, 3 d.p.) |

On a warm cache (all files fresh) `checksums` and `xattr()` drop to 0 while `stat()` stays at `2×N`. The gap between the two reveals how much work the cache saved.

**Behavior:**

- Directory arguments are recursed into by default. Use `-l` to disable.
- Paths may also be snapshot files (`.snap`, `.snap.gz`, `.snap.br`). Snapshot entries are displayed using stored hashes, sizes, and tags — no disk I/O is performed for those entries. Paths are shown as stored in the snapshot (relative to its origin directory). Snapshot and directory arguments can be freely mixed in one invocation.
- Symbolic links are never followed. Symlink CLI arguments are skipped with an error; symlinked entries during recursive traversal are silently ignored.
- Files are processed in argument order.
- Per-file errors (missing, permission denied) go to stderr; processing continues; exit code remains 0.
- SHA-256 output matches `shasum -a 256` exactly.
- Finder tags are sorted lexicographically. Tags containing commas cause an immediate halt (non-zero exit).
- Filenames with spaces and unicode are handled correctly.

### `lsdup` — list duplicate files

```
ft lsdup -S <source> [-S <source> ...] [options] <target> [targets...]
```

Lists target files that have a content-identical copy in a source tree.
Identity is determined by SHA-256; file names and paths are irrelevant.
Uses file size as a cheap pre-filter — only size-matched files are hashed.
Zero-length files are always excluded (every empty file shares one hash).

Source and target paths may be directories, individual files, or snapshot files
(`.snap`, `.snap.gz`, `.snap.br`). When a snapshot is used as a source, its
stored hashes are used directly — no disk I/O is performed for those entries,
so `checksums=0` is expected in `-Q` output for snap-only sources.

**Options:**

```
  -S <path>              Source directory or snapshot to compare against (repeatable)
  -A, --target-included  Count target files as part of the source pool;
                         a file that exists only in the target is still a dup
                         if two target files share the same hash
  -l, --no-recurse       Do not recurse into directories (default: recursive)
  -Q, --stats            Print invocation statistics to stderr after output
```

**Examples:**

```sh
ft lsdup -S ~/Backup ~/Photos            # find photos already backed up
ft lsdup -S baseline.snap ~/Photos       # find photos present in the snapshot
ft lsdup -S baseline.snap.br ~/Photos    # same with brotli-compressed snapshot
ft lsdup -S /vol1 -S /vol2 ~/target      # check against two source trees
ft lsdup -A -S ~/src ~/dst               # include target in source pool
ft lsdup -Q -S ~/src ~/dst               # duplicate check with stats
```

### `lsuniq` — list unique files

```
ft lsuniq -S <source> [-S <source> ...] [options] <target> [targets...]
```

The exact complement of `lsdup` — lists only the target files that have **no**
content-identical copy in any source tree. When source and target overlap, a
file is not counted as its own duplicate.

Source and target paths may be directories, individual files, or snapshot files
(`.snap`, `.snap.gz`, `.snap.br`). When a snapshot is used as a source, its
stored hashes are used directly — no disk I/O is performed for those entries.

**Options:**

```
  -S <path>              Source directory or snapshot to compare against (repeatable)
  -A, --target-included  Count target files as part of the source pool
  -l, --no-recurse       Do not recurse into directories (default: recursive)
  -Q, --stats            Print invocation statistics to stderr after output
```

**Examples:**

```sh
ft lsuniq -S ~/Backup ~/Photos           # find photos not yet backed up
ft lsuniq -S baseline.snap ~/Photos      # find photos not in the snapshot
ft lsuniq -S /vol1 -S /vol2 ~/new        # find files unique to ~/new
```

### `rmdotfiles` — remove cached dotfiles

```
ft rmdotfiles <dir> [dirs...]
```

Recursively removes `.filetool` and `.filetool.tmp.*` cache files from the
named directories. After each removal the parent directory's `mtime` is
restored via `utimensat()` so it does not appear to have been modified.

Output: one path per removed file (relative to each root argument given on the
command line), followed by a summary line on stdout. Per-directory errors go
to stderr; processing continues; exit code is always 0.

Symbolic links are never followed during traversal or as CLI arguments.

**Examples:**

```sh
ft rmdotfiles ~/Photos                   # remove all .filetool files under ~/Photos
ft rmdotfiles ~/Photos ~/Videos          # clean multiple trees at once
```

**Summary line:**

```
3 dotfiles removed     # N files were deleted
no dotfiles found      # nothing matched
```

### `diff` — compare two trees or snapshots

```
ft diff [options] <A> [B]
```

Compare two file trees or snapshots and report differences. Each operand can
be a `.snap` file or a directory path. Use `-` to read a snapshot from stdin.

**With one operand:** if it is a `.snap` file, compares against the current
directory (sugar for `ft diff <snap> .`).

**With two operands:** `A` is the old/baseline side, `B` is the new/current
side. Reports new, deleted, renamed, moved, relocated, modified, and
metadata-changed files. Rename detection uses SHA-256 hash matching (1:1
unique hashes only; ambiguous matches are reported as deleted + new). Empty
files are excluded from rename matching.

**Options:**

```
  --full-hash         Show full 64-char SHA-256 in detail lines (default: 12)
  --no-renames        Disable rename/move/relocation detection
  --tsv               Machine-readable TSV output (status, path_a, path_b, detail)
  --name-only         Print only file paths, no status prefix or detail lines
  --status            Print status prefix + path (like git diff --name-status)
  -l, --no-recurse    Do not recurse into directory operands (default: recursive)
  -Q, --stats         Print invocation statistics to stderr after output
```

**Examples:**

```sh
ft diff baseline.snap ~/Photos           # what changed since the snapshot?
ft diff baseline.snap                    # same, comparing against CWD
ft diff old.snap new.snap                # compare two snapshots (no disk I/O)
ft diff ~/Photos ~/Backup               # compare two live directories
ft diff --no-renames old.snap .          # disable rename detection
ft diff --tsv old.snap .                 # machine-readable TSV output
ft snap . | ft diff - ~/other            # pipe snapshot via stdin
```

### `snap` — point-in-time snapshot

```
ft snap [options] <path> [paths...]
```

Captures a point-in-time snapshot of file metadata: full 64-char SHA-256
hashes, sizes, timestamps, and Finder tags for every file under the given
paths.  Cached hashes are reused when still fresh; only changed or uncached
files are (re-)hashed.

All file paths in the output are **relative to the snapshot file location**
(or the current directory when piping to stdout).

**When stdout is a terminal:** writes a TSV file named
`snapshot-YYYYMMDD-HHMMSS.snap` in the current directory, then prints the
filename to stdout.  Refuses to overwrite an existing file (exits 1 with an
error message).

**When stdout is not a terminal (piped or redirected):** emits the TSV
snapshot directly to stdout so you can pipe it into other tools or redirect
to a custom file.

**Output format — `# ft snap v1` TSV:**

```
# ft snap v1
path	dev	ino	size	mtime_nsec	ctime_nsec	sha256	tags	imprinted_at
photos/IMG_001.CR3	16777232	48291034	4404224	1709481600000000000	…	e3b0c44298fc…	raw,vacation	1709500000
```

| Field | Description |
|-------|-------------|
| `path` | Relative path from snapshot location (percent-encoded: `%` `\t` `\n` `\r`) |
| `dev` | Device ID from `stat()` |
| `ino` | Inode number |
| `size` | File size in bytes |
| `mtime_nsec` | Modification time (nanoseconds since epoch) |
| `ctime_nsec` | Change time (nanoseconds since epoch) |
| `sha256` | Full 64-char SHA-256 hex digest (always computed; never truncated) |
| `tags` | Comma-separated Finder tags, or `-` if none |
| `imprinted_at` | Unix timestamp (seconds) when this record was last cached |

**Options:**

```
  -l, --no-recurse    Do not recurse into directories (default is recursive)
  -Q, --stats         Print invocation statistics to stderr after the snapshot
```

**Side effect:** snap also writes/updates the two-tier cache (`.filetool`
dotfiles and LMDB), so a subsequent `ft ls` over the same tree runs at full
cache speed.

**Examples:**

```sh
ft snap ~/Photos                   # snapshot Photos → snapshot-YYYYMMDD-HHMMSS.snap
ft snap -Q .                       # snapshot CWD with performance stats
ft snap . > archive.tsv            # pipe TSV to a custom file
ft snap ~/A ~/B > combined.tsv     # snapshot multiple directories
```

## Caching

Results are cached in two tiers so that expensive operations (hashing, tag extraction) only run when a file has actually changed. The cache is validated on every access via `stat()`. Deleting any cache file is always safe — it just means the next run is slower.

- Local `.filetool` cache files use a compact tab-separated format (v2) and
  are intended to be portable with their directories. Existing JSON-format
  files (v1) are treated as cache misses and automatically rewritten as v2.
- The LMDB cache under `~/.filetool/cache` is machine-local and not portable.

See [CONCEPT.md](CONCEPT.md) for the full caching algorithm and [DESIGN.md](DESIGN.md) for the Rust implementation details.

## Environment Variables

### Runtime

| Variable | Effect |
|----------|--------|
| `HOME` | Locates the Tier 2 LMDB cache at `$HOME/.filetool/cache/`. Must be set; the binary exits with an error if it is absent. |

### Test-time / CI

| Variable | Effect |
|----------|--------|
| `FT_SNAP_TO_FILE` | When set to any non-empty value, `ft snap` writes a `.snap` file even when stdout is not a terminal. Used by integration tests that need a real file to inspect rather than capturing stdout. |
| `FT_DIAG_SUMMARY` | When set to `1`, appends a machine-readable diagnostic counter line to stderr at exit: `ft: diag: errors=N warnings=N verbose=N`. Useful in CI to detect silent regressions. |

These are the **only** knobs. There is no log-level variable, no feature-flag variable, and no path-override variable beyond `HOME`. Verbosity is controlled exclusively by the `-v` / `--verbose` / `--debug=` CLI flags.

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success. Individual per-file errors (missing files, permission denied) are non-fatal and do not change the exit code. |
| `1` | Usage error (unknown verb, missing required argument, unknown flag), or a missing/unreadable `-S` source path for `lsdup`/`lsuniq`, or `ft snap` refusing to overwrite an existing `.snap` file. |

## Building

```
cargo build --release
```

The binary is at `target/release/ft`.

## Testing

```
cargo test
```

Integration tests exercise the compiled binary end-to-end. See `tests/cli.rs`.

## Documentation

- [CONCEPT.md](CONCEPT.md) — Language-agnostic behavior spec, caching algorithm, File Imprint schema
- [DESIGN.md](DESIGN.md) — Rust implementation details, module layout, dependency choices

## Requirements

- Rust 1.84+ (edition 2021)
- macOS (Finder tag support uses macOS extended attributes)

## License

Unlicensed.
