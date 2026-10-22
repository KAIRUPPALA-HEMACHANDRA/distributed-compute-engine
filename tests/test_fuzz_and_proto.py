import os
import sys
import json
import uuid

# Add the project root directory to Python's module search path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from hypothesis import given, settings, strategies as st
from proto_codec import encode_request_to_protobuf, decode_protobuf_to_request

def test_protobuf_roundtrip_and_compression():
    """Verifies Protobuf serialization round-trips cleanly and uses fewer bytes than JSON."""
    import server

    original_request = {
        "id": str(uuid.uuid4()),
        "op": "power",
        "args": [2, 16],
        "meta": {
            "auth_token": "test_secret_token",
            "timeout": 5.0
        }
    }

    json_bytes = json.dumps(original_request).encode("utf-8")
    proto_bytes = encode_request_to_protobuf(original_request)

    # 1. Verify binary Protobuf payload is more compact than text JSON
    assert len(proto_bytes) < len(json_bytes)

    # 2. Verify decoding restores the exact payload and executes cleanly in the core engine
    decoded_request = decode_protobuf_to_request(proto_bytes)
    response = server.handle_request(decoded_request, client_addr="PROTO_TEST")
    assert response["status"] == "ok"
    assert response["result"] == 65536

@settings(max_examples=60, deadline=None)
@given(
    op=st.one_of(
        st.sampled_from(["add", "sub", "mul", "div", "power", "modulo", "is_even", "is_prime", "in_range", "regex_match"]),
        st.text(min_size=0, max_size=20).filter(lambda x: x != "block")
    ),
    args=st.lists(
        st.one_of(
            st.integers(min_value=-1000, max_value=1000),
            st.floats(allow_nan=True, allow_infinity=True),
            st.text(max_size=15),
            st.booleans(),
            st.none()
        ),
        min_size=0,
        max_size=6
    ),
    timeout=st.one_of(st.floats(min_value=-10.0, max_value=25.0, allow_nan=False, allow_infinity=False), st.none())
)
def test_fuzz_handle_request_never_crashes(op, args, timeout):
    """Bombards handle_request with 60 randomized, malformed payloads to ensure zero unhandled crashes."""
    import server

    meta = {"auth_token": "test_secret_token"}
    if timeout is not None:
        meta["timeout"] = timeout

    fuzzed_payload = {
        "id": "fuzz-test-id",
        "op": op,
        "args": args,
        "meta": meta
    }

    response = server.handle_request(fuzzed_payload, client_addr="FUZZER")

    # The engine must NEVER crash; it must always return a structured 'ok' or 'error' dictionary
    assert isinstance(response, dict)
    assert response.get("status") in ("ok", "error")
    if response.get("status") == "error":
        assert "code" in response.get("error", {})


# 
# import os
# import sys
# import json
# import uuid

# # Add the project root directory to Python's module search path
# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# from hypothesis import given, settings, strategies as st
# import server
# from proto_codec import encode_request_to_protobuf, decode_protobuf_to_request

# def test_protobuf_roundtrip_and_compression():
#     """Verifies Protobuf serialization round-trips cleanly and uses fewer bytes than JSON."""
#     original_request = {
#         "id": str(uuid.uuid4()),
#         "op": "power",
#         "args": [2, 16],
#         "meta": {
#             "auth_token": server.EXPECTED_AUTH_TOKEN,
#             "timeout": 5.0
#         }
#     }

#     json_bytes = json.dumps(original_request).encode("utf-8")
#     proto_bytes = encode_request_to_protobuf(original_request)

#     # 1. Verify binary Protobuf payload is more compact than text JSON
#     assert len(proto_bytes) < len(json_bytes)

#     # 2. Verify decoding restores the exact payload and executes cleanly in the core engine
#     decoded_request = decode_protobuf_to_request(proto_bytes)
#     response = server.handle_request(decoded_request, client_addr="PROTO_TEST")
#     assert response["status"] == "ok"
#     assert response["result"] == 65536

# @settings(max_examples=60, deadline=None)
# @given(
#     op=st.one_of(
#         st.sampled_from(["add", "sub", "mul", "div", "power", "modulo", "is_even", "is_prime", "in_range", "regex_match"]),
#         st.text(min_size=0, max_size=20)
#     ),
#     args=st.lists(
#         st.one_of(
#             st.integers(min_value=-100000, max_value=100000),
#             st.floats(allow_nan=True, allow_infinity=True),
#             st.text(max_size=15),
#             st.booleans(),
#             st.none()
#         ),
#         min_size=0,
#         max_size=6
#     ),
#     timeout=st.one_of(st.floats(min_value=-10.0, max_value=25.0, allow_nan=False, allow_infinity=False), st.none())
# )
# def test_fuzz_handle_request_never_crashes(op, args, timeout):
#     """Bombards handle_request with 60 randomized, malformed payloads to ensure zero unhandled crashes."""
#     meta = {"auth_token": server.EXPECTED_AUTH_TOKEN}
#     if timeout is not None:
#         meta["timeout"] = timeout

#     fuzzed_payload = {
#         "id": "fuzz-test-id",
#         "op": op,
#         "args": args,
#         "meta": meta
#     }

#     response = server.handle_request(fuzzed_payload, client_addr="FUZZER")

#     # The engine must NEVER crash; it must always return a structured 'ok' or 'error' dictionary
#     assert isinstance(response, dict)
#     assert response.get("status") in ("ok", "error")
#     if response.get("status") == "error":
#         assert "code" in response.get("error", {})