#!/usr/bin/env python3
"""
client.py
Simple client to send one JSON request over TLS to the server and print response.
"""

import socket
import ssl
import json
import sys
import uuid
import os

HOST = '127.0.0.1'
PORT = 5000
TIMEOUT = 5.0

def send_request(req_obj):
    data = (json.dumps(req_obj, separators=(",", ":")) + "\n").encode('utf-8')
    
    # Configure the TLS context to trust our local self-signed certificate
    context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile="cert.pem")
    context.check_hostname = False  # Disabled strictly for local IP testing
    
    with socket.create_connection((HOST, PORT), timeout=TIMEOUT) as sock:
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

def parse_cli(argv):
    timeout = None
    argv2 = list(argv)
    if len(argv2) >= 2 and argv2[0] == "--timeout":
        try:
            timeout = float(argv2[1])
        except Exception:
            print("invalid timeout value")
            sys.exit(1)
        argv2 = argv2[2:]
    if len(argv2) < 2:
        print("usage: python client.py [--timeout seconds] <op> <arg1> [arg2 ...]")
        sys.exit(1)
    return argv2[0], argv2[1:], timeout

if __name__ == "__main__":
    op, args, timeout = parse_cli(sys.argv[1:])
    req = {
        "id": str(uuid.uuid4()),
        "op": op,
        "args": args,
        "meta": {}
    }
    if timeout is not None: req["meta"]["timeout"] = timeout
    
    client_token = os.environ.get("AUTH_TOKEN")
    if client_token: req["meta"]["auth_token"] = client_token
        
    resp = send_request(req)
    print("response:", json.dumps(resp, indent=2))