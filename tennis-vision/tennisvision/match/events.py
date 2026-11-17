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
    unsure_player: bool = False  # two players were within reach of the ball


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


def _overlap(a: np.ndarray, b: np.ndarray) -> float:
    if np.isnan(a[0]) or np.isnan(b[0]):
        return 0.0
    x0, y0, x1, y1 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, x1 - x0) * max(0.0, y1 - y0)
    return inter / min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))


def _racket_holder(ball, rackets: dict[int, np.ndarray], frame: int, player_boxes: np.ndarray, among: list[int]) -> int | None:
    """Of the players in reach, the one whose body is closest to the racket that is at the ball."""
    best_racket, best_d = None, None
    for f in range(frame - 2, frame + 3):
        for r in rackets.get(f, []):
            centre = np.array([(r[0] + r[2]) / 2, (r[1] + r[3]) / 2])
            d = np.hypot(*(centre - ball)) / max(np.hypot(r[2] - r[0], r[3] - r[1]), 1.0)
            if d < 1.5 and (best_d is None or d < best_d):
                best_racket, best_d = (centre, f), d
    if best_racket is None:
        return None
    centre, f = best_racket
    gaps = []
    for p in among:
        b = player_boxes[p, min(f, player_boxes.shape[1] - 1)]
        if np.isnan(b[0]):
            gaps.append(np.inf)
            continue
        dx = max(b[0] - centre[0], 0, centre[0] - b[2])
        dy = max(b[1] - centre[1], 0, centre[1] - b[3])
        gaps.append(np.hypot(dx, dy) / max(b[3] - b[1], 1.0))
    order = np.argsort(gaps)
    if len(order) > 1 and gaps[order[1]] - gaps[order[0]] < 0.05:
        return None                              # both bodies are equally close to the racket
    return among[int(order[0])]


def detect_events(track: np.ndarray, times: np.ndarray, player_boxes: np.ndarray, frame_size: tuple[int, int],
                  sounds: list[tuple[float, float]] | None = None, court=None, min_gap_s: float = 0.2,
                  rackets: dict[int, np.ndarray] | None = None) -> list[Event]:
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
        in_reach = [p for p, d in enumerate(dists) if d < 0.15]
        unsure = False
        if len(in_reach) > 1:
            holder = _racket_holder(ball, rackets, i, player_boxes, in_reach) if rackets is not None else None
            if holder is not None:
                nearest = holder
            unsure = holder is None or _overlap(player_boxes[in_reach[0], i], player_boxes[in_reach[1], i]) > 0.1
        heard = bool(len(sound_times)) and bool(np.any(np.abs(sound_times - times[i]) < 0.12))
        before = _fit_velocity(track, np.arange(max(0, i - 4), i + 1))
        after = _fit_velocity(track, np.arange(i, min(n, i + 5)))
        if before is None or after is None:
            continue
        reverses = float(np.dot(before, after)) < 0
        upward_kick = dv[i, 1] < -0.4 * threshold
        if near_player and reverses:
            kind = "hit"
        elif upward_kick and size[i] <= 12 * threshold:
            kind = "bounce"                 # larger jumps than this are tracking glitches, not bounces
        else:
            continue
        ev = Event(kind, i, float(times[i]), (float(ball[0]), float(ball[1])), nearest if kind == "hit" else None,
                   float(size[i] / threshold), heard=heard, unsure_player=unsure and kind == "hit")
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
