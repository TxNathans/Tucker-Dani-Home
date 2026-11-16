"""Ball tracking with WASB (HRNet heatmap model, MIT licence, tennis weights from the authors)."""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

MODEL_DIR = Path(__file__).resolve().parents[2] / "models"
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


def link_track(candidates: list[list[tuple[float, float, float]]], max_jump: float) -> np.ndarray:
    """Pick one candidate per frame by motion consistency. Returns (N, 2) with NaN where the ball is not seen."""
    n = len(candidates)
    track = np.full((n, 2), np.nan)
    last, velocity, gap = None, np.zeros(2), 0
    for i, cands in enumerate(candidates):
        if not cands:
            gap += 1
            if gap > 8:
                last = None
            continue
        if last is None:
            choice = cands[0]
        else:
            pred = last + velocity * (gap + 1)
            reach = max_jump * (gap + 1)
            near = [c for c in cands if np.hypot(c[0] - pred[0], c[1] - pred[1]) < reach]
            if not near:
                gap += 1
                if gap > 8:
                    last = None
                continue
            choice = min(near, key=lambda c: np.hypot(c[0] - pred[0], c[1] - pred[1]) - 0.5 * c[2])
        pos = np.array(choice[:2])
        if last is not None:
            velocity = (pos - last) / (gap + 1)
        last, gap = pos, 0
        track[i] = pos
    return track


def clean_track(track: np.ndarray, max_jump: float, max_gap: int = 6, min_run: int = 5) -> np.ndarray:
    """Remove things that are not a ball in flight (stationary spots, scattered blips), then bridge short gaps."""
    out = track.copy()
    n = len(out)
    # 1. a ball in play is never still: drop points that sit in one place for several frames
    still_px = max(1.5, 0.0025 * max_jump / 0.09)
    i = 0
    while i < n:
        if np.isnan(out[i, 0]):
            i += 1
            continue
        j = i + 1
        while j < n and not np.isnan(out[j, 0]) and np.hypot(*(out[j] - out[i])) < still_px * max(1, (j - i)) ** 0.5 * 1.5:
            j += 1
        if j - i >= 4:
            out[i:j] = np.nan
        i = j if j > i + 1 else i + 1
    # 2. split into runs of consistent motion and drop the short ones
    seen = np.where(~np.isnan(out[:, 0]))[0]
    runs, cur = [], []
    for k in seen:
        if cur and (k - cur[-1] > 3 or np.hypot(*(out[k] - out[cur[-1]])) > max_jump * (k - cur[-1])):
            runs.append(cur)
            cur = []
        cur.append(k)
    if cur:
        runs.append(cur)
    for run in runs:
        travel = np.hypot(*(out[run[-1]] - out[run[0]])) if len(run) > 1 else 0.0
        if len(run) < min_run or travel < 4 * still_px:
            out[run] = np.nan
    # 3. bridge short gaps where the two ends agree with one continuous flight
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
