"""Tests for format utilities."""

from chinatxtbook.utils.format import redact_url, safe_error, fmt_size


class TestRedactUrl:
    def test_redact_username_password(self):
        assert redact_url("https://user:pass@github.com/repo.git") == \
            "https://***@github.com/repo.git"

    def test_redact_access_token(self):
        result = redact_url("https://github.com/repo?access_token=secret123")
        assert "access_token=***" in result
        assert "secret123" not in result

    def test_redact_private_token(self):
        result = redact_url("https://gitee.com/api?private_token=abc")
        assert "private_token=***" in result

    def test_redact_oauth_token(self):
        result = redact_url("https://example.com?oauth_token=xyz")
        assert "oauth_token=***" in result

    def test_redact_api_key(self):
        result = redact_url("https://api.example.com?api_key=deadbeef")
        assert "api_key=***" in result

    def test_redact_no_credentials(self):
        url = "https://github.com/TapXWorld/ChinaTextbook.git"
        assert redact_url(url) == url

    def test_redact_empty(self):
        assert redact_url("") == ""
        assert redact_url(None) is None

    def test_redact_multiple_params(self):
        result = redact_url("https://example.com?token=abc&other=keep&auth=xyz")
        assert "token=***" in result
        assert "auth=***" in result
        assert "other=keep" in result


class TestSafeError:
    def test_safe_error_redacts_and_truncates(self):
        err = "Error: https://user:pass@github.com/repo?token=secret123" + "x" * 500
        result = safe_error(err, limit=100)
        assert len(result) <= 100
        assert "pass" not in result.lower() or "secret" not in result.lower()

    def test_safe_error_int_input(self):
        result = safe_error(42)
        assert "42" in result


class TestFmtSize:
    def test_fmt_size_none(self):
        assert fmt_size(None) == "大小未知"

    def test_fmt_size_bytes(self):
        assert "MB" in fmt_size(1048576)

    def test_fmt_size_gb(self):
        result = fmt_size(5 * 1024 ** 3)
        assert "GB" in result
        assert "5.00" in result

    def test_fmt_size_zero(self):
        assert "MB" in fmt_size(0)
