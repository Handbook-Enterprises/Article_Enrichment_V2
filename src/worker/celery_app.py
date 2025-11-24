import os
from celery import Celery
from pipeline import enrich

broker = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
backend = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")
app = Celery("enrichment", broker=broker, backend=backend)

@app.task
def enrich_task(article_path: str, keywords_path: str, out_path: str | None = None, model: str | None = None, offline: bool = False, qa_mode: str = "auto"):
    return enrich(article_path, keywords_path, out_path, model, offline, qa_mode)
