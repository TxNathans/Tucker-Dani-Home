"""Racket tracking for swing clips: find the racket each frame and estimate where the racket head is."""
from __future__ import annotations

import numpy as np

from ..match.players import RACKET, Detector
from ..video import VideoInfo, iter_frames

HEAD_FROM_GRIP = 1.55    # racket-head centre sits about 1.55x as far from the hand as the middle of the racket does
MAX_GAP_FRAMES = 8


def track_racket(video_path: str, info: VideoInfo, analyzer, crop: tuple[int, int, int, int], progress=None) -> dict:
    """Returns per-frame racket boxes (analysis pixels), the estimated head position, and which frames were seen."""
    seq = analyzer.seq
    n = len(seq.t)
    x0, y0, x1, y1 = crop
    wrist = analyzer.xy[:, analyzer.dom["wr"]]
    reach_px = 1.3 / analyzer.m_per_px
    detector = Detector("s")
    boxes = np.full((n, 4), np.nan)
    for i, _, frame in iter_frames(video_path, info, max_side=max(seq.width, seq.height)):
        if i >= n:
            break
        dets = detector.detect(frame[y0:y1, x0:x1], (RACKET,), conf=0.2, tiles=False)
        best, best_d = None, reach_px
        for d in dets:
            box = d[:4] + (x0, y0, x0, y0)
            # distance from the hand to the nearest point of the box: the hand is on the grip, at the box's edge
            dx = max(box[0] - wrist[i, 0], 0, wrist[i, 0] - box[2])
            dy = max(box[1] - wrist[i, 1], 0, wrist[i, 1] - box[3])
            gap = np.hypot(dx, dy)
            if gap < best_d and gap < 0.25 * reach_px:
                best, best_d = box, gap
        if best is not None:
            boxes[i] = best
        if progress and i % 10 == 0:
            progress(i / max(n, 1))
    # throw out detections that disagree with the ones either side of them (the detector boxed something else)
    offsets = np.column_stack([(boxes[:, 0] + boxes[:, 2]) / 2, (boxes[:, 1] + boxes[:, 3]) / 2]) - wrist
    idx = np.where(~np.isnan(boxes[:, 0]))[0]
    limit = 0.25 / analyzer.m_per_px
    for j in range(1, len(idx) - 1):
        p, i, q = idx[j - 1], idx[j], idx[j + 1]
        if i - p > 12 or q - i > 12:
            continue
        to_prev, to_next = np.linalg.norm(offsets[i] - offsets[p]), np.linalg.norm(offsets[i] - offsets[q])
        if to_prev > limit and to_next > limit and np.linalg.norm(offsets[p] - offsets[q]) < min(to_prev, to_next):
            boxes[i] = np.nan
    seen = ~np.isnan(boxes[:, 0])
    filled = boxes.copy()
    idx = np.where(seen)[0]
    for a, b in zip(idx[:-1], idx[1:]):
        if 1 < b - a <= MAX_GAP_FRAMES:
            for k in range(a + 1, b):
                f = (k - a) / (b - a)
                # carry the racket's offset from the hand across the gap, so the estimate follows the swing
                off = (boxes[a] - np.tile(wrist[a], 2)) * (1 - f) + (boxes[b] - np.tile(wrist[b], 2)) * f
                filled[k] = np.tile(wrist[k], 2) + off
    centre = np.column_stack([(filled[:, 0] + filled[:, 2]) / 2, (filled[:, 1] + filled[:, 3]) / 2])
    head = wrist + HEAD_FROM_GRIP * (centre - wrist)
    return dict(boxes=filled, head=head, seen=seen, valid=~np.isnan(filled[:, 0]))
