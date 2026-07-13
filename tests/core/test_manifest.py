"""Tests for SplitManifest."""

from pathlib import Path

import pytest

from chinatxtbook.core.manifest import SplitManifest, SPLIT_RE


class TestSplitRe:
    def test_matches_split_files(self):
        m = SPLIT_RE.match("test.pdf.1")
        assert m is not None
        assert m.group(1) == "test.pdf"
        assert m.group(2) == "1"

    def test_matches_double_digit(self):
        m = SPLIT_RE.match("book.pdf.15")
        assert m is not None
        assert m.group(1) == "book.pdf"
        assert m.group(2) == "15"

    def test_case_insensitive(self):
        m = SPLIT_RE.match("BOOK.PDF.1")
        assert m is not None

    def test_does_not_match_plain_pdf(self):
        assert SPLIT_RE.match("test.pdf") is None

    def test_does_not_match_other_extension(self):
        assert SPLIT_RE.match("test.txt.1") is None


class TestSplitManifest:
    def test_build_manifest(self):
        output = (
            "小学/语文/test.pdf.1\n"
            "小学/语文/test.pdf.2\n"
            "小学/语文/test.pdf.3\n"
            "小学/语文/other.pdf.1\n"
            "小学/数学/book.pdf.1\n"
            "小学/数学/book.pdf.2\n"
        )
        manifest = SplitManifest.build_expected_manifest(output, ["小学/"])

        assert manifest is not None
        assert "小学/语文" in manifest
        assert "test.pdf" in manifest["小学/语文"]
        assert manifest["小学/语文"]["test.pdf"] == {
            1: "test.pdf.1", 2: "test.pdf.2", 3: "test.pdf.3"
        }
        assert "other.pdf" in manifest["小学/语文"]
        assert "小学/数学" in manifest

    def test_build_manifest_empty(self):
        # Empty string = no split files, returns {} (not None)
        # None is reserved for actual git failures
        manifest = SplitManifest.build_expected_manifest("", [])
        assert manifest == {}

    def test_build_manifest_none_input(self):
        # None = git failure, returns None (fail-closed)
        manifest = SplitManifest.build_expected_manifest(None, [])
        assert manifest is None

    def test_missing_parts(self):
        assert SplitManifest.missing_parts([1, 3, 5]) == [2, 4]
        assert SplitManifest.missing_parts([1, 2, 3]) == []
        assert SplitManifest.missing_parts([]) == []

    def test_find_split_groups(self, tmp_path):
        d = tmp_path / "testdir"
        d.mkdir()
        (d / "book.pdf.1").write_text("")
        (d / "book.pdf.2").write_text("")
        (d / "book.pdf").write_text("")  # Non-split, should be ignored
        (d / "other.pdf.1").write_text("")
        (d / "other.pdf.3").write_text("")

        groups = SplitManifest.find_split_groups(d)

        assert "book.pdf" in groups
        assert groups["book.pdf"] == {1: ["book.pdf.1"], 2: ["book.pdf.2"]}
        assert "other.pdf" in groups

    def test_clean_stale_tmp(self, tmp_path):
        d = tmp_path / "testdir"
        d.mkdir()
        (d / "myfile.pdf.tmp").write_text("")
        (d / "other.tmp").write_text("")  # Not .pdf.tmp, should survive
        (d / "regular.pdf").write_text("")

        SplitManifest.clean_stale_tmp(d)

        assert not (d / "myfile.pdf.tmp").exists()
        assert (d / "other.tmp").exists()  # Non-pdf .tmp preserved
        assert (d / "regular.pdf").exists()
