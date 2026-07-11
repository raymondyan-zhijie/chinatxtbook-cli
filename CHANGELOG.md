# Changelog

## v1.1.0 (in development)

### Architectural Changes
- **Modular rewrite**: Single-file script (1734 lines) decomposed into package structure
  - `core/`: git_client, merger, evaluator, manifest, state, downloader, catalog, reporter
  - `utils/`: logging, lockfile, format, platform
  - `ui/`: Textual TUI (coming in Phase 2)
- **Fixed repository**: GitHub only (multi-source switching removed per v1.1 design)
- **Textual TUI**: Three-panel layout replacing menu-driven CLI (coming in Phase 2)

### Preserved from v1.0
- All safety-critical logic preserved byte-for-byte:
  - `evaluate_group()` → `core/evaluator.py`
  - `merge_one_file()` → `core/merger.py`
  - `invalidate_groups_by_diff()` → `core/state.py`
  - `redact_url()` / `safe_error()` → `utils/format.py`
- State file backward compatibility (v4.1, v4.2, v4.3, v1.0)
- Single-instance lock with stale recovery
- SHA256 stream hashing, atomic writes, fsync

### Removed from v1.0
- Gitee mirror support and latency-based source selection
- Transactional repo switching
- `--use-gitee`, `--repo` CLI flags

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
- Atomic merge: tmp → flush → fsync → re-read verify → os.replace
- POSIX parent directory fsync
