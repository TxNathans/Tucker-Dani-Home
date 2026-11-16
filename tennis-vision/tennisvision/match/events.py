"""Find hits and bounces in a ball track.

Gravity bends the ball's path smoothly; a racket or the court changes its velocity abruptly. Those abrupt changes
are the events. One next to a player is a hit; one away from the players with an upward kick is a bounce.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class Event:
    kind: str                    # hit | bounce
    frame: int
    t: float
    xy: tuple[float, float]      # ball position in the image
    player: int | None = None    # index into the tracked players, for hits
    strength: float = 0.0
    court_xy: tuple[float, float] | None = None
    heard: bool = False          # an impact sound lines up with it


def _fit_velocity(track: np.ndarray, idx: np.ndarray) -> np.ndarray | None:
    ok = idx[~np.isnan(track[idx, 0])]
    if len(ok) < 3 or ok[-1] - ok[0] < 2:
        return None
    A = np.column_stack([ok, np.ones(len(ok))])
    return np.linalg.lstsq(A, track[ok], rcond=None)[0][0]


def kinks(track: np.ndarray, k: int = 4) -> tuple[np.ndarray, np.ndarray]:
    """Per frame: velocity change vector (px/frame) between the k frames before and after, and its size."""
    n = len(track)
    dv = np.zeros((n, 2))
    for i in range(n):
        if np.isnan(track[i, 0]):
            continue
        before = _fit_velocity(track, np.arange(max(0, i - k), i + 1))
        after = _fit_velocity(track, np.arange(i, min(n, i + k + 1)))
        if before is not None and after is not None:
            dv[i] = after - before
    return dv, np.linalg.norm(dv, axis=1)


def reach_distance(ball: np.ndarray, box: np.ndarray) -> float:
    """Distance from the ball to a player's box grown by racket reach, in units of the player's height (0 = inside)."""
    if np.isnan(box[0]):
        return np.inf
    w, h = box[2] - box[0], box[3] - box[1]
    grow_x, grow_up = 0.55 * h, 0.35 * h
    x0, x1, y0, y1 = box[0] - grow_x, box[2] + grow_x, box[1] - grow_up, box[3] + 0.05 * h
    dx = max(x0 - ball[0], 0, ball[0] - x1)
    dy = max(y0 - ball[1], 0, ball[1] - y1)
    return float(np.hypot(dx, dy) / max(h, 1.0))


def detect_events(track: np.ndarray, times: np.ndarray, player_boxes: np.ndarray, frame_size: tuple[int, int],
                  sounds: list[tuple[float, float]] | None = None, court=None, min_gap_s: float = 0.2) -> list[Event]:
    """track (N,2) px with NaN gaps; player_boxes (P,N,4). Returns time-ordered hits and bounces."""
    n = len(track)
    fps = 1.0 / np.median(np.diff(times)) if n > 1 else 30.0
    scale = max(frame_size)
    dv, size = kinks(track)
    threshold = 0.0045 * scale * (30.0 / fps)
    sound_times = np.array([s for s, _ in (sounds or [])])
    candidates = []
    for i in range(1, n - 1):
        if size[i] < threshold:
            continue
        lo, hi = max(0, i - 3), min(n, i + 4)
        if size[i] < size[lo:hi].max():
            continue
        candidates.append(i)
    # a hit hidden behind the player's body shows up as a gap with opposite travel either side
    seen = ~np.isnan(track[:, 0])
    idx = np.where(seen)[0]
    for a, b in zip(idx[:-1], idx[1:]):
        if 3 <= b - a <= int(1.0 * fps):
            before = _fit_velocity(track, np.arange(max(0, a - 4), a + 1))
            after = _fit_velocity(track, np.arange(b, min(n, b + 5)))
            if before is not None and after is not None and np.dot(before, after) < 0:
                candidates.append(a)
    events: list[Event] = []
    for i in sorted(set(candidates)):
        ball = track[i]
        dists = [reach_distance(ball, player_boxes[p, i]) for p in range(len(player_boxes))]
        nearest = int(np.argmin(dists)) if dists else None
        near_player = nearest is not None and dists[nearest] < 0.15
        heard = bool(len(sound_times)) and bool(np.any(np.abs(sound_times - times[i]) < 0.12))
        before = _fit_velocity(track, np.arange(max(0, i - 4), i + 1))
        after = _fit_velocity(track, np.arange(i, min(n, i + 5)))
        if before is None or after is None:
            continue
        reverses = float(np.dot(before, after)) < 0
        upward_kick = dv[i, 1] < -0.4 * threshold
        if near_player and reverses:
            kind = "hit"
        elif upward_kick and not reverses:
            kind = "bounce"
        else:
            continue
        ev = Event(kind, i, float(times[i]), (float(ball[0]), float(ball[1])), nearest if kind == "hit" else None,
                   float(size[i] / threshold), heard=heard)
        if kind == "bounce" and court is not None:
            cx, cy = court.to_court([ball])[0]
            ev.court_xy = (float(cx), float(cy))
        events.append(ev)
    # keep the strongest event when two fall almost together; two hits by one player need a real gap
    events.sort(key=lambda e: e.frame)
    kept: list[Event] = []
    for ev in events:
        if kept and ev.t - kept[-1].t < min_gap_s:
            if ev.kind == "hit" and kept[-1].kind != "hit" or (ev.kind == kept[-1].kind and ev.strength > kept[-1].strength):
                kept[-1] = ev
            continue
        if ev.kind == "hit":
            prev_hit = next((e for e in reversed(kept) if e.kind == "hit"), None)
            if prev_hit and prev_hit.player == ev.player and ev.t - prev_hit.t < 0.6:
                continue
        kept.append(ev)
    return kept
