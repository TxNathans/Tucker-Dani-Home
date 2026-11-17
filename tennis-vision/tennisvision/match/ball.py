"""Ball tracking with WASB (HRNet heatmap model, MIT licence, tennis weights from the authors)."""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from ..paths import model_dir

MODEL_DIR = model_dir()
WEIGHTS = MODEL_DIR / "wasb_tennis_best.pth.tar"
WEIGHTS_GDRIVE_ID = "14AeyIOCQ2UaQmbZLNQJa1H_eSwxUXk7z"
IN_W, IN_H = 512, 288
MEAN = np.array([0.485, 0.456, 0.406], np.float32)
STD = np.array([0.229, 0.224, 0.225], np.float32)

WASB_CFG = dict(
    name="hrnet", frames_in=3, frames_out=3, inp_height=IN_H, inp_width=IN_W, out_height=IN_H, out_width=IN_W,
    rgb_diff=False, out_scales=[0],
    MODEL=dict(INIT_WEIGHTS=False, EXTRA=dict(
        FINAL_CONV_KERNEL=1, PRETRAINED_LAYERS=["*"], STEM=dict(INPLANES=64, STRIDES=[1, 1]),
        STAGE1=dict(NUM_MODULES=1, NUM_BRANCHES=1, BLOCK="BOTTLENECK", NUM_BLOCKS=[1], NUM_CHANNELS=[32], FUSE_METHOD="SUM"),
        STAGE2=dict(NUM_MODULES=1, NUM_BRANCHES=2, BLOCK="BASIC", NUM_BLOCKS=[2, 2], NUM_CHANNELS=[16, 32], FUSE_METHOD="SUM"),
        STAGE3=dict(NUM_MODULES=1, NUM_BRANCHES=3, BLOCK="BASIC", NUM_BLOCKS=[2, 2, 2], NUM_CHANNELS=[16, 32, 64], FUSE_METHOD="SUM"),
        STAGE4=dict(NUM_MODULES=1, NUM_BRANCHES=4, BLOCK="BASIC", NUM_BLOCKS=[2, 2, 2, 2], NUM_CHANNELS=[16, 32, 64, 128], FUSE_METHOD="SUM"),
        DECONV=dict(NUM_DECONVS=0, KERNEL_SIZE=[], NUM_BASIC_BLOCKS=2),
    )),
)


class _Cfg(dict):
    """Dict with attribute access, standing in for the OmegaConf object the WASB code expects."""

    def __getattr__(self, key):
        value = self[key]
        return _Cfg(value) if isinstance(value, dict) else value


def ensure_weights() -> str:
    if not WEIGHTS.exists():
        import gdown
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        gdown.download(id=WEIGHTS_GDRIVE_ID, output=str(WEIGHTS), quiet=True)
    return str(WEIGHTS)


class BallDetector:
    """Feeds three consecutive frames to the network and returns ball candidates for each of them."""

    def __init__(self, threshold: float = 0.5, threads: int | None = None):
        import torch
        from .wasb_hrnet import HRNet
        self.torch = torch
        if threads:
            torch.set_num_threads(threads)
        self.model = HRNet(_Cfg(WASB_CFG))
        state = torch.load(ensure_weights(), map_location="cpu", weights_only=False)["model_state_dict"]
        self.model.load_state_dict(state)
        self.model.eval()
        self.threshold = threshold

    @staticmethod
    def prepare(frame_bgr: np.ndarray) -> np.ndarray:
        img = cv2.resize(frame_bgr, (IN_W, IN_H), interpolation=cv2.INTER_AREA)
        img = (img[:, :, ::-1].astype(np.float32) / 255.0 - MEAN) / STD
        return img.transpose(2, 0, 1)

    def detect(self, triplets: list[list[np.ndarray]], sizes: tuple[int, int]) -> list[list[list[tuple[float, float, float]]]]:
        """triplets: batch of [3 prepared frames]. Returns, per triplet and per frame, [(x, y, score)] in source pixels."""
        torch = self.torch
        batch = torch.from_numpy(np.stack([np.concatenate(t, axis=0) for t in triplets]))
        with torch.inference_mode():
            heat = self.model(batch)[0].sigmoid().numpy()
        sx, sy = sizes[0] / IN_W, sizes[1] / IN_H
        out = []
        for hm3 in heat:
            per_frame = []
            for hm in hm3:
                cands = []
                if hm.max() > self.threshold:
                    n, labels = cv2.connectedComponents((hm > self.threshold).astype(np.uint8))
                    for m in range(1, n):
                        ys, xs = np.where(labels == m)
                        w = hm[ys, xs]
                        cands.append((float((xs * w).sum() / w.sum() * sx), float((ys * w).sum() / w.sum() * sy), float(w.sum())))
                per_frame.append(sorted(cands, key=lambda c: -c[2]))
            out.append(per_frame)
        return out


def _drop_stationary(cands, radius: float, window: int = 20, min_hits: int = 8):
    """Remove detections that keep showing up at one spot (lights, marks, a ball lying on the court)."""
    out = []
    for i, frame in enumerate(cands):
        kept = []
        for c in frame:
            frames_hit = [j for j in range(max(0, i - window), min(len(cands), i + window + 1))
                          if j != i and any(np.hypot(c[0] - o[0], c[1] - o[1]) < radius for o in cands[j])]
            if len(frames_hit) >= min_hits and max(frames_hit) - min(frames_hit) >= 12:
                continue
            kept.append(c)
        out.append(kept)
    return out


def link_track(cands: list[list[tuple[float, float, float]]], max_jump: float) -> np.ndarray:
    """Chain detections into flight segments by motion consistency, then keep the best segment at each moment.

    Returns (N, 2) with NaN where the ball is not seen.
    """
    n = len(cands)
    cands = _drop_stationary(cands, radius=max(2.0, 0.022 * max_jump))
    open_tracks: list[dict] = []
    done: list[dict] = []
    for i in range(n):
        free = list(cands[i])
        for tr in sorted(open_tracks, key=lambda t: -len(t["frames"])):
            gap = i - tr["frames"][-1]
            last = tr["pts"][-1]
            if len(tr["pts"]) >= 2:
                span = tr["frames"][-1] - tr["frames"][-2]
                vel = (tr["pts"][-1] - tr["pts"][-2]) / span
                pred = last + vel * gap
                tol = max(0.12 * max_jump, 0.6 * np.linalg.norm(vel)) * gap ** 0.5 + 0.06 * max_jump
            else:
                pred, tol = last, max_jump * gap
            best, best_d = None, tol
            for c in free:
                d = np.hypot(c[0] - pred[0], c[1] - pred[1])
                if d < best_d and np.hypot(c[0] - last[0], c[1] - last[1]) < max_jump * gap:
                    best, best_d = c, d
            if best is not None:
                free.remove(best)
                tr["frames"].append(i)
                tr["pts"].append(np.array(best[:2]))
                tr["score"] += best[2]
        for c in free:
            open_tracks.append(dict(frames=[i], pts=[np.array(c[:2])], score=c[2]))
        still_open = []
        for tr in open_tracks:
            (done if i - tr["frames"][-1] >= 4 else still_open).append(tr)
        open_tracks = still_open
    done.extend(open_tracks)
    good = []
    for tr in done:
        extent = np.ptp(np.array(tr["pts"]), axis=0).max()      # a real flight covers ground; a false spot does not
        if len(tr["frames"]) >= 4 and extent > 0.15 * max_jump:
            good.append(tr)
    track = np.full((n, 2), np.nan)
    owner = np.full(n, -1)
    for k, tr in sorted(enumerate(good), key=lambda kv: -len(kv[1]["frames"]) * (1 + kv[1]["score"] / max(len(kv[1]["frames"]), 1))):
        lo, hi = tr["frames"][0], tr["frames"][-1]
        if (owner[lo:hi + 1] >= 0).mean() > 0.3:
            continue                                  # a stronger segment already covers this time
        for f, p in zip(tr["frames"], tr["pts"]):
            if owner[f] < 0:
                track[f], owner[f] = p, k
    return track


def clean_track(track: np.ndarray, max_jump: float, max_gap: int = 6) -> np.ndarray:
    """Bridge short gaps where the two ends agree with one continuous flight."""
    out = track.copy()
    idx = np.where(~np.isnan(out[:, 0]))[0]
    for a, b in zip(idx[:-1], idx[1:]):
        if 1 < b - a <= max_gap + 1 and np.hypot(*(out[b] - out[a])) < 0.6 * max_jump * (b - a):
            for k in range(a + 1, b):
                f = (k - a) / (b - a)
                out[k] = out[a] * (1 - f) + out[b] * f
    return out


def detect_candidates(frames, size: tuple[int, int], batch: int = 4, progress=None, total: int | None = None,
                      detector: BallDetector | None = None) -> list[list[tuple[float, float, float]]]:
    """frames: iterable of BGR frames at the analysis frame rate. Returns ball candidates [(x, y, score)] per frame."""
    det = detector or BallDetector()
    cands: list[list[tuple[float, float, float]]] = []
    buf: list[np.ndarray] = []
    pending: list[list[np.ndarray]] = []

    def flush():
        if pending:
            for per_frame in det.detect(pending, size):
                cands.extend(per_frame)
            pending.clear()

    for frame in frames:
        buf.append(det.prepare(frame))
        if len(buf) == 3:
            pending.append(buf)
            buf = []
            if len(pending) == batch:
                flush()
                if progress and total:
                    progress(min(1.0, len(cands) / total))
    flush()
    if buf:                                         # tail of 1-2 frames: pad by repeating the last frame
        k = len(buf)
        while len(buf) < 3:
            buf.append(buf[-1])
        cands.extend(det.detect([buf], size)[0][:k])
    return cands


def build_track(cands: list[list[tuple[float, float, float]]], size: tuple[int, int]) -> np.ndarray:
    max_jump = 0.09 * max(size)
    return clean_track(link_track(cands, max_jump), max_jump)


def track_ball(frames, size: tuple[int, int], **kwargs) -> np.ndarray:
    return build_track(detect_candidates(frames, size, **kwargs), size)
