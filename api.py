from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
from typing import List, Optional, Any
import uuid
from redis import Redis
from rq import Queue
from rq.job import Job
from server import handle_request

app = FastAPI(title="Compute Engine REST API", version="2.0.0")

# Connect to the Redis container
redis_conn = Redis(host='redis_queue', port=6379)
q = Queue(connection=redis_conn)

class ComputeRequest(BaseModel):
    op: str
    args: List[Any]
    timeout: Optional[float] = 5.0

@app.post("/api/v1/compute")
def compute_sync(req: ComputeRequest, x_auth_token: str = Header(...)):
    payload = {"id": str(uuid.uuid4()), "op": req.op, "args": req.args, "meta": {"timeout": req.timeout, "auth_token": x_auth_token}}
    response = handle_request(payload, client_addr="REST_SYNC")
    if response.get("status") == "error":
        raise HTTPException(status_code=400, detail=response["error"])
    return response

@app.post("/api/v1/compute/async")
def compute_async(req: ComputeRequest, x_auth_token: str = Header(...)):
    payload = {"id": str(uuid.uuid4()), "op": req.op, "args": req.args, "meta": {"timeout": req.timeout, "auth_token": x_auth_token}}
    # Immediately drop the computation task into the Redis queue
    job = q.enqueue(handle_request, payload, "REST_ASYNC")
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
