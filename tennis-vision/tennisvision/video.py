"""Video and audio IO through ffmpeg, so iPhone clips (HEVC, rotation flags, edit lists) decode correctly."""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from typing import Iterator

import numpy as np


@dataclass
class VideoInfo:
    width: int
    height: int
    fps: float
    pts: list[float]
    has_audio: bool

    @property
    def n_frames(self) -> int:
        return len(self.pts)

    @property
    def duration(self) -> float:
        return self.pts[-1] + 1.0 / self.fps if self.pts else 0.0


def _run(cmd: list[str]) -> str:
    return subprocess.run(cmd, check=True, capture_output=True, text=True).stdout


def probe(path: str) -> VideoInfo:
    meta = json.loads(_run([
        "ffprobe", "-v", "error", "-print_format", "json", "-show_streams", path,
    ]))
    video = next(s for s in meta["streams"] if s["codec_type"] == "video")
    has_audio = any(s["codec_type"] == "audio" for s in meta["streams"])
    w, h = int(video["width"]), int(video["height"])
    rotation = 0
    for side in video.get("side_data_list", []):
        if "rotation" in side:
            rotation = int(round(float(side["rotation"])))
    if abs(rotation) % 180 == 90:
        w, h = h, w
    raw = _run([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "frame=best_effort_timestamp_time", "-of", "csv=p=0", path,
    ])
    pts = []
    for line in raw.splitlines():
        token = line.strip().strip(",")
        if token and token != "N/A":
            pts.append(float(token.split(",")[0]))
    pts.sort()
    if len(pts) > 1:
        fps = (len(pts) - 1) / (pts[-1] - pts[0])
    else:
        num, den = video.get("avg_frame_rate", "30/1").split("/")
        fps = float(num) / max(float(den), 1.0)
    return VideoInfo(width=w, height=h, fps=fps, pts=pts, has_audio=has_audio)


def scaled_size(info: VideoInfo, max_side: int | None) -> tuple[int, int]:
    w, h = info.width, info.height
    if max_side and max(w, h) > max_side:
        s = max_side / max(w, h)
        w, h = int(round(w * s)), int(round(h * s))
    return w - w % 2, h - h % 2


def iter_frames(path: str, info: VideoInfo | None = None, max_side: int | None = None,
                start: float | None = None, end: float | None = None) -> Iterator[tuple[int, float, np.ndarray]]:
    """Yield (index, timestamp_seconds, BGR frame). Rotation is applied by ffmpeg."""
    info = info or probe(path)
    w, h = scaled_size(info, max_side)
    cmd = ["ffmpeg", "-v", "error"]
    if start is not None:
        cmd += ["-ss", f"{start:.3f}"]
    if end is not None:
        cmd += ["-to", f"{end:.3f}"]
    cmd += ["-i", path, "-an", "-sn", "-vf", f"scale={w}:{h}", "-fps_mode", "passthrough",
            "-pix_fmt", "bgr24", "-f", "rawvideo", "-"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, bufsize=w * h * 3)
    pts = info.pts
    if start is not None or end is not None:
        lo = start or 0.0
        hi = end if end is not None else float("inf")
        pts = [p for p in pts if lo - 1e-6 <= p < hi]
    step = 1.0 / info.fps
    i = 0
    try:
        while True:
            buf = proc.stdout.read(w * h * 3)
            if len(buf) < w * h * 3:
                break
            t = pts[i] if i < len(pts) else (pts[-1] + step * (i - len(pts) + 1) if pts else i * step)
            yield i, t, np.frombuffer(buf, np.uint8).reshape(h, w, 3)
            i += 1
    finally:
        proc.stdout.close()
        proc.kill()
        proc.wait()


class VideoWriter:
    """H.264 MP4 writer that plays in Safari/iOS."""

    def __init__(self, path: str, width: int, height: int, fps: float, crf: int = 20):
        self.width, self.height = width - width % 2, height - height % 2
        self.proc = subprocess.Popen([
            "ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24",
            "-s", f"{self.width}x{self.height}", "-r", f"{fps:.4f}", "-i", "-",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf), "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", path,
        ], stdin=subprocess.PIPE)

    def write(self, frame: np.ndarray) -> None:
        if frame.shape[1] != self.width or frame.shape[0] != self.height:
            frame = frame[: self.height, : self.width]
        self.proc.stdin.write(np.ascontiguousarray(frame).tobytes())

    def close(self) -> None:
        self.proc.stdin.close()
        self.proc.wait()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def read_audio(path: str, rate: int = 16000) -> np.ndarray:
    """Mono float32 audio in [-1, 1]; empty array if there is no audio track."""
    proc = subprocess.run([
        "ffmpeg", "-v", "error", "-i", path, "-vn", "-ac", "1", "-ar", str(rate),
        "-f", "s16le", "-",
    ], capture_output=True)
    if proc.returncode != 0 or not proc.stdout:
        return np.zeros(0, np.float32)
    return np.frombuffer(proc.stdout, np.int16).astype(np.float32) / 32768.0
