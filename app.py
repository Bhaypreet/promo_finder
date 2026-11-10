"""FastAPI service around the same LangGraph pipeline (deployable to Hugging Face Spaces with the Dockerfile).

    uvicorn app:app --port 7860        then open http://localhost:7860/docs

POST /jobs              upload a .zip of episode scripts -> job id (runs in the background)
GET  /jobs/{id}         status, run metadata and the ranked promos
GET  /jobs/{id}/cutlist download the editor's CSV cut list
POST /approve           add an approved promo to the playbook knowledge base (RAG feedback loop)

If APP_TOKEN is set, every call needs the header `Authorization: Bearer <APP_TOKEN>`.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import threading
import uuid
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from promo_finder.llm import load_env
from promo_finder.rag import KB
from run import run

load_env()
app = FastAPI(title="Promo Finder", description="Finds ranked 20-60 s promos in microdrama screenplays.")
JOBS: dict[str, dict] = {}
_one_at_a_time = threading.Lock()          # the free-tier token budget is shared, so jobs queue


def auth(authorization: str | None = Header(default=None)) -> None:
    token = os.environ.get("APP_TOKEN")
    if token and authorization != f"Bearer {token}":
        raise HTTPException(401, "missing or wrong bearer token")


class Approval(BaseModel):
    show: str
    title: str
    hook: str
    cliffhanger: str
    why: str


def _work(job_id: str, zip_path: str, episodes: str | None, rules_only: bool, montage: bool, viewer: bool) -> None:
    job = JOBS[job_id]
    with _one_at_a_time:
        job["status"] = "running"
        try:
            out = Path(tempfile.gettempdir()) / "promo_jobs" / job_id
            promos, meta = run(zip_path, episodes=episodes, rules_only=rules_only, montage=montage,
                               use_viewer=viewer, out=str(out), quiet=True)
            job.update(status="done", out=str(out), meta=meta,
                       promos=json.loads((out / "promos.json").read_text(encoding="utf-8"))["promos"])
        except Exception as e:
            job.update(status="failed", error=str(e)[:500])


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.post("/jobs", dependencies=[Depends(auth)])
async def create_job(background: BackgroundTasks, scripts: UploadFile = File(..., description=".zip of episode .txt files"),
                     episodes: str | None = Form(None, description="e.g. 1-10"), rules_only: bool = Form(False),
                     montage: bool = Form(True), viewer: bool = Form(True)) -> dict:
    if not scripts.filename.lower().endswith(".zip"):
        raise HTTPException(400, "upload a .zip of episode scripts")
    job_id = uuid.uuid4().hex[:10]
    tmp = Path(tempfile.mkdtemp(prefix="upload_")) / "show.zip"
    with tmp.open("wb") as f:
        shutil.copyfileobj(scripts.file, f)
    JOBS[job_id] = {"status": "queued"}
    background.add_task(_work, job_id, str(tmp), episodes, rules_only, montage, viewer)
    return {"job_id": job_id, "status": "queued"}


@app.get("/jobs/{job_id}", dependencies=[Depends(auth)])
def get_job(job_id: str) -> dict:
    if job_id not in JOBS:
        raise HTTPException(404, "unknown job")
    return {k: v for k, v in JOBS[job_id].items() if k != "out"}


@app.get("/jobs/{job_id}/cutlist", dependencies=[Depends(auth)])
def cutlist(job_id: str) -> FileResponse:
    job = JOBS.get(job_id)
    if not job or job.get("status") != "done":
        raise HTTPException(404, "job not finished")
    return FileResponse(Path(job["out"]) / "promos_cutlist.csv", filename="promos_cutlist.csv")


@app.post("/approve", dependencies=[Depends(auth)])
def approve(a: Approval) -> dict:
    with open(KB / "approved_promos.jsonl", "a", encoding="utf-8") as f:
        f.write(a.model_dump_json() + "\n")
    return {"ok": True, "note": "added to the playbook; retrieved as an example from the next run"}
