"""Integration tests for DownloadOrchestrator (F-02/F-03 main pipeline).

Validates the clone -> checkout -> scan -> merge orchestration that the CLI
now wires (F-02). GitClient is mocked; filesystem operations use tmp_path.
"""

from unittest.mock import MagicMock

import pytest

from chinatxtbook.core.downloader import DownloadOrchestrator
from chinatxtbook.core.state import StateManager


@pytest.fixture
def mock_git():
    """MagicMock GitClient with sensible success defaults."""
    git = MagicMock()
    git.is_repo_valid.return_value = True
    git.get_head_commit.return_value = "abc123"
    git.detect_default_branch.return_value = "master"
    git.path_exists_in_tree.return_value = True
    git.sparse_checkout.return_value = True
    git.checkout.return_value = True
    git.clone.return_value = True
    git.fetch.return_value = True
    git.rev_parse.return_value = "abc123"
    git.merge_ff.return_value = True
    git.restore_files.return_value = True
    return git


@pytest.fixture
def orch(mock_git, tmp_path, monkeypatch):
    """DownloadOrchestrator with WORK_DIR patched to tmp_path."""
    monkeypatch.setattr("chinatxtbook.core.downloader.WORK_DIR", tmp_path)
    sm = StateManager(tmp_path / "state.json")
    return DownloadOrchestrator(mock_git, sm, log_callback=lambda m, level="INFO": None)


SPLIT_FILES = ["小学/数学/book.pdf.1", "小学/数学/book.pdf.2"]


class TestClone:
    def test_clone_success_sets_state(self, orch, mock_git):
        mock_git.is_repo_valid.return_value = False
        mock_git.clone.return_value = True
        state = {"clone_done": False}
        assert orch.clone(state, "https://example.com/repo.git") is True
        assert state["clone_done"] is True

    def test_clone_failure(self, orch, mock_git):
        mock_git.is_repo_valid.return_value = False
        mock_git.clone.return_value = False
        state = {"clone_done": False}
        assert orch.clone(state, "https://example.com/repo.git") is False
        assert state["clone_done"] is False


class TestCheckout:
    def test_checkout_success(self, orch, mock_git, tmp_path):
        # Post-checkout verification requires the dir to exist on disk
        (tmp_path / "小学" / "数学").mkdir(parents=True)
        (tmp_path / "小学" / "数学" / "book.pdf.1").write_bytes(b"x")
        mock_git.ls_tree.return_value = ["小学/数学/book.pdf.1"]
        state = {"selected_paths": ["小学/数学/"]}
        assert orch.checkout(state, "master") is True
        assert state["checkout_done"] is True
        mock_git.sparse_checkout.assert_called_once()
        mock_git.checkout.assert_called_once_with("master")

    def test_checkout_empty_selection_fails(self, orch):
        state = {"selected_paths": []}
        assert orch.checkout(state, "master") is False

    def test_checkout_stale_path_fails_fail_closed(self, orch, mock_git):
        state = {"selected_paths": ["小学/不存在/"]}
        mock_git.path_exists_in_tree.return_value = False
        assert orch.checkout(state, "master") is False
        mock_git.sparse_checkout.assert_not_called()


class TestScan:
    def test_scan_returns_manifest(self, orch, mock_git):
        mock_git.ls_tree.return_value = SPLIT_FILES
        state = {"selected_paths": ["小学/数学/"]}
        manifest = orch.scan(state, force=True)
        assert manifest is not None
        assert "小学/数学" in manifest
        assert "book.pdf" in manifest["小学/数学"]
        assert state["target_dirs"] == ["小学/数学"]

    def test_scan_fail_closed_on_git_error(self, orch, mock_git):
        mock_git.ls_tree.return_value = None
        state = {"selected_paths": ["小学/数学/"]}
        assert orch.scan(state, force=True) is None

    def test_scan_empty_tree_returns_empty_manifest(self, orch, mock_git):
        # Empty ls-tree (no split files) is not an error -> {} manifest
        mock_git.ls_tree.return_value = []
        state = {"selected_paths": ["小学/数学/"]}
        manifest = orch.scan(state, force=True)
        assert manifest == {}

    def test_scan_preserves_target_dirs_without_force(self, orch, mock_git):
        mock_git.ls_tree.return_value = SPLIT_FILES
        state = {"selected_paths": ["小学/数学/"], "target_dirs": ["cached"]}
        manifest = orch.scan(state, force=False)
        assert manifest is not None
        # target_dirs not overwritten when not forced
        assert state["target_dirs"] == ["cached"]


class TestMergeDryRun:
    def test_dry_run_previews_without_merging(self, orch, mock_git):
        mock_git.ls_tree.return_value = SPLIT_FILES
        state = {"selected_paths": ["小学/数学/"]}
        manifest = orch.scan(state, force=True)
        assert manifest is not None
        # dry-run must not touch the filesystem or call restore_files
        assert orch.merge(state, manifest, dry_run=True) is True
        mock_git.restore_files.assert_not_called()

    def test_merge_no_target_dirs_is_noop(self, orch):
        state = {"target_dirs": []}
        assert orch.merge(state, {}, dry_run=True) is True
