"""Overlay video for match mode: players, ball trail, rackets, events, court lines and a top-down mini court."""
from __future__ import annotations

import cv2
import numpy as np

from ..stats.schema import DOUBLES_HALF_WIDTH as DW, HALF_LENGTH as L
from ..video import VideoWriter, iter_frames
from .court import LINES

PLAYER_BGR = [(0, 176, 255), (255, 160, 58), (164, 227, 80), (255, 100, 210)]


def _label(img, text, org, color, scale=0.55):
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, 2)
    x, y = int(org[0]), int(max(org[1], th + 8))
    cv2.rectangle(img, (x, y - th - 8), (x + tw + 8, y), color, -1)
    cv2.putText(img, text, (x + 4, y - 5), cv2.FONT_HERSHEY_SIMPLEX, scale, (20, 20, 20), 2, cv2.LINE_AA)


def _mini_court(height: int) -> tuple[np.ndarray, callable]:
    """Blank top-down court image and a function mapping court metres to its pixels (far end at the top)."""
    pad = 2.5
    scale = height / (2 * L + 2 * pad)
    width = int((2 * DW + 2 * pad) * scale)
    img = np.full((height, width, 3), (60, 90, 60), np.uint8)
    to_px = lambda p: (int((p[0] + DW + pad) * scale), int((L + pad - p[1]) * scale))
    for a, b in LINES.values():
        cv2.line(img, to_px(a), to_px(b), (235, 235, 235), 1, cv2.LINE_AA)
    cv2.line(img, to_px((-DW - 0.9, 0)), to_px((DW + 0.9, 0)), (30, 30, 30), 2, cv2.LINE_AA)
    return img, to_px


def render_match(video_path: str, out_path: str, info, stride: int, size: tuple[int, int], times: np.ndarray, players,
                 boxes: np.ndarray, track: np.ndarray, events, court, hit_info: list[dict], feet_court, rackets=None,
                 out_side: int = 960, progress=None) -> None:
    w, h = size
    s = min(1.0, out_side / max(w, h))
    ow, oh = int(w * s) // 2 * 2, int(h * s) // 2 * 2
    n = len(times)
    fps = info.fps / stride
    hold = int(fps * 1.0)
    by_frame: dict[int, list] = {}
    for e in events:
        by_frame.setdefault(e.frame, []).append(e)
    hit_by_frame = {hi["frame"]: hi for hi in hit_info}
    names = [p.name for p in players]
    ids = [p.id for p in players]
    mini_base, to_px = _mini_court(int(oh * 0.42)) if court is not None else (None, None)
    bounce_marks: list[tuple[tuple[int, int], bool]] = []
    recent: list[tuple[int, str, tuple]] = []
    k = 0
    with VideoWriter(out_path, ow, oh, fps, crf=23) as writer:
        for i, _, frame in iter_frames(video_path, info, max_side=max(w, h)):
            if i % stride:
                continue
            if k >= n:
                break
            img = cv2.resize(frame, (ow, oh), interpolation=cv2.INTER_AREA) if s < 1.0 else frame.copy()
            if court is not None:
                court.scaled((ow, oh)).draw(img, (0, 230, 255), 1)
            if rackets is not None:
                for r in rackets.get(k - k % 2, []):
                    cv2.rectangle(img, (int(r[0] * s), int(r[1] * s)), (int(r[2] * s), int(r[3] * s)), (60, 60, 255), 1, cv2.LINE_AA)
            for p in range(len(players)):
                b = boxes[p, k]
                if np.isnan(b[0]):
                    continue
                c = PLAYER_BGR[p % 4]
                cv2.rectangle(img, (int(b[0] * s), int(b[1] * s)), (int(b[2] * s), int(b[3] * s)), c, 2, cv2.LINE_AA)
                _label(img, names[p], (b[0] * s, b[1] * s - 2), c)
            for j in range(max(1, k - 14), k + 1):
                if not np.isnan(track[j, 0]) and not np.isnan(track[j - 1, 0]):
                    a = (j - (k - 14)) / 14
                    cv2.line(img, (int(track[j - 1, 0] * s), int(track[j - 1, 1] * s)), (int(track[j, 0] * s), int(track[j, 1] * s)),
                             (int(80 * a), int(255 * a), int(255 * a)), 2, cv2.LINE_AA)
            if not np.isnan(track[k, 0]):
                cv2.circle(img, (int(track[k, 0] * s), int(track[k, 1] * s)), 5, (0, 255, 255), 2, cv2.LINE_AA)
            for e in by_frame.get(k, []):
                if e.kind == "hit":
                    hi = hit_by_frame.get(e.frame, {})
                    who = names[e.player] if e.player is not None else "?"
                    stroke = hi.get("stroke", "")
                    text = f"{who}: {stroke}" if stroke and stroke != "unknown" else f"{who}: hit"
                    recent.append((k, text + (" ?" if e.unsure_player else ""), (60, 60, 255)))
                else:
                    recent.append((k, "bounce", (0, 220, 255)))
                    if court is not None and e.court_xy is not None:
                        bounce_marks.append((to_px(e.court_xy), True))
                cv2.circle(img, (int(e.xy[0] * s), int(e.xy[1] * s)), 14, (60, 60, 255) if e.kind == "hit" else (0, 220, 255), 2, cv2.LINE_AA)
            recent = [r for r in recent if k - r[0] <= hold]
            for row, (_, text, color) in enumerate(recent[-3:]):
                _label(img, text, (10, 34 + row * 30), color, 0.7)
            if mini_base is not None:
                mini = mini_base.copy()
                for pt, _ in bounce_marks[-40:]:
                    cv2.circle(mini, pt, 3, (0, 220, 255), -1, cv2.LINE_AA)
                for p in range(len(players)):
                    f = feet_court[p][k]
                    if not np.isnan(f[0]):
                        cv2.circle(mini, to_px(f), 5, PLAYER_BGR[p % 4], -1, cv2.LINE_AA)
                mh, mw = mini.shape[:2]
                img[oh - mh - 8:oh - 8, ow - mw - 8:ow - 8] = cv2.addWeighted(img[oh - mh - 8:oh - 8, ow - mw - 8:ow - 8], 0.25, mini, 0.75, 0)
            writer.write(img)
            k += 1
            if progress and k % 30 == 0:
                progress(k / n)
