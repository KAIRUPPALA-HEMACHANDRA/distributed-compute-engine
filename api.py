from fastapi import FastAPI, HTTPException, Header, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import List, Optional, Any
import uuid
import time
import asyncio
from pathlib import Path
from redis import Redis
from rq import Queue
from rq.job import Job
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from server import handle_request

app = FastAPI(title="Compute Engine REST API", version="2.2.0")

# Connect to the Redis container
redis_conn = Redis(host='redis_queue', port=6379)
q = Queue(connection=redis_conn)

# Define Prometheus Telemetry Metrics
REQUEST_COUNT = Counter(
    "compute_requests_total",
    "Total compute requests processed by the gateway",
    ["mode", "operation", "status"]
)
REQUEST_LATENCY = Histogram(
    "compute_request_latency_seconds",
    "Time spent processing compute requests",
    ["mode"]
)

class ComputeRequest(BaseModel):
    op: str
    args: List[Any]
    timeout: Optional[float] = 5.0

@app.get("/dashboard", response_class=HTMLResponse)
def serve_dashboard():
    return Path("dashboard.html").read_text(encoding="utf-8")

@app.post("/api/v1/compute")
def compute_sync(req: ComputeRequest, x_auth_token: str = Header(...)):
    start_time = time.time()
    payload = {"id": str(uuid.uuid4()), "op": req.op, "args": req.args, "meta": {"timeout": req.timeout, "auth_token": x_auth_token}}
    response = handle_request(payload, client_addr="REST_SYNC")
    
    REQUEST_LATENCY.labels(mode="sync").observe(time.time() - start_time)
    
    if response.get("status") == "error":
        REQUEST_COUNT.labels(mode="sync", operation=req.op, status="error").inc()
        raise HTTPException(status_code=400, detail=response["error"])
        
    REQUEST_COUNT.labels(mode="sync", operation=req.op, status="ok").inc()
    return response

@app.post("/api/v1/compute/async")
def compute_async(req: ComputeRequest, x_auth_token: str = Header(...)):
    start_time = time.time()
    payload = {"id": str(uuid.uuid4()), "op": req.op, "args": req.args, "meta": {"timeout": req.timeout, "auth_token": x_auth_token}}
    job = q.enqueue(handle_request, payload, "REST_ASYNC")
    
    REQUEST_LATENCY.labels(mode="async").observe(time.time() - start_time)
    REQUEST_COUNT.labels(mode="async", operation=req.op, status="queued").inc()
    return {"job_id": job.get_id(), "status": "queued", "message": "Task offloaded to background worker."}

@app.get("/api/v1/compute/status/{job_id}")
def check_async_status(job_id: str):
    try:
        job = Job.fetch(job_id, connection=redis_conn)
    except Exception:
        raise HTTPException(status_code=404, detail="Job ID not found in Redis.")
    
    if job.is_finished:
        return {"job_id": job_id, "status": "finished", "result": job.result}
    elif job.is_failed:
        return {"job_id": job_id, "status": "failed"}
    else:
        return {"job_id": job_id, "status": job.get_status()}

@app.websocket("/ws/status/{job_id}")
async def websocket_job_status(websocket: WebSocket, job_id: str):
    await websocket.accept()
    try:
        while True:
            try:
                job = Job.fetch(job_id, connection=redis_conn)
            except Exception:
                await websocket.send_json({"job_id": job_id, "status": "not_found"})
                break

            if job.is_finished:
                result_data = job.result
                # Convert huge integers (> 2^53 - 1) to strings so browser JSON doesn't turn them into null
                if isinstance(result_data, dict) and isinstance(result_data.get("result"), int):
                    if abs(result_data["result"]) > 9007199254740991:
                        result_data = {**result_data, "result": str(result_data["result"])}
                await websocket.send_json({"job_id": job_id, "status": "finished", "result": result_data})
                break
            elif job.is_failed:
                await websocket.send_json({"job_id": job_id, "status": "failed"})
                break
            else:
                await websocket.send_json({"job_id": job_id, "status": job.get_status()})

            await asyncio.sleep(0.3)
    except WebSocketDisconnect:
        pass

@app.get("/metrics")
def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)