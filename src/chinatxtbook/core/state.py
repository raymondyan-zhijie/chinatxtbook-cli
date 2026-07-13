"""State manager extracted from v1.0.

Handles state.json persistence, version compatibility, and stale group marking.
Source: v1.0 lines 296-343, 430-456, 1530-1623.
"""

import hashlib
import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from chinatxtbook import VERSION, COMPATIBLE_STATE_VERSIONS, MIGRATABLE_STATE_VERSIONS
from chinatxtbook.config import STATE_FILE


class StateManager:
    """Manages application state persistence with backward compatibility.

    Source: v1.0 new_state() (L297-315), load_state() (L317-333),
    save_state() (L335-339), invalidate_groups_by_diff() (L430-456).
    """

    def __init__(self, state_file: Path = STATE_FILE):
        self.state_file = state_file

    @staticmethod
    def new_state() -> dict:
        """Create a fresh v1.1 state dict per design doc 2.3 Section 12."""
        return {
            "schema_version": VERSION,
            "app_version": VERSION,
            "version": VERSION,  # backward compat
            "created_at": datetime.now().isoformat(),
            "updated_at": None,
            "started_at": datetime.now().isoformat(),
            "last_run": None,
            # Repository
            "repo_source": None,
            "default_branch": None,
            "clone_done": False,
            # Selection (v1.1 two-layer model)
            "selection": {
                "requires_reselection": False,
                "selected_books": [],
                "selected_files": [],
                "fingerprint": None,
                "updated_at": None,
            },
            "selected_paths": [],
            "selection_done": False,
            "selection_fingerprint": None,
            "checkout_done": False,
            "target_dirs": [],
            # Groups (cross-selection persistent cache)
            "groups": {},
            "last_failures": {},
            # Tasks
            "tasks": {"active": [], "history": []},
            # Preferences
            "preferences": {
                "verify_hashes": True,
                "clean_parts_after_verify": False,
            },
            # Updates
            "updates": {
                "ignored_software_version": None,
                "last_software_check_at": None,
                "last_catalog_check_at": None,
            },
            # Migration
            "migration": None,
            # Size cache
            "size_cache": None,
        }

    def load(self) -> dict:
        """Load state from file, handling version compatibility.

        Source: v1.0 lines 317-333.
        """
        if self.state_file.exists():
            try:
                s = json.loads(self.state_file.read_text("utf-8"))
                ver = str(s.get("version", ""))
                if ver in MIGRATABLE_STATE_VERSIONS:
                    # v1.0→v1.1 migration: preserve groups (hashes/sizes),
                    # clear directory selections (selected_paths etc.)
                    base = self.new_state()
                    # Preserve groups with legacy_imported flag
                    old_groups = s.get("groups") or {}
                    for k, v in old_groups.items():
                        if v.get("status") == "ok" and v.get("sha256"):
                            v["legacy_imported"] = True
                            v["requires_reselection"] = True
                    base["groups"] = old_groups
                    base["repo_source"] = s.get("repo_source")
                    base["default_branch"] = s.get("default_branch")
                    base["clone_done"] = s.get("clone_done", False)
                    # Migration record
                    base["migration"] = {
                        "from_version": ver,
                        "to_version": VERSION,
                        "migrated_at": datetime.now().isoformat(),
                        "notes": "Cleared selected_paths; user must re-select",
                    }
                    return base
                elif ver not in COMPATIBLE_STATE_VERSIONS:
                    backup = self.state_file.with_name(
                        self.state_file.name + f".{s.get('version', 'old')}.bak"
                    )
                    shutil.copy(self.state_file, backup)
                    import logging
                    logging.warning(
                        f"不兼容的旧版本状态文件，已备份为 {backup.name}，重新开始"
                    )
                    return self.new_state()
                base = self.new_state()
                base.update(s)
                base["version"] = VERSION
                return base
            except Exception:
                import logging
                logging.warning("状态文件损坏，重新开始")
        return self.new_state()

    def save(self, state: dict):
        """Atomically save state to file with fsync. Source: v1.0 lines 335-339."""
        state["last_run"] = datetime.now().isoformat()
        tmp = self.state_file.with_suffix(".json.tmp")
        data = json.dumps(state, ensure_ascii=False, indent=2)
        tmp.write_text(data, "utf-8")
        # fsync + atomic replace (F-12 fix)
        with open(tmp, "ab") as f:
            os.fsync(f.fileno())
        os.replace(tmp, self.state_file)
        if os.name == "posix":
            try:
                dfd = os.open(str(self.state_file.parent), os.O_RDONLY)
                try:
                    os.fsync(dfd)
                finally:
                    os.close(dfd)
            except OSError:
                pass

    @staticmethod
    def selection_fingerprint(paths: list[str]) -> str:
        """Generate a hash fingerprint for a set of selected paths.
        Source: v1.0 lines 341-342.
        """
        return hashlib.sha256(
            "\n".join(sorted(paths)).encode("utf-8")
        ).hexdigest()

    def invalidate_by_diff(
        self, state: dict, work_dir: Path, old: Optional[str], new: Optional[str]
    ) -> Optional[int]:
        """Mark changed groups as stale using git diff.

        Preserves historical parts set for upstream deletion detection.
        Source: v1.0 lines 430-456.
        """
        groups = state.get("groups") or {}

        if old and new:
            ok, out, _ = self._git_diff(work_dir, old, new)
            if ok:
                from chinatxtbook.core.manifest import SPLIT_RE

                invalidated = 0
                for p in out.strip().split("\n"):
                    p = p.strip()
                    if not p:
                        continue
                    name = os.path.basename(p)
                    m = SPLIT_RE.match(name)
                    key = (
                        (Path(p).parent / m.group(1)).as_posix()
                        if m
                        else Path(p).as_posix()
                    )
                    if key in groups and not groups[key].get("stale"):
                        groups[key]["stale"] = True
                        invalidated += 1
                return invalidated

        # Diff failed or HEAD missing: mark all stale (fail-closed)
        for rec in groups.values():
            rec["stale"] = True
        return None

    @staticmethod
    def _git_diff(work_dir: Path, old: str, new: str):
        """Run git diff --name-only. Source: v1.0 line 439."""
        import subprocess
        try:
            r = subprocess.run(
                ["git", "diff", "--name-only", old, new],
                cwd=str(work_dir),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env={
                    **os.environ,
                    "GIT_TERMINAL_PROMPT": "0",
                },
            )
            return r.returncode == 0, r.stdout, r.stderr
        except Exception as e:
            return False, "", str(e)


def groups_in_selection(state: dict) -> dict:
    """Filter groups dict to only those in current selection.

    Source: v1.0 lines 1531-1540.
    """
    sels = [s.rstrip("/") for s in (state.get("selected_paths") or [])]
    groups = state.get("groups", {})
    if not sels:
        return {}
    return {
        k: v
        for k, v in groups.items()
        if any(k == s or k.startswith(s + "/") for s in sels)
    }
