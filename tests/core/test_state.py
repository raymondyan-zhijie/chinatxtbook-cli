"""Tests for StateManager."""

import json
from datetime import datetime

import pytest

from chinatxtbook.core.state import StateManager, groups_in_selection


class TestStateManager:
    @pytest.fixture
    def state_mgr(self, tmp_path):
        state_file = tmp_path / "state.json"
        return StateManager(state_file=state_file)

    def test_new_state(self, state_mgr):
        s = state_mgr.new_state()
        assert s["version"] == "1.1.0"
        assert s["clone_done"] is False
        assert s["groups"] == {}
        assert s["last_failures"] == {}

    def test_save_and_load(self, state_mgr):
        s = state_mgr.new_state()
        s["clone_done"] = True
        s["groups"]["test/key"] = {
            "status": "ok", "size": 1024,
            "sha256": "a" * 64, "parts": [1, 2],
            "at": datetime.now().isoformat(),
        }
        state_mgr.save(s)

        loaded = state_mgr.load()
        assert loaded["clone_done"] is True
        assert "test/key" in loaded["groups"]

    def test_load_v1_0_state(self, state_mgr, sample_state_v1_0):
        """v1.0 state files should load and be upgraded."""
        state_mgr.state_file.write_text(
            json.dumps(sample_state_v1_0, ensure_ascii=False, indent=2),
            "utf-8",
        )
        loaded = state_mgr.load()
        assert loaded["version"] == "1.1.0"
        assert loaded["clone_done"] is True
        assert "小学/语文/test.pdf" in loaded["groups"]

    def test_incompatible_version_backup(self, state_mgr):
        """Incompatible version should trigger backup and fresh start."""
        old_state = {"version": "3.0", "clone_done": True, "groups": {}}
        state_mgr.state_file.write_text(json.dumps(old_state), "utf-8")

        loaded = state_mgr.load()
        assert loaded["version"] == "1.1.0"
        # Old state should be backed up
        backups = list(state_mgr.state_file.parent.glob("state.json.*.bak"))
        assert len(backups) == 1

    def test_corrupted_state_handled(self, state_mgr):
        """Corrupted JSON should trigger fresh start."""
        state_mgr.state_file.write_text("not valid json {{{")

        loaded = state_mgr.load()
        assert loaded["version"] == "1.1.0"
        assert loaded["clone_done"] is False

    def test_selection_fingerprint(self):
        fp1 = StateManager.selection_fingerprint(["小学/语文/", "小学/数学/"])
        fp2 = StateManager.selection_fingerprint(["小学/语文/", "小学/数学/"])
        fp3 = StateManager.selection_fingerprint(["初中/数学/"])

        assert fp1 == fp2
        assert fp1 != fp3
        assert len(fp1) == 64


class TestGroupsInSelection:
    def test_filters_by_selected_paths(self):
        state = {
            "selected_paths": ["小学/语文/"],
            "groups": {
                "小学/语文/test.pdf": {"status": "ok"},
                "小学/数学/test.pdf": {"status": "ok"},
                "小学/语文/subdir/test.pdf": {"status": "ok"},
            },
        }
        result = groups_in_selection(state)
        assert "小学/语文/test.pdf" in result
        assert "小学/语文/subdir/test.pdf" in result
        assert "小学/数学/test.pdf" not in result

    def test_empty_selection_returns_empty(self):
        state = {
            "selected_paths": [],
            "groups": {"小学/语文/test.pdf": {"status": "ok"}},
        }
        assert groups_in_selection(state) == {}
