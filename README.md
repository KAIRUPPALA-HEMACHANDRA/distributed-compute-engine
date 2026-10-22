# Distributed Secure Compute Engine

A production-grade, containerized Remote Procedure Call (RPC) and asynchronous microservice platform engineered to execute CPU-bound mathematical operations and data validation workloads.

This system bridges low-latency, TLS-encrypted TCP socket networking with modern web architecture, combining a multithreaded Python core engine, a FastAPI REST & WebSocket gateway, an asynchronous Redis job queue, Protocol Buffers binary serialization, and real-time Prometheus/Grafana observability.

---

## 🏗️ System Architecture

The platform is architected across six containerized services orchestrated via Docker Compose:

1. **Core Socket Engine (`server.py` - Port `5000`)**: A multithreaded TCP server utilizing newline-framed messaging wrapped in TLS (`ssl`). Enforces per-IP sliding-window rate limiting, token authentication, and strict execution timeouts (max 10.0s).
2. **FastAPI REST & WebSocket Gateway (`api.py` - Port `8000`)**: Validates incoming HTTP payloads via Pydantic schemas, routes lightweight tasks synchronously, offloads heavy computations to Redis, and streams live job updates to browser clients over WebSockets.
3. **Redis Message Broker (`redis:7-alpine` - Port `6379`)**: In-memory queue and state store backing asynchronous job persistence.
4. **Asynchronous Background Worker (`worker.py`)**: Dedicated RQ worker node that pulls heavy CPU-bound tasks from Redis and executes them without blocking web-facing threads.
5. **Prometheus Telemetry Server (`prom/prometheus` - Port `9090`)**: Scrapes real-time request counters and latency histograms from the FastAPI `/metrics` endpoint every 5 seconds.
6. **Grafana Observability Dashboard (`grafana/grafana` - Port `3000`)**: Visualizes live API throughput, operation distribution, and latency metrics.

---

## ✨ Key Engineering Features

* **Transport & Application Security**: 4096-bit RSA TLS encryption for raw socket transport alongside header/payload token authentication (`AUTH_TOKEN`).
* **Traffic & Overload Protection**: Custom IP-based sliding-window rate limiter (`RATE_LIMIT_MAX_REQUESTS = 50`) and thread-level execution timeouts prevent resource exhaustion.
* **Comprehensive Compute & Validation Suite**:
  * **Math Operations**: `add`, `sub`, `mul`, `div`, `power` (with exponent safety bounds), and `modulo`.
  * **Validation Operations**: `is_even`, `is_prime`, `in_range`, and `regex_match`.
* **Live Web UI & WebSocket Streaming (`/dashboard`)**: Interactive browser control panel that submits async jobs to Redis and streams real-time status transitions (`QUEUED` -> `FINISHED`) and arbitrarily large integer results via WebSockets.
* **Binary Protocol Buffers (`compute.proto` & `proto_codec.py`)**: Supports compact `proto3` binary serialization to minimize payload size compared to plain-text JSON.
* **Observability Stack**: Built-in Prometheus instrumentation (`compute_requests_total` and `compute_request_latency_seconds`) paired with Grafana dashboards.
* **Automated CI & Fuzz Testing**: GitHub Actions pipeline dynamically provisions ephemeral TLS certificates and executes 22 `pytest` suites—including **Hypothesis** property-based fuzz testing that bombards the engine with randomized malformed payloads.

---

## 🚀 Quick Start (Docker Compose)

### Prerequisites
* Docker & Docker Compose
* OpenSSL (for generating local self-signed TLS certificates)

### 1. Generate Local TLS Certificates
In the project root directory, generate a self-signed certificate and private key:
```bash
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -sha256 -days 365 -nodes -subj "/CN=localhost"