#!/usr/bin/env python3
"""
persistent_client.py

Keeps a persistent connection to the server and lets you:
 - send single requests via CLI and exit
 - or start an interactive prompt and send multiple requests on the same connection

Features:
 - auto-reconnect with retries and exponential backoff
 - retries on transient socket errors
"""

import socket
import json
import sys
import uuid
import time
import random
from typing import Optional

HOST = "127.0.0.1"
PORT = 5000
CONNECT_TIMEOUT = 5.0
SOCK_RECV_TIMEOUT = 5.0

def create_connection_with_retries(host, port, max_retries=5, base_backoff=0.2):
    attempt = 0
    while attempt <= max_retries:
        try:
            s = socket.create_connection((host, port), timeout=CONNECT_TIMEOUT)
            s.settimeout(SOCK_RECV_TIMEOUT)
            return s
        except Exception as e:
            if attempt == max_retries:
                raise
            # exponential backoff with jitter
            backoff = base_backoff * (2 ** attempt)
            jitter = backoff * 0.2 * (random.random() * 2 - 1)
            delay = max(0.0, backoff + jitter)
            print(f"connect attempt {attempt+1} failed: {e}. retrying in {delay:.2f}s...")
            time.sleep(delay)
            attempt += 1
    raise RuntimeError("failed to connect")

def send_request_over_socket(sock, req):
    payload = (json.dumps(req, separators=(",", ":")) + "\n").encode("utf-8")
    sock.sendall(payload)
    data = bytearray()
    while True:
        chunk = sock.recv(4096)
        if not chunk:
            break
        data.extend(chunk)
        if b"\n" in data:
            line, _, _rest = bytes(data).partition(b"\n")
            return json.loads(line.decode("utf-8"))
    return None

def single_request_mode(argv):
    # supports optional --timeout similar to client.py
    timeout = None
    args = list(argv)
    if len(args) >= 2 and args[0] == "--timeout":
        try:
            timeout = float(args[1])
        except Exception:
            print("invalid timeout value")
            sys.exit(1)
        args = args[2:]
    if len(args) < 2:
        print("usage: persistent_client.py [--timeout secs] <op> <arg1> [arg2 ...]")
        sys.exit(1)
    op = args[0]
    op_args = args[1:]
    req = {"id": str(uuid.uuid4()), "op": op, "args": op_args}
    if timeout is not None:
        req["meta"] = {"timeout": timeout}
    # connect, send, receive, close
    sock = create_connection_with_retries(HOST, PORT)
    try:
        resp = send_request_over_socket(sock, req)
        print(json.dumps(resp, indent=2))
    finally:
        try:
            sock.close()
        except Exception:
            pass

def interactive_mode():
    print("Starting persistent interactive client. Type 'quit' to exit.")
    sock = create_connection_with_retries(HOST, PORT)
    print("Connected to server.")
    try:
        while True:
            line = input("pcs> ").strip()
            if not line:
                continue
            if line in ("quit", "exit"):
                break
            parts = line.split()
            op = parts[0]
            op_args = parts[1:]
            req = {"id": str(uuid.uuid4()), "op": op, "args": op_args}
            try:
                resp = send_request_over_socket(sock, req)
                print(json.dumps(resp, indent=2))
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, socket.error) as e:
                print("connection lost, attempting reconnect...")
                try:
                    sock.close()
                except Exception:
                    pass
                sock = create_connection_with_retries(HOST, PORT)
                print("reconnected. retrying last request...")
                try:
                    resp = send_request_over_socket(sock, req)
                    print(json.dumps(resp, indent=2))
                except Exception as e2:
                    print("retry failed:", e2)
    finally:
        try:
            sock.close()
        except Exception:
            pass

if __name__ == "__main__":
    if len(sys.argv) > 1:
        single_request_mode(sys.argv[1:])
    else:
        interactive_mode()