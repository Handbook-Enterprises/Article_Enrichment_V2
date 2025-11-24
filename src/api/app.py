import os
from fastapi import FastAPI
from pydantic import BaseModel
from celery.result import AsyncResult
from worker.celery_app import enrich_task

class EnrichRequest(BaseModel):
    article_path: str
    keywords_path: str
    out_path: str | None = None
    model: str | None = None
    offline: bool = False
    qa_mode: str = "auto"

app = FastAPI()

@app.post("/tasks")
def add_task(req: EnrichRequest):
    r = enrich_task.delay(req.article_path, req.keywords_path, req.out_path, req.model, req.offline, req.qa_mode)
    return {"task_id": r.id}

@app.get("/tasks/{task_id}")
def task_status(task_id: str):
    r = AsyncResult(task_id)
    return {"task_id": task_id, "state": r.state, "result": r.result if r.ready() else None}
