"""Web app: upload a video from a phone, run swing or match analysis, read the results.

Run:  python -m app.server            (then open http://<this-computer's-ip>:8000 on the phone, same Wi-Fi)
"""
from __future__ import annotations

import json
import re
import shutil
import socket
import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from tennisvision.paths import jobs_dir
from fastapi import Body, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent
DATA = jobs_dir()       # inside the project when run from source; the per-computer folder when started by the launcher
DATA.mkdir(parents=True, exist_ok=True)
ID_RE = re.compile(r"^[0-9a-f]{12}$")
SAFE_NAME = re.compile(r"[^A-Za-z0-9 _.-]+")
TOOLS = {"line", "angle", "circle", "pen"}
LIST_KEYS = ("id", "kind", "status", "progress", "created", "title", "error", "starred")
FILE_RE = re.compile(r"^[A-Za-z0-9_.-]+$")

app = FastAPI(title="Tracer Tennis")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
PORT = 8000
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
        if job["kind"] in ("swing", "serve"):
            from tennisvision.swing.pipeline import analyze_video
            analyze_video(str(folder / job["video"]), str(folder), height_m=params["height_m"], handedness=params["hand"],
                          mode=job["kind"], serve_type=params.get("serve_type", "auto"), progress=progress)
        else:
            from tennisvision.match.pipeline import analyze_match
            analyze_match(str(folder / job["video"]), str(folder), fmt=params["format"], names=params["names"],
                          hands=params["hands"], corners=params["corners"], height_m=params["height_m"],
                          session="lesson" if job["kind"] == "lesson" else "match", progress=progress)
        job.update(status="done", progress=1.0, finished=time.time())
    except Exception as exc:                       # report the failure to the phone instead of dying silently
        traceback.print_exc()
        message = str(exc) if isinstance(exc, ValueError) else f"Analysis failed: {type(exc).__name__}: {exc}"
        if isinstance(exc, ModuleNotFoundError) and (exc.name or "").split(".")[0] == "torch":
            message = NO_BALL_TRACKING
        job.update(status="error", error=message, finished=time.time())
    save_meta(job_id)


@app.post("/api/jobs")
async def create_job(video: UploadFile = File(...), kind: str = Form("swing"), height_cm: float = Form(170.0),
                     hand: str = Form("auto"), format: str = Form("singles"), names: str = Form(""),
                     hands: str = Form(""), corners: str = Form(""), title: str = Form(""), serve_type: str = Form("auto")):
    if (kind not in ("swing", "serve", "match", "lesson") or format not in ("singles", "doubles")
            or hand not in ("auto", "right", "left") or serve_type not in ("auto", "flat", "slice", "kick")):
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
        params=dict(height_m=height_cm / 100.0, hand=hand, format=format, serve_type=serve_type,
                    names=[clean(n) for n in names.split(",")] if names.strip() else None,
                    hands=[h if h in ("right", "left") else "right" for h in hands.split(",")] if hands.strip() else None,
                    corners=corner_list),
    )
    save_meta(job_id)
    worker.submit(run_job, job_id)
    return dict(id=job_id)


@app.get("/api/jobs")
def list_jobs():
    rows = [{k: j.get(k) for k in LIST_KEYS} for j in jobs.values()]
    return sorted(rows, key=lambda r: -r["created"])


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    folder = job_dir(job_id)
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(404, "Unknown job")
    out = {k: job.get(k) for k in LIST_KEYS}
    out["notes"] = job.get("notes", "")
    report = folder / "report.json"
    if job["status"] == "done" and report.exists():
        out["report"] = json.loads(report.read_text())
    marks = folder / "marks.json"
    out["marks"] = json.loads(marks.read_text()) if marks.exists() else []
    return JSONResponse(out)


@app.patch("/api/jobs/{job_id}")
def update_job(job_id: str, changes: dict = Body(...)):
    """Rename a video, star it, or save notes with it."""
    job_dir(job_id)
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(404, "Unknown job")
    if "title" in changes:
        title = str(changes["title"]).strip()[:80]
        if not title:
            raise HTTPException(400, "The name cannot be empty")
        job["title"] = title
    if "starred" in changes:
        job["starred"] = bool(changes["starred"])
    if "notes" in changes:
        job["notes"] = str(changes["notes"])[:4000]
    save_meta(job_id)
    return {k: job.get(k) for k in LIST_KEYS} | dict(notes=job.get("notes", ""))


@app.put("/api/jobs/{job_id}/marks")
def save_marks(job_id: str, marks: list = Body(...)):
    """Save the drawings made on a video: one list per video on screen, each a list of {tool, color, pts}."""
    folder = job_dir(job_id)
    if job_id not in jobs:
        raise HTTPException(404, "Unknown job")
    clean = []
    try:
        assert len(marks) <= 2
        for stage in marks:
            assert len(stage) <= 200
            rows = []
            for m in stage:
                pts = [[round(float(x), 4), round(float(y), 4)] for x, y in m["pts"]]
                assert m["tool"] in TOOLS and re.fullmatch(r"#[0-9a-fA-F]{6}", m["color"]) and 2 <= len(pts) <= 2000
                rows.append(dict(tool=m["tool"], color=m["color"], pts=pts))
            clean.append(rows)
    except (AssertionError, KeyError, TypeError, ValueError):
        raise HTTPException(400, "Drawings were not in the expected form")
    (folder / "marks.json").write_text(json.dumps(clean, separators=(",", ":")))
    return dict(saved=sum(len(s) for s in clean))


def download_name(job: dict, suffix: str) -> str:
    title = re.sub(r"\.[A-Za-z0-9]{2,4}$", "", job.get("title") or "video")
    base = SAFE_NAME.sub("", title).strip() or "tracer-tennis"
    return f"{base[:60]} {suffix}"


@app.get("/api/jobs/{job_id}/report.pdf")
def report_pdf(job_id: str, swing: int = 1):
    """The read for one swing or serve as a PDF."""
    from .report_pdf import build_pdf
    job, report, picked = pick_swing(f"{job_id}:{swing}")
    data = build_pdf(job, report, picked, DATA / job_id, job.get("notes", ""))
    name = download_name(job, "report.pdf")
    return Response(data, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{name}"'})


@app.get("/api/jobs/{job_id}/numbers.csv")
def numbers_csv(job_id: str, swing: int = 1):
    """Every number for one swing or serve as a spreadsheet file."""
    from .report_pdf import numbers_csv as build
    job, _, picked = pick_swing(f"{job_id}:{swing}")
    name = download_name(job, "numbers.csv")
    return Response(build(picked), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{name}"'})


@app.get("/api/jobs/{job_id}/shots.csv")
def shots_csv(job_id: str):
    """Every shot of a lesson or match as a spreadsheet file."""
    import csv
    import io
    folder = job_dir(job_id)
    job = jobs.get(job_id)
    path = folder / "report.json"
    if job is None or job["status"] != "done" or job["kind"] not in ("match", "lesson") or not path.exists():
        raise HTTPException(404, "No analysed lesson or match with that id")
    report = json.loads(path.read_text())
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["Rally", "Time (s)", "Player", "Stroke", "Contact", "Result", "Speed (mph)", "Landing depth"])
    for rally in report.get("rallies", []):
        for s in rally["shots"]:
            mph = round(s["speed_kmh"] * 0.621) if s.get("speed_kmh") else ""
            w.writerow([rally["n"], s["t"], s["name"], s["stroke"], s["contact"], s["result"], mph, s.get("depth", "")])
    name = download_name(job, "shots.csv")
    return Response(out.getvalue(), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{name}"'})


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


def swing_report(job_id: str) -> dict:
    """The stored report of a finished swing or serve job."""
    folder = job_dir(job_id)
    job = jobs.get(job_id)
    path = folder / "report.json"
    if job is None or job["status"] != "done" or job["kind"] not in ("swing", "serve") or not path.exists():
        raise HTTPException(404, "No analysed swing with that id")
    return json.loads(path.read_text())


def swing_name(stroke: str, serve: dict | None) -> str:
    return f"{serve['type'].capitalize()} serve" if serve and serve.get("type") in ("flat", "slice", "kick") else stroke.capitalize()


@app.get("/api/swings")
def list_swings():
    """Every analysed swing and serve, newest video first, for the compare picker."""
    rows = []
    for job in sorted(jobs.values(), key=lambda j: -j["created"]):
        if job["status"] != "done" or job["kind"] not in ("swing", "serve"):
            continue
        try:
            report = swing_report(job["id"])
        except (HTTPException, json.JSONDecodeError):
            continue
        for s in report["swings"]:
            coaching = s.get("coaching") or {}
            rows.append(dict(ref=f"{job['id']}:{s['index']}", job=job["id"], index=s["index"], title=job["title"], kind=job["kind"],
                             created=job["created"], name=swing_name(s["stroke"], s.get("serve")), stroke=s["stroke"],
                             hand=s["hand"], counts=coaching.get("counts"), light=coaching.get("light"),
                             keyframe=report.get("keyframes", {}).get(f"{s['index']}:contact")))
    return rows


def pick_swing(ref: str) -> tuple[dict, dict, dict]:
    """ref is "<job id>:<swing number>". Returns the job, its report and the swing."""
    job_id, _, number = ref.partition(":")
    report = swing_report(job_id)
    swing = next((s for s in report["swings"] if str(s["index"]) == number), None)
    if swing is None:
        raise HTTPException(404, "That video has no swing with that number")
    return jobs[job_id], report, swing


@app.get("/api/compare")
def compare(a: str, b: str):
    """Compare two analysed swings: a is the baseline, b the retest."""
    from tennisvision.swing.compare import compare_swings
    if a == b:
        raise HTTPException(400, "Pick two different swings")
    (job_a, report_a, swing_a), (job_b, report_b, swing_b) = pick_swing(a), pick_swing(b)
    if (job_a["kind"] == "serve") != (job_b["kind"] == "serve"):
        raise HTTPException(400, "Compare a serve with a serve, or a swing with a swing")
    side = lambda job, report, swing: dict(
        job=job["id"], index=swing["index"], title=job["title"], kind=job["kind"], created=job["created"],
        name=swing_name(swing["stroke"], swing.get("serve")), fps=report["video"]["fps"], contact=swing["times"]["contact"],
        contact_frame=swing["frames"]["contact"], files=report["files"], swing=swing)
    out = compare_swings(swing_a, swing_b, "Baseline", "Retest")
    out.update(a=side(job_a, report_a, swing_a), b=side(job_b, report_b, swing_b))
    return JSONResponse(out)


@app.get("/files/{job_id}/{name}")
def get_file(job_id: str, name: str, download: int = 0):
    folder = job_dir(job_id)
    if not FILE_RE.match(name) or name.startswith("source") or name == "job.json":
        raise HTTPException(404, "Not found")
    path = folder / name
    if not path.is_file():
        raise HTTPException(404, "Not found")
    if download and job_id in jobs:
        return FileResponse(path, filename=download_name(jobs[job_id], "marked up" + path.suffix))
    return FileResponse(path)


NO_BALL_TRACKING = ("Lesson and Match need PyTorch to follow the ball, and it is not installed on this computer. "
                    "Close Tracer Tennis and start it again to retry the install. Swing, Serve and Compare work without it.")


def ball_tracking() -> bool:
    import importlib.util
    return importlib.util.find_spec("torch") is not None


def lan_addresses() -> list[str]:
    """IPv4 addresses other devices can use to reach this computer (home Wi-Fi first, then VPNs such as Tailscale)."""
    found: list[str] = []
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe.connect(("10.255.255.255", 1))          # no packet is sent; this only picks the outgoing interface
        found.append(probe.getsockname()[0])
        probe.close()
    except OSError:
        pass
    try:
        for item in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            found.append(item[4][0])
    except OSError:
        pass
    unique = [a for i, a in enumerate(found) if a not in found[:i] and not a.startswith("127.")]
    return unique


@app.get("/api/info")
def info():
    return dict(computer=socket.gethostname(), urls=[f"http://{a}:{PORT}" for a in lan_addresses()], ball_tracking=ball_tracking())


@app.get("/api/qr")
def qr():
    """QR code for the first address a phone on the same network can open."""
    import io
    import segno
    urls = info()["urls"]
    if not urls:
        raise HTTPException(404, "This computer has no network address")
    buf = io.BytesIO()
    segno.make(urls[0], error="m").save(buf, kind="svg", scale=6, border=2, dark="#14201a", light="#ffffff")
    return Response(buf.getvalue(), media_type="image/svg+xml", headers={"Cache-Control": "no-store"})


@app.get("/")
def index():
    return FileResponse(ROOT / "static" / "index.html", headers={"Cache-Control": "no-cache"})


load_jobs()


def open_app_window(url: str) -> None:
    """Open the app in its own window (Chrome or Edge app mode) or, failing that, the default browser."""
    import os
    import subprocess
    import webbrowser
    candidates = [
        os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        shutil.which("google-chrome") or "", shutil.which("chromium") or "",
    ]
    for exe in candidates:
        if exe and Path(exe).is_file():
            try:
                subprocess.Popen([exe, f"--app={url}", "--window-size=460,900"])
                return
            except OSError:
                continue
    webbrowser.open(url)


def main() -> None:
    global PORT
    import argparse
    import uvicorn
    from tennisvision import ensure_ffmpeg
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--open", action="store_true", help="open the app in a window once the server is up")
    args = ap.parse_args()
    PORT = args.port
    ensure_ffmpeg()
    here = f"http://localhost:{PORT}"
    print(f"\nTracer Tennis is running.\n  On this computer: {here}")
    for url in info()["urls"]:
        print(f"  On your iPhone (same Wi-Fi): {url}")
    print("  Scan the QR code on the app's home page with the iPhone camera to open it there.\n", flush=True)
    if args.open:
        threading.Timer(1.5, open_app_window, args=(here,)).start()
    uvicorn.run(app, host=args.host, port=PORT, log_level="warning")


if __name__ == "__main__":
    main()
