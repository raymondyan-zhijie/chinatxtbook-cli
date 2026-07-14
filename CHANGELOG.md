# Changelog

## v1.1.1

### Fixes
- **R5-1 (Critical)**: Package `ui/styles.tcss` in wheel/sdist -- TUI crashed on
  `pip install` due to missing CSS (`StylesheetError`). Added `ui/*.tcss` to
  `package-data`; verified tcss accessible in installed wheel.
- **R5-2**: Include `schemas/app-state.schema.json` in EXE build (`--add-data`),
  so schema validation works in the Windows executable.
- **R5-3**: CI `build-wheel` now asserts `styles.tcss` is in the wheel (catches
  packaging regressions that `twine check` misses).

## v1.1.0

### Architectural Changes
- **Modular rewrite**: Single-file script (1734 lines) decomposed into package structure
  - `core/`: git_client, merger, evaluator, manifest, state, downloader, catalog, reporter
  - `utils/`: logging, lockfile, format, platform, paths
  - `ui/`: Textual TUI (three-panel layout, 9 screens, 14 hotkeys)
- **Fixed repository**: GitHub only (multi-source switching removed per v1.1 design)
- **Textual TUI** (default mode): three-panel layout (catalog tree / book list / detail)
  replacing the menu-driven CLI; CLI retained as headless fallback with full
  download/merge support via DownloadOrchestrator

### New in v1.1
- **TUI mode**: interactive browsing, selection, download pipeline, task management,
  logs, update checks, help/diagnostics (F-01)
- **CLI mode** (`--cli`): headless download/merge wired through DownloadOrchestrator -
  supports `--status`, `--list`, `--report`, `--update`, `--reselect`, `--clean`,
  `--dry-run`, `--skip-verify`, `--dirs`, `--workers` (F-02)
- **State schema validation**: `schemas/app-state.schema.json` + jsonschema cross-field
  invariants, packaged in-wheel so validation holds in installed artifacts (F-16/M-1)
- **Path safety**: PathPolicy rejects traversal/absolute/symlink/NUL on all write paths,
  including restore-to-workspace and output (F-17/M-3)
- **Disk space check** before merge (F-07), **single-instance lock** with stale
  reclamation (F-06), **group persistence** for breakpoint resume (F-04)

### Preserved from v1.0
- All safety-critical logic preserved byte-for-byte:
  - `evaluate_group()` -> `core/evaluator.py`
  - `merge_one_file()` -> `core/merger.py`
  - `invalidate_groups_by_diff()` -> `core/state.py`
  - `redact_url()` / `safe_error()` -> `utils/format.py`
- State file backward compatibility (v4.1, v4.2, v4.3, v1.0)
- SHA256 stream hashing, atomic writes, fsync
- Fail-closed Git tree manifest reading, stale record marking, single-part rejection

### Removed from v1.0
- Gitee mirror support and latency-based source selection
- Transactional repo switching
- `--use-gitee`, `--repo` CLI flags

### Quality gates
- ruff (strict) + black + compileall + pytest (82 tests) + pip-audit in CI
- Package builds: wheel + sdist (schema included)

---

## v1.0 (2026-07-11)

First stable release after six rounds of security audit (dev versions v4.0–v4.3 RC).
See `README_v1.0.md` for full changelog history.

Key safety mechanisms:
- SHA256 as sole completion evidence
- Fail-closed Git tree manifest reading
- Stale record marking with historical parts preservation
- Single-part group rejection
- Non-manifest group rejection
- Atomic merge: tmp -> flush -> fsync -> re-read verify -> os.replace
- POSIX parent directory fsync
