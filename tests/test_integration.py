# tests/test_integration.py
import threading
import time
import socket
import ssl
import json
import pytest
import os
import uuid
import sys

os.environ["AUTH_TOKEN"] = "test_secret_token"
os.environ["ALLOW_BLOCK_OP"] = "1"

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from server import GracefulServer

TEST_HOST = "127.0.0.1"
TEST_PORT = 5001  

@pytest.fixture(scope="module")
def live_server():
    server = GracefulServer(host=TEST_HOST, port=TEST_PORT)
    server_thread = threading.Thread(target=server.start, daemon=True)
    server_thread.start()
    time.sleep(0.5) 
    yield server
    server.shutdown()
    server_thread.join(timeout=2.0)

def send_test_request(req_obj):
    data = (json.dumps(req_obj) + "\n").encode('utf-8')
    context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile="cert.pem")
    context.check_hostname = False
    
    with socket.create_connection((TEST_HOST, TEST_PORT), timeout=2.0) as sock:
        with context.wrap_socket(sock, server_hostname="localhost") as ssock:
            ssock.sendall(data)
            buf = bytearray()
            while True:
                chunk = ssock.recv(1024)
                if not chunk:
                    break
                buf.extend(chunk)
                if b'\n' in buf:
                    line, _, _ = bytes(buf).partition(b'\n')
                    return json.loads(line.decode('utf-8'))
    return None

def test_successful_request_with_auth(live_server):
    req = {
        "id": str(uuid.uuid4()),
        "op": "power",
        "args": [2, 8],
        "meta": {"auth_token": "test_secret_token"}
    }
    resp = send_test_request(req)
    assert resp is not None
    assert resp["status"] == "ok"
    assert resp["result"] == 256

def test_unauthorized_request(live_server):
    req = {
        "id": str(uuid.uuid4()),
        "op": "add",
        "args": [10, 20],
        "meta": {"auth_token": "wrong_password"}
    }
    resp = send_test_request(req)
    assert resp is not None
    assert resp["status"] == "error"
    assert resp["error"]["code"] == "UNAUTHORIZED"

# def test_rate_limiting(live_server):
#     req = {
#         "id": str(uuid.uuid4()),
#         "op": "add",
#         "args": [1, 1],
#         "meta": {"auth_token": "test_secret_token"}
#     }
#     rate_limited = False
#     for _ in range(55):
#         resp = send_test_request(req)
#         if resp and resp.get("status") == "error" and resp["error"].get("code") == "RATE_LIMIT_EXCEEDED":
#             rate_limited = True
#             break
#     assert rate_limited is True


def test_rate_limiting(live_server):
    import server
    # Widen the sliding window to 10 seconds specifically for this test 
    # to account for the heavy overhead of 55 sequential TLS handshakes.
    original_window = server.RATE_LIMIT_WINDOW_SEC
    server.RATE_LIMIT_WINDOW_SEC = 10.0  
    
    req = {
        "id": str(uuid.uuid4()),
        "op": "add",
        "args": [1, 1],
        "meta": {"auth_token": "test_secret_token"}
    }
    
    rate_limited = False
    for _ in range(55):
        resp = send_test_request(req)
        if resp and resp.get("status") == "error" and resp["error"].get("code") == "RATE_LIMIT_EXCEEDED":
            rate_limited = True
            break
            
    # Restore the original window size so it doesn't affect other components
    server.RATE_LIMIT_WINDOW_SEC = original_window
    
    assert rate_limited is True

