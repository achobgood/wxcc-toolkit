"""Client hardening behaviors (Phase D — design § 14b)."""
import httpx
import pytest
import typer

from wxcc_flow.client import FlowClient, _error_body, _ERROR_BODY_LIMIT


class TestResultGuard:
    """_result tolerates non-JSON success bodies (14b.1)."""

    def test_json_body_parses(self):
        assert FlowClient._result(httpx.Response(200, json={"a": 1})) == {"a": 1}

    def test_non_json_body_returns_text(self):
        assert FlowClient._result(httpx.Response(200, text="OK")) == "OK"

    def test_empty_body_returns_empty_dict(self):
        assert FlowClient._result(httpx.Response(200, content=b"")) == {}


class TestErrorBody:
    """_handle_error prints full bodies, explicit marker past the bound (14b.2)."""

    def test_under_limit_full_body(self):
        body = '{"error": "' + "x" * 500 + '"}'
        assert _error_body(httpx.Response(500, text=body)) == body

    def test_over_limit_explicit_marker(self):
        body = "y" * (_ERROR_BODY_LIMIT + 100)
        out = _error_body(httpx.Response(500, text=body))
        assert out.endswith(" …[truncated]")
        assert out.startswith("y" * _ERROR_BODY_LIMIT)

    def test_handle_error_500_prints_beyond_old_200_bound(self, capsys):
        body = '{"message": "' + "z" * 800 + '"}'
        resp = httpx.Response(500, text=body)
        with pytest.raises(typer.Exit):
            FlowClient._handle_error(None, resp)
        assert body in capsys.readouterr().err
