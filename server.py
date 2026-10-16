#!/usr/bin/env python3
"""
server.py (multithreaded) — with structured logging & rotation

Features:
- arithmetic & validation ops
- per-request timeout via meta.timeout
- multithreaded worker per connection
- sliding-window rate limiting per IP address
- token-based authentication
- TLS Transport Encryption
"""

import socket
import ssl
import json
import uuid
import traceback
import threading
import signal
import sys
import re
import os
import time
import logging
import collections
from math import isfinite, sqrt
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from logging.handlers import RotatingFileHandler
from datetime import datetime, timezone

# ---------- configuration ----------
HOST = "127.0.0.1"
PORT = 5000
RECV_CHUNK = 1024
CONN_TIMEOUT = 30.0
REQUEST_TIMEOUT_DEFAULT = 5.0
REQUEST_TIMEOUT_MAX = 10.0
MAX_ARG_COUNT = 64
MAX_NUMERIC_ABS = 1e12

# TLS Configuration
CERT_FILE = "cert.pem"
KEY_FILE = "key.pem"

# ---------- Security & Limits ----------
AUTH_TOKEN_ENV = os.environ.get("AUTH_TOKEN")
RATE_LIMIT_MAX_REQUESTS = 50
RATE_LIMIT_WINDOW_SEC = 1.0

_client_request_times = collections.defaultdict(list)
_rate_lock = threading.Lock()

def is_rate_limited(client_ip):
    now = time.time()
    with _rate_lock:
        valid_times = [t for t in _client_request_times[client_ip] if now - t < RATE_LIMIT_WINDOW_SEC]
        _client_request_times[client_ip] = valid_times
        if len(valid_times) >= RATE_LIMIT_MAX_REQUESTS:
            return True
        _client_request_times[client_ip].append(now)
        return False

LOG_FILE = "server.log"
LOG_MAX_BYTES = 5 * 1024 * 1024
LOG_BACKUP_COUNT = 5

# ---------- logging setup ----------
logger = logging.getLogger("pcs_server")
logger.setLevel(logging.INFO)
ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.INFO)
logger.addHandler(ch)
fh = RotatingFileHandler(LOG_FILE, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT)
fh.setLevel(logging.INFO)
logger.addHandler(fh)

def log_event(level, event, **data):
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "event": event,
    }
    entry.update(data)
    if "meta" in entry and isinstance(entry["meta"], dict):
        if "auth_token" in entry["meta"]:
            entry["meta"] = dict(entry["meta"])
            entry["meta"]["auth_token"] = "***REDACTED***"
    line = json.dumps(entry, default=str, separators=(",", ":"))
    if level == "ERROR":
        logger.error(line)
    elif level == "WARN":
        logger.warning(line)
    else:
        logger.info(line)

# ---------- utilities & validation ----------
def parse_numbers(args):
    parsed = []
    for a in args:
        if isinstance(a, (int, float)):
            v = a
        else:
            s = str(a).strip()
            try:
                v = int(s)
            except Exception:
                try:
                    v = float(s)
                except Exception:
                    raise ValueError(f"argument not numeric: {a!r}")
        try:
            if abs(float(v)) > MAX_NUMERIC_ABS:
                raise ValueError(f"numeric argument {v!r} exceeds allowed magnitude ({MAX_NUMERIC_ABS})")
        except TypeError:
            raise ValueError(f"argument not numeric: {a!r}")
        parsed.append(v)
    return parsed

def validate_request_schema(obj):
    if not isinstance(obj, dict):
        return False, ("INVALID_SCHEMA", "request must be a JSON object")
    if "op" not in obj or not isinstance(obj["op"], str):
        return False, ("INVALID_SCHEMA", "missing or invalid 'op' field (must be string)")
    if "args" in obj and not isinstance(obj["args"], list):
        return False, ("INVALID_SCHEMA", "'args' must be a list if present")
    if "meta" in obj and not isinstance(obj["meta"], dict):
        return False, ("INVALID_SCHEMA", "'meta' must be an object if present")
    if "args" in obj and len(obj["args"]) > MAX_ARG_COUNT:
        return False, ("TOO_MANY_ARGS", f"too many args (max {MAX_ARG_COUNT})")
    return True, None

# ---------- arithmetic ops ----------
def op_add(args):
    nums = parse_numbers(args)
    if len(nums) < 2: raise ValueError("add requires at least 2 arguments")
    return sum(nums)

def op_sub(args):
    nums = parse_numbers(args)
    if len(nums) < 2: raise ValueError("sub requires at least 2 arguments")
    res = float(nums[0])
    for x in nums[1:]: res -= float(x)
    return res

def op_mul(args):
    nums = parse_numbers(args)
    if len(nums) < 2: raise ValueError("mul requires at least 2 arguments")
    res = 1.0
    for x in nums: res *= float(x)
    return res

def op_div(args):
    if len(args) != 2: raise ValueError("div requires exactly 2 arguments")
    a, b = parse_numbers(args)
    if b == 0: raise ZeroDivisionError("division by zero")
    return a / b

def op_power(args):
    if len(args) != 2: raise ValueError("power requires exactly 2 arguments (base, exponent)")
    base, exp = parse_numbers(args)
    if abs(exp) > 10000: raise ValueError("exponent exceeds maximum allowed limit of 10000")
    if base < 0 and not exp.is_integer(): raise ValueError("fractional exponent with negative base results in complex number")
    return base ** exp

def op_modulo(args):
    if len(args) != 2: raise ValueError("modulo requires exactly 2 arguments")
    a, b = parse_numbers(args)
    if b == 0: raise ZeroDivisionError("modulo by zero is not allowed")
    return a % b

# ---------- validation ops ----------
def op_is_even(args):
    if len(args) != 1: raise ValueError("is_even requires exactly 1 argument")
    nums = parse_numbers(args)
    return (int(nums[0]) % 2) == 0

def is_probable_prime(n):
    n = int(n)
    if n <= 1: return False
    if n <= 3: return True
    if n % 2 == 0: return False
    r = int(sqrt(n))
    i = 3
    while i <= r:
        if n % i == 0: return False
        i += 2
    return True

def op_is_prime(args):
    if len(args) != 1: raise ValueError("is_prime requires exactly 1 argument")
    nums = parse_numbers(args)
    return is_probable_prime(nums[0])

def op_in_range(args):
    if len(args) != 3: raise ValueError("in_range requires 3 args: value, low, high")
    val, low, high = parse_numbers(args)
    return low <= val <= high

def op_regex_match(args):
    if len(args) < 2 or len(args) > 3: raise ValueError("regex_match requires 2 or 3 args: pattern, text, [flags]")
    pattern = str(args[0])
    text = str(args[1])
    flags = str(args[2]) if len(args) == 3 else ""
    re_flags = 0
    if "i" in flags: re_flags |= re.IGNORECASE
    if "m" in flags: re_flags |= re.MULTILINE
    if "s" in flags: re_flags |= re.DOTALL
    try:
        compiled = re.compile(pattern, flags=re_flags)
    except re.error as e:
        raise ValueError(f"invalid regex pattern: {e}")
    return bool(compiled.search(text))

def op_block(args):
    if len(args) != 1: raise ValueError("block requires exactly 1 arg (seconds)")
    secs = float(args[0])
    time.sleep(secs)
    return {"slept": secs}

# ---------- registry ----------
OPERATIONS = {
    "add": op_add, "sub": op_sub, "mul": op_mul, "div": op_div,
    "power": op_power, "modulo": op_modulo, "is_even": op_is_even,
    "is_prime": op_is_prime, "in_range": op_in_range, "regex_match": op_regex_match,
}
if os.environ.get("ALLOW_BLOCK_OP") == "1":
    OPERATIONS["block"] = op_block

# ---------- executor & request handling ----------
_executor = ThreadPoolExecutor(max_workers=16)

def _execute_op_with_timeout(op_func, args, timeout):
    fut = _executor.submit(op_func, args)
    return fut.result(timeout=timeout)

def make_error(req_id, code, message, hint=None, trace=None):
    err = {"code": code, "message": message}
    if hint: err["hint"] = hint
    if trace: err["trace"] = trace
    return {"id": req_id, "status": "error", "error": err}

def handle_request(obj, client_addr=None):
    if not isinstance(obj, dict):
        req_id = str(uuid.uuid4())
        log_event("WARN", "bad_request_obj", client=str(client_addr), detail=str(obj))
        return make_error(req_id, "INVALID_SCHEMA", "request must be a JSON object")

    req_id = obj.get("id") or str(uuid.uuid4())
    ok, info = validate_request_schema(obj)
    if not ok:
        log_event("WARN", "invalid_schema", req_id=req_id, client=str(client_addr))
        return make_error(req_id, info[0], info[1])

    meta = obj.get("meta", {}) or {}
    client_ip = str(client_addr).split(":")[0] if client_addr else "unknown"

    if is_rate_limited(client_ip):
        log_event("WARN", "rate_limit_exceeded", req_id=req_id, client=str(client_addr))
        return make_error(req_id, "RATE_LIMIT_EXCEEDED", "Too many requests. Please slow down.")

    if AUTH_TOKEN_ENV is not None:
        client_token = meta.get("auth_token")
        if not client_token or client_token != AUTH_TOKEN_ENV:
            log_event("WARN", "unauthorized", req_id=req_id, client=str(client_addr))
            return make_error(req_id, "UNAUTHORIZED", "Missing or invalid authentication token")

    op_name = obj.get("op")
    args = obj.get("args", [])

    log_event("INFO", "request_received", req_id=req_id, client=str(client_addr), op=op_name, args=args, meta=meta)

    if op_name not in OPERATIONS:
        log_event("WARN", "unknown_op", req_id=req_id, client=str(client_addr), op=op_name)
        return make_error(req_id, "UNKNOWN_OP", f"unknown op '{op_name}'")

    op_func = OPERATIONS[op_name]
    try:
        timeout = float(meta.get("timeout", REQUEST_TIMEOUT_DEFAULT))
    except Exception:
        return make_error(req_id, "INVALID_SCHEMA", "meta.timeout must be numeric")
    if timeout <= 0 or timeout > REQUEST_TIMEOUT_MAX:
        return make_error(req_id, "INVALID_SCHEMA", f"meta.timeout must be >0 and <= {REQUEST_TIMEOUT_MAX}")

    try:
        result = _execute_op_with_timeout(op_func, args, timeout=timeout)
    except TimeoutError:
        return make_error(req_id, "TIMEOUT", f"operation timed out after {timeout} seconds")
    except ZeroDivisionError as e:
        return make_error(req_id, "DIV_BY_ZERO", str(e), hint="ensure divisor is non-zero")
    except ValueError as e:
        return make_error(req_id, "BAD_ARG", str(e))
    except Exception as e:
        trace = traceback.format_exc()
        return make_error(req_id, "EXEC_ERR", str(e), trace=trace)

    if isinstance(result, float) and not isfinite(result):
        return make_error(req_id, "NONFINITE", "result not finite")

    log_event("INFO", "response_sent", req_id=req_id, client=str(client_addr), op=op_name, status="ok", result=result)
    return {"id": req_id, "status": "ok", "result": result}

def send_json(conn, obj):
    payload = (json.dumps(obj, separators=(",", ":")) + "\n").encode("utf-8")
    conn.sendall(payload)

def recv_line(conn):
    buf = bytearray()
    while True:
        try:
            chunk = conn.recv(RECV_CHUNK)
        except (socket.timeout, ssl.SSLError):
            return None
        except Exception:
            return None
        if not chunk:
            if not buf: return None
            break
        buf.extend(chunk)
        if b"\n" in buf:
            line, _, _rest = bytes(buf).partition(b"\n")
            return line.decode("utf-8")
    return bytes(buf).decode("utf-8")

# ---------- client worker & server ----------
def client_worker(conn, addr, tls_context):
    client_str = f"{addr[0]}:{addr[1]}"
    try:
        # Perform the TLS handshake inside the thread to prevent blocking the server accept loop
        secure_conn = tls_context.wrap_socket(conn, server_side=True)
    except ssl.SSLError as e:
        log_event("WARN", "ssl_handshake_failed", client=client_str, error=str(e))
        conn.close()
        return

    log_event("INFO", "client_connect", client=client_str)
    secure_conn.settimeout(CONN_TIMEOUT)
    with secure_conn:
        while True:
            line = recv_line(secure_conn)
            if line is None:
                log_event("INFO", "client_disconnect", client=client_str)
                break
            try:
                req = json.loads(line)
            except Exception as e:
                resp = make_error(str(uuid.uuid4()), "JSON_PARSE_ERROR", f"invalid JSON: {e}")
                try:
                    send_json(secure_conn, resp)
                except Exception:
                    break
                continue
            resp = handle_request(req, client_addr=client_str)
            try:
                send_json(secure_conn, resp)
            except Exception:
                break
    log_event("INFO", "worker_exit", client=client_str)

class GracefulServer:
    def __init__(self, host=HOST, port=PORT):
        self.host = host
        self.port = port
        self._sock = None
        self._threads = []
        self._stop = threading.Event()
        
        # Initialize the SSL Context for the server
        self.tls_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        self.tls_context.load_cert_chain(certfile=CERT_FILE, keyfile=KEY_FILE)

    def start(self):
        log_event("INFO", "server_start", host=self.host, port=self.port, tls="enabled")
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((self.host, self.port))
        self._sock.listen(50)
        try:
            while not self._stop.is_set():
                try:
                    conn, addr = self._sock.accept()
                except OSError:
                    break
                t = threading.Thread(target=client_worker, args=(conn, addr, self.tls_context), daemon=True)
                t.start()
                self._threads.append(t)
        except KeyboardInterrupt:
            log_event("INFO", "keyboard_interrupt")
        finally:
            self.shutdown()

    def shutdown(self):
        log_event("INFO", "server_shutdown")
        self._stop.set()
        try:
            if self._sock:
                self._sock.close()
        except Exception:
            pass
        for t in self._threads:
            if t.is_alive():
                t.join(timeout=0.1)

def _signal_handler(sig, frame):
    log_event("INFO", "signal_received", sig=sig)
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, _signal_handler)
    server = GracefulServer()
    server.start()