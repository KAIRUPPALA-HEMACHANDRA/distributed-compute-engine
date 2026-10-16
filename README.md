# Distributed Secure Compute Engine

A highly resilient, containerized Remote Procedure Call (RPC) microservice engineered to offload and process CPU-bound mathematical operations and data validation tasks.

This project bridges raw, low-latency socket networking with modern web accessibility. By combining a multithreaded Python TCP engine with a FastAPI REST wrapper and an asynchronous Redis job queue, the architecture ensures that heavy computational workloads never block user-facing web threads.

## 🏗️ Architectural Overview
The system is split into three distinct layers, orchestrated seamlessly via Docker Compose:

Core Socket Engine (server.py): A multithreaded, bare-metal TCP server utilizing a custom JSON-over-TCP framing protocol. It enforces strict sliding-window rate limiting per IP address, token-based authentication, and wraps all transmissions in a secure TLS (ssl.wrap_socket) tunnel.

REST API Gateway (api.py): A high-performance FastAPI web wrapper. It intercepts standard HTTP JSON payloads, validates them using strict Pydantic schemas, and translates them into the internal protocol required by the core engine.

Asynchronous Job Queue (worker.py & Redis): For computationally massive tasks (e.g., massive prime calculations or exponential math), the REST API instantly offloads the payload to a Redis queue. A dedicated background worker silently executes the CPU-bound task and stores the result, allowing the client to poll for completion without freezing the network connection.

## ✨ Key Features

Cryptographic Security: Enforced TLS 1.3 transport encryption alongside environment-level token authentication to prevent unauthorized execution.

DDoS & Overload Resilience: Custom IP-based sliding-window rate limiting and hardcoded maximum execution timeouts (10.0s) prevent malicious actors from locking server threads.

Mathematical & Validation Operations: Supports dynamic operations including add, sub, mul, div, power, modulo, is_even, is_prime, in_range, and complex regex_match.

Robust Observability: Structured JSON logging deployed across all nodes with automated file rotation, ensuring complete audit trails of client connections, handshake failures, and computational errors.

Complete Containerization: Multi-stage Dockerfile and docker-compose.yml guarantee immediate, reproducible deployments across any cloud or local environment.

Continuous Integration (CI): Automated GitHub Actions pipeline that dynamically provisions ephemeral TLS certificates to run the pytest suite on every code push.

## 🚀 Getting Started

### Prerequisites

Docker and Docker Compose installed.

OpenSSL (for generating local TLS certificates).

### 1. Generate Security Certificates
Before building the containers, generate a self-signed certificate in the project root to enable the TLS tunnel:
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -sha256 -days 365 -nodes -subj "/CN=localhost"

### 2. Boot the Distributed Environment
Use Docker Compose to build the multi-container ecosystem:
docker-compose up --build
This command will simultaneously launch the Core Socket Server, the Redis Cache, the Background Worker, and the FastAPI Gateway.

## 📡 API Usage & Endpoints
Once the containers are running, navigate to http://localhost:8000/docs to access the interactive Swagger UI.

Authentication: All HTTP requests require the x-auth-token header. The default development token is production_secret_key.

### Synchronous Execution (Lightweight Math)

POST /api/v1/compute
Executes lightweight mathematical operations and returns the result in the same HTTP connection.

### Asynchronous Execution (For Heavy Workloads)

POST /api/v1/compute/async
Instantly queues a massive mathematical operation in Redis and returns a unique job_id.

GET /api/v1/compute/status/{job_id}
Retrieves the status (queued, finished, failed) and the final mathematical result of the background task once complete.

## 🧪 Running the Test Suite
To run the automated pytest integration suite against the raw socket engine locally:
pytest tests/ -v


## 🗺️ Future Roadmap
While the core distributed architecture is stable, future iterations will focus on enhanced observability and binary efficiency:
*   **Telemetry & Observability:** Integrating Prometheus metrics and a Grafana dashboard for real-time tracking of queue depths, rate-limit triggers, and compute latency.
*   **Protocol Buffers (gRPC):** Migrating the internal communication payload from JSON over TCP to Protobufs to reduce serialization overhead and network bandwidth.
*   **Live Dashboarding:** Implementing a WebSocket layer on the FastAPI gateway to stream asynchronous job completion statuses to frontend clients in real-time.
*   **Fuzz Testing:** Expanding the `pytest` integration suite with mutation-driven fuzz testing to aggressively validate the Pydantic schemas against edge-case payload injection.