#!/usr/bin/env python3
"""
concurrent_test.py
Spawns many client threads that connect to the server concurrently and send requests.
"""

import threading
import socket
import json
import uuid
import time
import random

HOST = "127.0.0.1"
PORT = 5000
THREADS = 40
REQUESTS_PER_THREAD = 10

def worker(tid):
    for i in range(REQUESTS_PER_THREAD):
        op = random.choice(["add", "mul", "sub", "div"])
        if op == "div":
            a = random.randint(1, 100)
            b = random.randint(1, 100)  # avoid zero
            args = [a, b]
        elif op == "sub":
            a = random.randint(1, 200)
            b = random.randint(1, 100)
            args = [a, b]
        else:
            a = random.randint(1, 50)
            b = random.randint(1, 50)
            args = [a, b]
        req = {"id": str(uuid.uuid4()), "op": op, "args": args}
        try:
            with socket.create_connection((HOST, PORT), timeout=5) as s:
                s.sendall((json.dumps(req) + "\n").encode("utf-8"))
                data = b""
                while True:
                    chunk = s.recv(1024)
                    if not chunk:
                        break
                    data += chunk
                    if b"\n" in data:
                        line, _, _ = data.partition(b"\n")
                        break
                if not data:
                    print(f"[{tid}] no data back for {op} {args}")
                else:
                    resp = json.loads(line.decode("utf-8"))
                    print(f"[{tid}] {op} {args} -> {resp.get('status')}")
        except Exception as e:
            print(f"[{tid}] exception: {e}")
        time.sleep(random.random() * 0.2)

threads = []
for i in range(THREADS):
    t = threading.Thread(target=worker, args=(i,), daemon=True)
    t.start()
    threads.append(t)

for t in threads:
    t.join()

print("concurrent_test complete")