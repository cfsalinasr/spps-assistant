"""Tests for the API response envelope helpers."""

from spps_assistant.api.responses import ok, err


def test_ok_wraps_data_with_ok_true():
    assert ok({"a": 1}) == {"ok": True, "data": {"a": 1}}


def test_ok_wraps_none_data():
    assert ok(None) == {"ok": True, "data": None}


def test_err_wraps_code_and_message():
    assert err("bad_input", "nope") == {
        "ok": False,
        "error": {"code": "bad_input", "message": "nope"},
    }
