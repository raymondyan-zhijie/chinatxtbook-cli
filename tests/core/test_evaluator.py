"""Tests for GroupEvaluator — the safety-critical decision engine.

Covers all branches from v1.0 evaluate_group().
"""


import pytest

from chinatxtbook.core.evaluator import GroupEvaluator


class TestGroupEvaluator:
    """Test all decision paths of the group evaluation engine."""

    @pytest.fixture
    def evaluator(self, tmp_path):
        return GroupEvaluator(work_dir=tmp_path)

    @pytest.fixture
    def state(self, sample_state_v1_0):
        return sample_state_v1_0

    # ── Normal cases ───────────────────────────────────────

    def test_all_parts_present_merge(self, evaluator, state):
        """All split parts present and no record → merge."""
        present = {1: ["test.pdf.1"], 2: ["test.pdf.2"], 3: ["test.pdf.3"]}
        expected = {1: "test.pdf.1", 2: "test.pdf.2", 3: "test.pdf.3"}

        result = evaluator.evaluate(state, "dir", "test.pdf", present, expected)

        assert result["action"] == "merge"
        assert result["parts_map"] == expected
        assert result["restore"] == []
        assert result["detail"] is None

    def test_all_parts_skip_verify_fast_skip(self, evaluator, state, tmp_path):
        """--skip-verify with valid record and matching size → skip."""
        # Create output file
        out = tmp_path / "dir" / "test.pdf"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"\x00" * 2048)

        # Add record
        state.setdefault("groups", {})["dir/test.pdf"] = {
            "status": "ok", "size": 2048, "sha256": "x" * 64,
            "parts": [1, 2], "at": "2026-01-01T00:00:00",
        }

        present = {1: ["test.pdf.1"], 2: ["test.pdf.2"]}
        expected = {1: "test.pdf.1", 2: "test.pdf.2"}

        result = evaluator.evaluate(state, "dir", "test.pdf", present, expected,
                                     verify=False)  # skip-verify

        assert result["action"] == "skip"
        assert "快速跳过" in result["detail"]

    # ── Error: Duplicate parts ─────────────────────────────

    def test_duplicate_parts_error(self, evaluator, state):
        """Both .1 and .01 present → error."""
        present = {1: ["test.pdf.1", "test.pdf.01"]}
        expected = {1: "test.pdf.1"}

        result = evaluator.evaluate(state, "dir", "test.pdf", present, expected)

        assert result["action"] == "error"
        assert "重复" in result["detail"]

    # ── Error: Single-part rejection ───────────────────────

    def test_single_part_rejected(self, evaluator, state):
        """Only .pdf.1 → cannot prove completeness → error."""
        present = {1: ["test.pdf.1"]}
        expected = {1: "test.pdf.1"}

        result = evaluator.evaluate(state, "dir", "test.pdf", present, expected)

        assert result["action"] == "error"
        assert "单卷" in result["detail"]

    # ── Error: Non-manifest (outside git tree) ─────────────

    def test_outside_manifest_rejected(self, evaluator, state):
        """Group not in git tree → error."""
        present = {1: ["test.pdf.1"], 2: ["test.pdf.2"]}
        expected = None  # Not in manifest

        result = evaluator.evaluate(state, "dir", "test.pdf", present, expected)

        assert result["action"] == "error"
        assert "Git 树清单" in result["detail"]

    # ── Error: Upstream duplicate ──────────────────────────

    def test_upstream_duplicate_error(self, evaluator, state):
        """Manifest has duplicate index → error."""
        present = {1: ["test.pdf.1"]}
        expected = {1: ["test.pdf.1", "test.pdf.01"]}  # list = duplicate

        result = evaluator.evaluate(state, "dir", "test.pdf", present, expected)

        assert result["action"] == "error"
        assert "重复" in result["detail"]

    # ── Error: Manifest discontinuity ──────────────────────

    def test_manifest_discontinuity_error(self, evaluator, state):
        """Missing index in manifest → error."""
        present = {1: ["test.pdf.1"], 3: ["test.pdf.3"]}
        expected = {1: "test.pdf.1", 3: "test.pdf.3"}

        result = evaluator.evaluate(state, "dir", "test.pdf", present, expected)

        assert result["action"] == "error"
        assert "不连续" in result["detail"]

    # ── Stale record handling ──────────────────────────────

    def test_stale_with_deleted_volume_rejected(self, evaluator, state, tmp_path):
        """Stale record: historical parts=[1,2,3] but manifest only [1,2] → error."""
        out = tmp_path / "dir" / "test.pdf"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"\x00" * 3072)

        state.setdefault("groups", {})["dir/test.pdf"] = {
            "status": "ok", "size": 3072, "sha256": "y" * 64,
            "parts": [1, 2, 3], "stale": True, "at": "2026-01-01T00:00:00",
        }

        present = {1: ["test.pdf.1"], 2: ["test.pdf.2"]}
        expected = {1: "test.pdf.1", 2: "test.pdf.2"}

        result = evaluator.evaluate(state, "dir", "test.pdf", present, expected)

        assert result["action"] == "error"
        assert "上游删除" in result["detail"] or "删除了原有分卷" in result["detail"]

    def test_stale_no_skip_evidence(self, evaluator, state, tmp_path):
        """Stale record must never be used as skip evidence."""
        out = tmp_path / "dir" / "test.pdf"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"\x00" * 2048)

        state.setdefault("groups", {})["dir/test.pdf"] = {
            "status": "ok", "size": 2048, "sha256": "z" * 64,
            "parts": [1, 2], "stale": True, "at": "2026-01-01T00:00:00",
        }

        present = {1: ["test.pdf.1"], 2: ["test.pdf.2"]}
        expected = {1: "test.pdf.1", 2: "test.pdf.2"}

        # Even with --skip-verify, stale record should NOT skip
        result = evaluator.evaluate(state, "dir", "test.pdf", present, expected,
                                     verify=False)

        # Should merge (not skip), because stale records cannot be used
        # as skip evidence, and all parts are present
        assert result["action"] == "merge"

    def test_stale_missing_old_parts_field(self, evaluator, state, tmp_path):
        """Old record (v4.2/v4.3) without parts field → error with existing output."""
        out = tmp_path / "dir" / "test.pdf"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"\x00" * 2048)

        state.setdefault("groups", {})["dir/test.pdf"] = {
            "status": "ok", "size": 2048, "sha256": "w" * 64,
            "stale": True, "at": "2026-01-01T00:00:00",
            # NOTE: no "parts" field (old v4.2/v4.3 record)
        }

        present = {1: ["test.pdf.1"], 2: ["test.pdf.2"]}
        expected = {1: "test.pdf.1", 2: "test.pdf.2"}

        result = evaluator.evaluate(state, "dir", "test.pdf", present, expected)

        assert result["action"] == "error"
        assert "缺少分卷集合信息" in result["detail"]

    # ── Missing local parts (--clean scenario) ─────────────

    def test_missing_parts_hash_verified_skip(self, evaluator, state, tmp_path):
        """Missing local parts, but hash matches record → skip."""
        out = tmp_path / "dir" / "test.pdf"
        out.parent.mkdir(parents=True, exist_ok=True)
        # Write known content that matches the expected hash
        out.write_bytes(b"\x00" * 2048)

        # Pre-compute what the hash would be with this content
        import hashlib
        actual_hash = hashlib.sha256(b"\x00" * 2048).hexdigest()

        state.setdefault("groups", {})["dir/test.pdf"] = {
            "status": "ok", "size": 2048, "sha256": actual_hash,
            "parts": [1, 2], "at": "2026-01-01T00:00:00",
        }

        present = {}  # All parts cleaned
        expected = {1: "test.pdf.1", 2: "test.pdf.2"}

        result = evaluator.evaluate(state, "dir", "test.pdf", present, expected)

        assert result["action"] == "skip"
        assert "分卷已清理" in result["detail"]

    def test_missing_parts_no_record_restore(self, evaluator, state):
        """Missing local parts, no record → merge with restore."""
        present = {1: ["test.pdf.1"]}  # Only part 1 present
        expected = {1: "test.pdf.1", 2: "test.pdf.2"}

        result = evaluator.evaluate(state, "dir", "test.pdf", present, expected)

        assert result["action"] == "merge"
        assert len(result["restore"]) > 0
