"""Tests for PathPolicy - path safety validation (F-17/N-2).

Validates: normal resolution, rejection of traversal/absolute/nul/empty/symlink.
Mirrors the dynamic checks from audit round 4 section 5.
"""

import os

import pytest

from chinatxtbook.utils.paths import PathPolicy


@pytest.fixture
def root(tmp_path):
    """Clean root directory with a subdir and file."""
    (tmp_path / "subdir").mkdir()
    (tmp_path / "subdir" / "file.pdf").write_bytes(b"x")
    return tmp_path


class TestResolveWithin:
    def test_normal_relative_path(self, root):
        result = PathPolicy.resolve_within(root, "subdir/file.pdf")
        assert result is not None
        assert result.is_absolute()

    def test_nested_relative_path(self, root):
        result = PathPolicy.resolve_within(root, "a/b/c/file.pdf")
        assert result is not None

    def test_empty_candidate(self, root):
        assert PathPolicy.resolve_within(root, "") is None

    def test_nul_byte(self, root):
        assert PathPolicy.resolve_within(root, "file\0.pdf") is None

    def test_traversal_parent(self, root):
        assert PathPolicy.resolve_within(root, "../secret") is None

    def test_traversal_nested(self, root):
        assert PathPolicy.resolve_within(root, "subdir/../../secret") is None

    def test_absolute_unix(self, root):
        assert PathPolicy.resolve_within(root, "/etc/passwd") is None

    def test_absolute_windows_backslash(self, root):
        assert PathPolicy.resolve_within(root, "\\windows\\system32") is None

    def test_path_escapes_root(self, root):
        assert PathPolicy.resolve_within(root, "../../../escape") is None


class TestSafeWritePath:
    def test_creates_parent_dirs(self, tmp_path):
        result = PathPolicy.safe_write_path(tmp_path, "a/b/c/file.pdf")
        assert result is not None
        assert result.parent.exists()

    def test_rejects_traversal(self, tmp_path):
        assert PathPolicy.safe_write_path(tmp_path, "../escape.pdf") is None

    def test_rejects_absolute(self, tmp_path):
        assert PathPolicy.safe_write_path(tmp_path, "/etc/passwd") is None


class TestSymlinkRejection:
    def test_symlink_pointing_outside_rejected(self, root, tmp_path):
        target = tmp_path.parent / "outside_target"
        target.write_text("secret")
        link = root / "link"
        try:
            os.symlink(str(target), str(link))
        except (OSError, NotImplementedError):
            pytest.skip("symlink creation not supported/privileged on this platform")
        assert PathPolicy.resolve_within(root, "link") is None
