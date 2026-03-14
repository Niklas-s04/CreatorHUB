from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from rq.job import Job

from app.api.deps import get_current_user, require_role
from app.models.user import User, UserRole
from app.schemas.images import ImageSearchRequest, JobStatusOut
from app.workers.queue import default_queue, redis_conn
from app.workers.jobs import image_hunt_job

router = APIRouter()


@router.post("/search", response_model=JobStatusOut)
def start_search(payload: ImageSearchRequest, _: User = Depends(require_role(UserRole.admin, UserRole.editor))) -> JobStatusOut:
    job = default_queue.enqueue(
        image_hunt_job,
        str(payload.product_id),
        payload.query,
        payload.max_results,
        payload.source,
        job_timeout=600,
        result_ttl=3600,
    )
    return JobStatusOut(job_id=job.id, status=job.get_status())


@router.get("/jobs/{job_id}", response_model=JobStatusOut)
def job_status(job_id: str, _: User = Depends(get_current_user)) -> JobStatusOut:
    try:
        job = Job.fetch(job_id, connection=redis_conn)
    except Exception:
        raise HTTPException(status_code=404, detail="Job not found")
    status = job.get_status()
    result = None
    error = None
    if status == "finished":
        result = job.result
    if status == "failed":
        error = str(job.exc_info)[-2000:] if job.exc_info else "failed"
    return JobStatusOut(job_id=job.id, status=status, result=result, error=error)
