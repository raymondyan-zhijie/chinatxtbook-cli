"""Tests for GitClient - git operations wrapper (F-13 coverage)."""

from unittest.mock import MagicMock, patch

import pytest

from chinatxtbook.core.git_client import GitClient


@pytest.fixture
def git(tmp_path):
    return GitClient(work_dir=tmp_path, log_callback=lambda m, level="INFO": None)


def _mock_run(returncode=0, stdout="", stderr=""):
    return MagicMock(returncode=returncode, stdout=stdout, stderr=stderr)


class TestRun:
    def test_run_success(self, git):
        with patch("chinatxtbook.core.git_client.subprocess.run") as mock_run:
            mock_run.return_value = _mock_run(0, "output\n", "")
            ok, out, err = git.run(["status"])
            assert ok is True
            assert out == "output\n"

    def test_run_failure_returns_false(self, git):
        with patch("chinatxtbook.core.git_client.subprocess.run") as mock_run:
            mock_run.return_value = _mock_run(1, "", "error")
            ok, out, err = git.run(["bad-cmd"], retry=1)
            assert ok is False


class TestLsTree:
    def test_fail_closed_returns_none(self, git):
        with patch("chinatxtbook.core.git_client.subprocess.run") as mock_run:
            mock_run.return_value = _mock_run(1, "", "err")
            assert git.ls_tree("path/") is None

    def test_returns_stripped_list(self, git):
        with patch("chinatxtbook.core.git_client.subprocess.run") as mock_run:
            mock_run.return_value = _mock_run(0, "a\nb\n", "")
            assert git.ls_tree("path/") == ["a", "b"]

    def test_empty_returns_empty_list(self, git):
        with patch("chinatxtbook.core.git_client.subprocess.run") as mock_run:
            mock_run.return_value = _mock_run(0, "", "")
            assert git.ls_tree("path/") == []


class TestPathExists:
    def test_exists_true(self, git):
        with patch("chinatxtbook.core.git_client.subprocess.run") as mock_run:
            mock_run.return_value = _mock_run(0, "dir\n", "")
            assert git.path_exists_in_tree("dir") is True

    def test_not_exists_false(self, git):
        with patch("chinatxtbook.core.git_client.subprocess.run") as mock_run:
            mock_run.return_value = _mock_run(0, "", "")
            assert git.path_exists_in_tree("missing") is False


class TestDetectDefaultBranch:
    def test_from_state(self, git):
        state = {"default_branch": "main"}
        assert git.detect_default_branch(state) == "main"

    def test_detect_master_fallback(self, git):
        state = {}
        with patch("chinatxtbook.core.git_client.subprocess.run") as mock_run:
            # symbolic-ref fails, rev-parse origin/master succeeds
            mock_run.side_effect = [
                _mock_run(1, "", ""),
                _mock_run(0, "", ""),
            ]
            assert git.detect_default_branch(state) == "master"
            assert state["default_branch"] == "master"


class TestGetHeadCommit:
    def test_returns_sha(self, git):
        with patch("chinatxtbook.core.git_client.subprocess.run") as mock_run:
            mock_run.return_value = _mock_run(0, "abc123\n", "")
            assert git.get_head_commit() == "abc123"

    def test_returns_none_on_failure(self, git):
        with patch("chinatxtbook.core.git_client.subprocess.run") as mock_run:
            mock_run.return_value = _mock_run(1, "", "err")
            assert git.get_head_commit() is None
