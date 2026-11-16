"""Player detection (YOLOX, Apache-2.0), tracking, and identity by clothing colour."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np
from scipy.optimize import linear_sum_assignment

MODEL_DIR = Path(__file__).resolve().parents[2] / "models"
YOLOX_URL = "https://github.com/Megvii-BaseDetection/YOLOX/releases/download/0.1.1rc0/yolox_{v}.onnx"
PERSON, RACKET = 0, 38
INPUT = 640


class Detector:
    def __init__(self, variant: str = "s", threads: int = 4):
        import onnxruntime as ort
        path = MODEL_DIR / f"yolox_{variant}.onnx"
        if not path.exists():
            import urllib.request
            MODEL_DIR.mkdir(parents=True, exist_ok=True)
            urllib.request.urlretrieve(YOLOX_URL.format(v=variant), path)
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = threads
        self.session = ort.InferenceSession(str(path), opts, providers=["CPUExecutionProvider"])
        self.name = self.session.get_inputs()[0].name
        grids, strides = [], []
        for s in (8, 16, 32):
            n = INPUT // s
            xv, yv = np.meshgrid(np.arange(n), np.arange(n))
            grids.append(np.stack((xv, yv), 2).reshape(-1, 2))
            strides.append(np.full((n * n, 1), s))
        self.grid, self.stride = np.concatenate(grids), np.concatenate(strides)

    def _run(self, img: np.ndarray, classes: tuple[int, ...], conf: float) -> np.ndarray:
        h, w = img.shape[:2]
        r = min(INPUT / h, INPUT / w)
        canvas = np.full((INPUT, INPUT, 3), 114, np.uint8)
        resized = cv2.resize(img, (int(w * r), int(h * r)), interpolation=cv2.INTER_LINEAR)
        canvas[: resized.shape[0], : resized.shape[1]] = resized
        blob = canvas.transpose(2, 0, 1)[None].astype(np.float32)
        out = self.session.run(None, {self.name: blob})[0][0]
        xy = (out[:, :2] + self.grid) * self.stride
        wh = np.exp(out[:, 2:4]) * self.stride
        rows = []
        for c in classes:
            score = out[:, 4] * out[:, 5 + c]
            keep = score > conf
            if keep.any():
                boxes = np.concatenate([xy[keep] - wh[keep] / 2, xy[keep] + wh[keep] / 2], 1) / r
                rows.append(np.column_stack([boxes, score[keep], np.full(keep.sum(), c)]))
        return np.concatenate(rows) if rows else np.zeros((0, 6))

    def detect(self, frame: np.ndarray, classes=(PERSON, RACKET), conf: float = 0.35, tiles: bool = True) -> np.ndarray:
        """Rows of [x0, y0, x1, y1, score, class]. Tiling keeps small far-court players detectable."""
        h, w = frame.shape[:2]
        dets = [self._run(frame, classes, conf)]
        if tiles and max(h, w) > 900:
            tw, th = int(w * 0.6), int(h * 0.6)
            for x0 in (0, w - tw):
                for y0 in (0, h - th):
                    d = self._run(frame[y0:y0 + th, x0:x0 + tw], classes, conf)
                    if len(d):
                        d[:, [0, 2]] += x0
                        d[:, [1, 3]] += y0
                        edge = (d[:, 0] < x0 + 3) & (x0 > 0) | (d[:, 2] > x0 + tw - 3) & (x0 + tw < w) \
                            | (d[:, 1] < y0 + 3) & (y0 > 0) | (d[:, 3] > y0 + th - 3) & (y0 + th < h)
                        dets.append(d[~edge])
        d = np.concatenate(dets)
        keep = []
        for c in classes:
            idx = np.where(d[:, 5] == c)[0]
            if len(idx):
                boxes = np.column_stack([d[idx, 0], d[idx, 1], d[idx, 2] - d[idx, 0], d[idx, 3] - d[idx, 1]])
                picked = cv2.dnn.NMSBoxes(boxes.tolist(), d[idx, 4].tolist(), conf, 0.5)
                keep.extend(idx[np.array(picked).reshape(-1)].tolist())
        return d[keep]


def appearance(frame: np.ndarray, box: np.ndarray) -> np.ndarray:
    """Clothing descriptor: colour histograms of the torso and of the hips/legs."""
    x0, y0, x1, y1 = box[:4]
    w, h = x1 - x0, y1 - y0
    feats = []
    for top, bottom in ((0.18, 0.48), (0.48, 0.78)):
        xa, xb = int(x0 + 0.25 * w), int(x1 - 0.25 * w)
        ya, yb = int(y0 + top * h), int(y0 + bottom * h)
        patch = frame[max(ya, 0):max(yb, ya + 1), max(xa, 0):max(xb, xa + 1)]
        if patch.size == 0:
            feats.append(np.zeros(40, np.float32))
            continue
        hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)
        hs = cv2.calcHist([hsv], [0, 1], None, [8, 4], [0, 180, 0, 256]).flatten()
        v = cv2.calcHist([hsv], [2], None, [8], [0, 256]).flatten()
        f = np.concatenate([hs, v * 1.5])
        feats.append(f / (f.sum() + 1e-6))
    return np.concatenate(feats).astype(np.float32)


def appearance_distance(a: np.ndarray, b: np.ndarray) -> float:
    return float(1.0 - np.sum(np.sqrt(a * b)) / 2.0)     # Bhattacharyya over the two body regions


def iou(a: np.ndarray, b: np.ndarray) -> float:
    x0, y0, x1, y1 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, x1 - x0) * max(0.0, y1 - y0)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


@dataclass
class Track:
    id: int
    feat: np.ndarray
    boxes: dict[int, np.ndarray] = field(default_factory=dict)
    last: int = -1

    @property
    def box(self) -> np.ndarray:
        return self.boxes[self.last]

    def add(self, frame_idx: int, box: np.ndarray, feat: np.ndarray) -> None:
        self.boxes[frame_idx] = box[:4].copy()
        self.last = frame_idx
        self.feat = 0.9 * self.feat + 0.1 * feat

    def weight(self) -> float:
        areas = [(b[2] - b[0]) * (b[3] - b[1]) for b in self.boxes.values()]
        return len(self.boxes) * float(np.sqrt(np.mean(areas)))


class PlayerTracker:
    """Frame-to-frame association on overlap, position and clothing; lost players are re-found by clothing."""

    def __init__(self, max_lost: int = 45):
        self.tracks: list[Track] = []
        self.max_lost = max_lost
        self._next = 1

    def update(self, frame_idx: int, frame: np.ndarray, people: np.ndarray) -> None:
        feats = [appearance(frame, p) for p in people]
        live = [t for t in self.tracks if frame_idx - t.last <= self.max_lost]
        if live and len(people):
            cost = np.zeros((len(live), len(people)))
            for i, t in enumerate(live):
                tb = t.box
                th = tb[3] - tb[1]
                for j, p in enumerate(people):
                    gap = frame_idx - t.last
                    centre = np.hypot((tb[0] + tb[2] - p[0] - p[2]) / 2, (tb[1] + tb[3] - p[1] - p[3]) / 2) / max(th, 1.0)
                    look = appearance_distance(t.feat, feats[j])
                    size = abs(np.log((p[3] - p[1]) / max(th, 1.0)))
                    c = 0.35 * (1 - iou(tb, p)) + 0.25 * min(centre / (1 + 0.15 * gap), 2.0) + 1.4 * look + 0.2 * size
                    if (centre > 1.2 + 0.25 * gap and look > 0.18) or look > 0.45 or size > 0.7:
                        c = 1e3
                    cost[i, j] = c
            rows, cols = linear_sum_assignment(cost)
            used = set()
            for i, j in zip(rows, cols):
                if cost[i, j] < 1e3:
                    live[i].add(frame_idx, people[j], feats[j])
                    used.add(j)
        else:
            used = set()
        for j, p in enumerate(people):
            if j not in used:
                t = Track(self._next, feats[j].copy())
                t.add(frame_idx, p, feats[j])
                self.tracks.append(t)
                self._next += 1

    def finish(self, max_players: int, min_frames: int = 8) -> list[Track]:
        """Merge fragments of the same person (same clothing, never on screen together) and keep the main players."""
        tracks = sorted((t for t in self.tracks if len(t.boxes) >= min_frames), key=lambda t: -t.weight())
        merged: list[Track] = []
        for t in tracks:
            target = None
            best = 0.16
            for m in merged:
                if set(m.boxes) & set(t.boxes):
                    continue
                d = appearance_distance(m.feat, t.feat)
                if d < best:
                    best, target = d, m
            if target is None:
                merged.append(t)
            else:
                target.boxes.update(t.boxes)
                target.last = max(target.last, t.last)
        merged.sort(key=lambda t: -t.weight())
        return merged[:max_players]


def boxes_array(track: Track, n_frames: int, max_gap: int = 20) -> np.ndarray:
    """(N, 4) boxes with short gaps filled; NaN where the player is out of view."""
    out = np.full((n_frames, 4), np.nan)
    idx = sorted(k for k in track.boxes if k < n_frames)
    for k in idx:
        out[k] = track.boxes[k]
    for a, b in zip(idx[:-1], idx[1:]):
        if 1 < b - a <= max_gap:
            for k in range(a + 1, b):
                f = (k - a) / (b - a)
                out[k] = out[a] * (1 - f) + out[b] * f
    return out
