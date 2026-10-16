# Distributed Secure Compute Engine

A highly resilient, containerized Remote Procedure Call (RPC) microservice engineered to offload and process CPU-bound mathematical operations and data validation tasks. 

This project bridges raw, low-latency socket networking with modern web accessibility. By combining a multithreaded Python TCP engine with a FastAPI REST wrapper and an asynchronous Redis job queue, the architecture ensures that heavy computational workloads never block user-facing web threads.

## 🏗️ Architectural Overview

The system is split into three distinct layers, orchestrated seamlessly via Docker Compose:

1.  **Core Socket Engine (`server.py`)**: A multithreaded, bare-metal TCP server utilizing a custom JSON-over-TCP framing protocol. It enforces strict sliding-window rate limiting per IP address, token-based authentication, and wraps all transmissions in a secure TLS (`ssl.wrap_socket`) tunnel.
2.  **REST API Gateway (`api.py`)**: A high-performance FastAPI web wrapper. It intercepts standard HTTP JSON payloads, validates them using strict Pydantic schemas, and translates them into the internal protocol required by the core engine.
3.  **Asynchronous Job Queue (`worker.py` & Redis)**: For computationally massive tasks (e.g., massive prime calculations or exponential math), the REST API instantly offloads the payload to a Redis queue. A dedicated background worker silently executes the CPU-bound task and stores the result, allowing the client to poll for completion without freezing the network connection.

## ✨ Key Features

*   **Cryptographic Security**: Enforced TLS 1.3 transport encryption alongside environment-level token authentication to prevent unauthorized execution.
*   **DDoS & Overload Resilience**: Custom IP-based sliding-window rate limiting and hardcoded maximum execution timeouts (10.0s) prevent malicious actors from locking server threads.
*   **Mathematical & Validation Operations**: Supports dynamic operations including `add`, `sub`, `mul`, `div`, `power`, `modulo`, `is_even`, `is_prime`, `in_range`, and complex `regex_match`.
*   **Robust Observability**: Structured JSON logging deployed across all nodes with automated file rotation, ensuring complete audit trails of client connections, handshake failures, and computational errors.
*   **Complete Containerization**: Multi-stage `Dockerfile` and `docker-compose.yml` guarantee immediate, reproducible deployments across any cloud or local environment.
*   **Comprehensive Test Suite**: Automated integration testing utilizing `pytest` to validate concurrent connection handling, rate-limit threshold enforcement, and schema validation.

## 🚀 Getting Started

### Prerequisites
*   Docker and Docker Compose installed (WSL 2 backend recommended for Windows).
*   OpenSSL (for generating local TLS certificates).

### 1. Generate Security Certificates
Before building the containers, generate a self-signed certificate in the project root to enable the TLS tunnel:
```bash
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -sha256 -days 365 -nodes -subj "/CN=localhost"