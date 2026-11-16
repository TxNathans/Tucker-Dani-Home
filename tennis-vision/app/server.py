"""Web app: upload a video from a phone, run swing or match analysis, read the results.

Run:  python -m app.server            (then open http://<this-computer's-ip>:8000 on the phone, same Wi-Fi)
"""
from __future__ import annotations

import json
import re
import shutil
import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse

ROOT = Path(__file__).resolve().parent
DATA = ROOT.parent / "data" / "jobs"
DATA.mkdir(parents=True, exist_ok=True)
ID_RE = re.compile(r"^[0-9a-f]{12}$")
FILE_RE = re.compile(r"^[A-Za-z0-9_.-]+$")

app = FastAPI(title="Tennis Vision")
worker = ThreadPoolExecutor(max_workers=1)          # one analysis at a time: the models use every core
jobs: dict[str, dict] = {}
lock = threading.Lock()


def job_dir(job_id: str) -> Path:
    if not ID_RE.match(job_id):
        raise HTTPException(404, "Unknown job")
    return DATA / job_id


def save_meta(job_id: str) -> None:
    with lock:
        meta = {k: v for k, v in jobs[job_id].items() if k != "report"}
    (DATA / job_id / "job.json").write_text(json.dumps(meta))


def load_jobs() -> None:
    for meta_file in DATA.glob("*/job.json"):
        try:
            meta = json.loads(meta_file.read_text())
        except json.JSONDecodeError:
            continue
        if meta.get("status") in ("queued", "running"):
            meta.update(status="error", error="The server restarted before this finished. Upload the video again.")
        jobs[meta["id"]] = meta


def run_job(job_id: str) -> None:
    job = jobs[job_id]
    folder = DATA / job_id
    job.update(status="running", started=time.time())

    def progress(fraction: float) -> None:
        job["progress"] = round(float(fraction), 3)

    try:
        params = job["params"]
        if job["kind"] == "swing":
            from tennisvision.swing.pipeline import analyze_video
            analyze_video(str(folder / job["video"]), str(folder), height_m=params["height_m"], handedness=params["hand"],
                          progress=progress)
        else:
            from tennisvision.match.pipeline import analyze_match
            analyze_match(str(folder / job["video"]), str(folder), fmt=params["format"], names=params["names"],
                          hands=params["hands"], corners=params["corners"], height_m=params["height_m"],
                          session="lesson" if job["kind"] == "lesson" else "match", progress=progress)
        job.update(status="done", progress=1.0, finished=time.time())
    except Exception as exc:                       # report the failure to the phone instead of dying silently
        traceback.print_exc()
        message = str(exc) if isinstance(exc, ValueError) else f"Analysis failed: {type(exc).__name__}: {exc}"
        job.update(status="error", error=message, finished=time.time())
    save_meta(job_id)


@app.post("/api/jobs")
async def create_job(video: UploadFile = File(...), kind: str = Form("swing"), height_cm: float = Form(170.0),
                     hand: str = Form("auto"), format: str = Form("singles"), names: str = Form(""),
                     hands: str = Form(""), corners: str = Form(""), title: str = Form("")):
    if kind not in ("swing", "match", "lesson") or format not in ("singles", "doubles") or hand not in ("auto", "right", "left"):
        raise HTTPException(400, "Bad options")
    if not 100 <= height_cm <= 230:
        raise HTTPException(400, "Height must be between 100 and 230 cm")
    corner_list = None
    if corners:
        try:
            corner_list = json.loads(corners)
            assert len(corner_list) == 4 and all(len(c) == 2 and 0 <= float(c[0]) <= 1 and 0 <= float(c[1]) <= 1 for c in corner_list)
            corner_list = [[float(c[0]), float(c[1])] for c in corner_list]
        except (ValueError, AssertionError, TypeError):
            raise HTTPException(400, "Court corners must be four [x, y] pairs between 0 and 1")
    job_id = uuid.uuid4().hex[:12]
    folder = DATA / job_id
    folder.mkdir(parents=True)
    suffix = Path(video.filename or "video.mp4").suffix.lower()
    if suffix not in (".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"):
        suffix = ".mp4"
    name = "source" + suffix
    with open(folder / name, "wb") as fh:
        shutil.copyfileobj(video.file, fh, length=1024 * 1024)
    clean = lambda s: s.strip()[:40]
    jobs[job_id] = dict(
        id=job_id, kind=kind, status="queued", progress=0.0, created=time.time(), video=name,
        title=clean(title) or (video.filename or "Video"),
        params=dict(height_m=height_cm / 100.0, hand=hand, format=format,
                    names=[clean(n) for n in names.split(",")] if names.strip() else None,
                    hands=[h if h in ("right", "left") else "right" for h in hands.split(",")] if hands.strip() else None,
                    corners=corner_list),
    )
    save_meta(job_id)
    worker.submit(run_job, job_id)
    return dict(id=job_id)


@app.get("/api/jobs")
def list_jobs():
    rows = [{k: j.get(k) for k in ("id", "kind", "status", "progress", "created", "title", "error")} for j in jobs.values()]
    return sorted(rows, key=lambda r: -r["created"])


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    folder = job_dir(job_id)
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(404, "Unknown job")
    out = {k: job.get(k) for k in ("id", "kind", "status", "progress", "created", "title", "error")}
    report = folder / "report.json"
    if job["status"] == "done" and report.exists():
        out["report"] = json.loads(report.read_text())
    return JSONResponse(out)


@app.delete("/api/jobs/{job_id}")
def delete_job(job_id: str):
    folder = job_dir(job_id)
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(404, "Unknown job")
    if job["status"] in ("queued", "running"):
        raise HTTPException(409, "Still running")
    jobs.pop(job_id)
    shutil.rmtree(folder, ignore_errors=True)
    return dict(ok=True)


@app.get("/files/{job_id}/{name}")
def get_file(job_id: str, name: str):
    folder = job_dir(job_id)
    if not FILE_RE.match(name) or name.startswith("source") or name == "job.json":
        raise HTTPException(404, "Not found")
    path = folder / name
    if not path.is_file():
        raise HTTPException(404, "Not found")
    return FileResponse(path)


@app.get("/")
def index():
    return FileResponse(ROOT / "static" / "index.html", headers={"Cache-Control": "no-cache"})


load_jobs()


def main() -> None:
    import argparse
    import uvicorn
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
