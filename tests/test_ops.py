# tests/test_ops.py
import os
import sys

# allow dev-only block op for timeout testing
os.environ["ALLOW_BLOCK_OP"] = "1"
# uniform auth token for unit tests to match integration tests
os.environ["AUTH_TOKEN"] = "test_secret_token"

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from server import op_add, op_div, op_sub, op_mul, op_is_prime, op_is_even, op_in_range, op_regex_match, handle_request
import pytest
import json

def test_add():
    assert op_add([1,2,3]) == 6

def test_sub():
    assert op_sub([10,3]) == 7

def test_mul():
    assert op_mul([2,3,4]) == 24

def test_div_ok():
    assert op_div([10,2]) == 5

def test_div_by_zero():
    with pytest.raises(ZeroDivisionError):
        op_div([1,0])

def test_is_even_true():
    assert op_is_even([4]) is True

def test_is_even_false():
    assert op_is_even([5]) is False

def test_is_prime_true():
    assert op_is_prime([97]) is True

def test_is_prime_false():
    assert op_is_prime([100]) is False

def test_in_range_true():
    assert op_in_range([5, 1, 10]) is True

def test_in_range_false():
    assert op_in_range([0, 1, 10]) is False

def test_regex_match_simple():
    assert op_regex_match([r"^hello", "hello world"]) is True

def test_regex_match_flags():
    assert op_regex_match([r"hello", "HeLLo", "i"]) is True

def test_regex_invalid_pattern():
    with pytest.raises(ValueError):
        op_regex_match(["[unclosed", "text"])

def test_handle_request_invalid_schema():
    resp = handle_request("not-a-dict")
    assert resp["status"] == "error" and resp["error"]["code"] == "INVALID_SCHEMA"

def test_handle_request_too_many_args():
    long_args = list(range(1000))
    # Inject token to ensure it passes auth if schema validation order ever changes
    req = {"id":"t1","op":"add","args": long_args, "meta": {"auth_token": "test_secret_token"}}
    resp = handle_request(req)
    assert resp["status"] == "error" and resp["error"]["code"] in ("TOO_MANY_ARGS","INVALID_SCHEMA")

def test_handle_request_timeout():
    # use dev-only 'block' op which sleeps; set meta.timeout small to trigger TIMEOUT
    req = {
        "id": "t2",
        "op": "block",
        "args": [2],
        "meta": {
            "timeout": 0.1,
            "auth_token": "test_secret_token"  # Satisfy the auth gate to reach the timeout logic
        }
    }
    resp = handle_request(req)
    assert resp["status"] == "error" and resp["error"]["code"] == "TIMEOUT"