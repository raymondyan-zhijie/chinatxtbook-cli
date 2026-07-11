"""State manager extracted from v1.0.

Handles state.json persistence, version compatibility, and stale group marking.
Source: v1.0 lines 296-343, 430-456, 1530-1623.
"""

import copy
import hashlib
import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from chinatxtbook import VERSION, COMPATIBLE_STATE_VERSIONS
from chinatxtbook.config import STATE_FILE
from chinatxtbook.utils.platform import is_interrupted


class StateManager:
    """Manages application state persistence with backward compatibility.

    Source: v1.0 new_state() (L297-315), load_state() (L317-333),
    save_state() (L335-339), invalidate_groups_by_diff() (L430-456).
    """

    def __init__(self, state_file: Path = STATE_FILE):
        self.state_file = state_file

    @staticmethod
    def new_state() -> dict:
        """Create a fresh state dict. Source: v1.0 lines 297-315."""
        return {
            "version": VERSION,
            "started_at": datetime.now().isoformat(),
            "last_run": None,
            "repo_source": None,
            "default_branch": None,
            "clone_done": False,
            "selection_done": False,
            "selected_paths": [],
            "selection_fingerprint": None,
            "checkout_done": False,
            "target_dirs": [],
            "groups": {},
            "last_failures": {},
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
                if ver not in COMPATIBLE_STATE_VERSIONS:
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
        """Atomically save state to file. Source: v1.0 lines 335-339."""
        state["last_run"] = datetime.now().isoformat()
        tmp = self.state_file.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(state, ensure_ascii=False, indent=2), "utf-8"
        )
        os.replace(tmp, self.state_file)

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
            import subprocess
            ok, out, _ = self._git_diff(work_dir, old, new)
            if ok:
                import re
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
