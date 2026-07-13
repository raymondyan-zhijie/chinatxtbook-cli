"""Shared pytest fixtures for ChinaTextbook tests."""

import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Add src to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture
def temp_work_dir():
    """Create a temporary workspace directory."""
    tmp = tempfile.mkdtemp(prefix="chinatxtbook_test_")
    yield Path(tmp)
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def sample_state_v1_0():
    """Create a v1.0-format state dict for testing."""
    return {
        "version": "1.0",
        "started_at": datetime.now().isoformat(),
        "last_run": datetime.now().isoformat(),
        "repo_source": "https://github.com/TapXWorld/ChinaTextbook.git",
        "default_branch": "master",
        "clone_done": True,
        "selection_done": True,
        "selected_paths": ["小学/语文/", "小学/数学/"],
        "selection_fingerprint": None,
        "checkout_done": True,
        "target_dirs": ["小学/语文", "小学/数学"],
        "groups": {
            "小学/语文/test.pdf": {
                "status": "ok",
                "size": 1048576,
                "sha256": "a" * 64,
                "parts": [1, 2, 3],
                "at": datetime.now().isoformat(),
            },
            "小学/数学/test2.pdf": {
                "status": "ok",
                "size": 524288,
                "sha256": "b" * 64,
                "parts": [1, 2],
                "at": datetime.now().isoformat(),
            },
        },
        "last_failures": {},
        "size_cache": None,
    }


@pytest.fixture
def sample_manifest():
    """Create a sample git-tree manifest."""
    return {
        "小学/语文": {
            "test.pdf": {1: "test.pdf.1", 2: "test.pdf.2", 3: "test.pdf.3"},
            "single.pdf": {1: "single.pdf.1"},
        },
        "小学/数学": {
            "test2.pdf": {1: "test2.pdf.1", 2: "test2.pdf.2"},
        },
    }


@pytest.fixture
def mock_git_client():
    """Create a mock GitClient."""
    client = MagicMock()
    client.is_repo_valid.return_value = True
    client.get_head_commit.return_value = "abc123def456"
    client.ls_tree.return_value = [
        "小学/语文/test.pdf.1",
        "小学/语文/test.pdf.2",
        "小学/语文/test.pdf.3",
        "小学/语文/single.pdf.1",
        "小学/数学/test2.pdf.1",
        "小学/数学/test2.pdf.2",
    ]
    return client


@pytest.fixture
def create_split_files():
    """Factory fixture that creates test split PDF files."""
    def _create(base_dir: Path, rel_dir: str, parts: dict, sizes: list = None):
        """Create split files. parts: {idx: filename}, sizes: list of byte sizes."""
        d = base_dir / rel_dir
        d.mkdir(parents=True, exist_ok=True)
        for i, idx in enumerate(sorted(parts)):
            fname = parts[idx]
            content = b"\x00" * (sizes[i] if sizes else 1024)
            (d / fname).write_bytes(content)
        return d
    return _create
