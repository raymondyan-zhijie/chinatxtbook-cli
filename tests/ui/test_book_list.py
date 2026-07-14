"""Tests for book_list natural sort (Chinese numeral parsing)."""

from chinatxtbook.ui.widgets.book_list import _cn_num_to_int, _natural_key


class TestCnNumToInt:
    def test_single_digit(self):
        assert _cn_num_to_int("一") == 1
        assert _cn_num_to_int("九") == 9

    def test_ten(self):
        assert _cn_num_to_int("十") == 10

    def test_ten_x(self):
        assert _cn_num_to_int("十一") == 11
        assert _cn_num_to_int("十九") == 19

    def test_x_ten(self):
        assert _cn_num_to_int("二十") == 20
        assert _cn_num_to_int("九十") == 90

    def test_x_ten_y(self):
        assert _cn_num_to_int("二十一") == 21
        assert _cn_num_to_int("九十九") == 99

    def test_non_numeral(self):
        assert _cn_num_to_int("年级") is None
        assert _cn_num_to_int("") is None
        assert _cn_num_to_int("一百") is None  # 百 not supported


class TestNaturalKey:
    def test_chinese_numeral_sort(self):
        names = ["十一年级", "二年级", "一年级", "二十一年级"]
        assert sorted(names, key=_natural_key) == [
            "一年级",
            "二年级",
            "十一年级",
            "二十一年级",
        ]

    def test_arabic_sort(self):
        names = ["第10册", "第2册", "第1册"]
        assert sorted(names, key=_natural_key) == ["第1册", "第2册", "第10册"]

    def test_mixed_arabic_and_chinese(self):
        names = ["2年级", "一", "1年级"]
        result = sorted(names, key=_natural_key)
        # "1年级" and "一" sort as 1; "2年级" as 2
        assert result[-1] == "2年级"
