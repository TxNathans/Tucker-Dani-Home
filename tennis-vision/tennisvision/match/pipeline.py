"""Match / session video in, tracked play and statistics out.

Two modes, chosen automatically:
- calibrated: the camera is fixed and the four court corners were tapped. Positions are in metres, so landing spots,
  in/out, speeds, scoring, positioning and strategy are all available.
- uncalibrated: handheld or partial view. Players, ball, hits, stroke types and per-shot mocap still work;
  anything that needs court coordinates is left out.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

import cv2
import numpy as np
from scipy.signal import savgol_filter

from ..pose import PoseSequence, make_landmarker
from ..stats.engine import compute
from ..stats.positioning import positioning, view_from, zone_of
from ..stats.schema import HALF_LENGTH, Match, Player, Rules
from ..stats.strategy import recommendations
from ..swing.analyze import SwingAnalyzer, impact_sounds
from ..swing.render import draw_skeleton
from ..video import iter_frames, probe, read_audio, scaled_size
from .ball import build_track, detect_candidates
from .court import Court, refine
from .events import detect_events
from .lesson import lesson_breakdown
from .players import PERSON, RACKET, Detector, PlayerTracker, boxes_array
from .rally import Bounce, Hit, build_points, build_shots, shot_summary, split_rallies
from .render import render_match

ANALYSIS_SIDE = 1280
COLORS = ["#ffb000", "#3aa0ff", "#50e3a4", "#d264ff"]
MOCAP_MIN_BOX_PX = 110        # player height in source pixels below which pose is not attempted
MOCAP_KEYS = ("hand_speed_peak", "swing_path", "elbow_contact", "contact_height", "knee_bend_dom", "shoulder_turn",
              "separation", "contact_in_front", "trunk_lean", "head_stability", "finish_height")


def _first_frame(video_path, info):
    for _, _, frame in iter_frames(video_path, info, max_side=ANALYSIS_SIDE):
        return frame.copy()
    raise ValueError("The video has no frames.")


def _camera_shift(ref_gray: np.ndarray, frame: np.ndarray) -> float:
    cur = cv2.cvtColor(cv2.resize(frame, (480, 270)), cv2.COLOR_BGR2GRAY).astype(np.float32)
    (dx, dy), _ = cv2.phaseCorrelate(ref_gray, cur, cv2.createHanningWindow((480, 270), cv2.CV_32F))
    return float(np.hypot(dx, dy))


def _on_court(people: np.ndarray, court: Court) -> np.ndarray:
    """Keep detections whose feet are on or just around the court."""
    if not len(people):
        return people
    feet = np.column_stack([(people[:, 0] + people[:, 2]) / 2, people[:, 3]])
    xy = court.to_court(feet)
    keep = (np.abs(xy[:, 0]) < 5.485 + 3.5) & (np.abs(xy[:, 1]) < HALF_LENGTH + 6.0)
    return people[keep]


def _feet_court(boxes: np.ndarray, court: Court, fps: float) -> np.ndarray:
    """(N, 2) smoothed court positions of one player's feet; NaN where not seen."""
    out = np.full((len(boxes), 2), np.nan)
    ok = ~np.isnan(boxes[:, 0])
    if ok.sum() < 3:
        return out
    feet = np.column_stack([(boxes[ok, 0] + boxes[ok, 2]) / 2, boxes[ok, 3]])
    xy = court.to_court(feet)
    win = max(5, int(fps * 0.35) | 1)
    if ok.sum() > win:
        xy = savgol_filter(xy, win, 2, axis=0)
    out[ok] = xy
    return out


def _movement(pos: np.ndarray, times: np.ndarray) -> dict:
    ok = ~np.isnan(pos[:, 0])
    if ok.sum() < 5:
        return dict(distance_m=0.0, avg_speed_kmh=None, max_speed_kmh=None, positions=[], zones={})
    p, t = pos[ok], times[ok]
    step = np.linalg.norm(np.diff(p, axis=0), axis=1)
    dt = np.diff(t)
    moving = (dt < 0.5) & (step / np.maximum(dt, 1e-3) < 12.0)       # drop teleports from identity gaps
    speed = step[moving] / np.maximum(dt[moving], 1e-3)
    zones: dict[str, int] = {}
    for q in p[:: max(1, len(p) // 400)]:
        z = zone_of(view_from((q[0], q[1]), (q[0], q[1])))
        zones[z] = zones.get(z, 0) + 1
    total = sum(zones.values())
    sample = p[:: max(1, len(p) // 300)]
    return dict(
        distance_m=round(float(step[moving].sum()), 1),
        avg_speed_kmh=round(float(speed.mean() * 3.6), 1) if len(speed) else None,
        max_speed_kmh=round(float(np.percentile(speed, 99) * 3.6), 1) if len(speed) else None,
        positions=[[round(float(a), 2), round(float(b), 2)] for a, b in sample],
        zones={k: round(100 * v / total, 1) for k, v in zones.items()},
    )


def _lateral_stroke(ball_xy, box, feet_court, court: Court, hand: str) -> str:
    """Forehand or backhand from which side of the body the ball is on, using the court to know which way they face."""
    centre = np.array([(box[0] + box[2]) / 2, (box[1] + box[3]) / 2])
    base = court.to_image([feet_court])[0]
    ex = court.to_image([(feet_court[0] + 1.0, feet_court[1])])[0] - base
    ex /= np.linalg.norm(ex) + 1e-9
    lateral = float(np.dot(np.asarray(ball_xy) - centre, ex))
    facing = 1.0 if feet_court[1] < 0 else -1.0
    dominant = 1.0 if hand == "right" else -1.0
    return "forehand" if lateral * facing * dominant > 0 else "backhand"


def shot_mocap(video_path: str, info, t_hit: float, boxes_src: np.ndarray, hand: str, height_m: float,
               landmarker, mp, clock: list[int], keyframe_path: str | None = None) -> dict | None:
    """Pose-track the hitter through one shot and measure the swing. boxes_src: the player's boxes (source pixels) over the window."""
    boxes_src = boxes_src[~np.isnan(boxes_src[:, 0])]
    if not len(boxes_src):
        return None
    x0, y0 = boxes_src[:, 0].min(), boxes_src[:, 1].min()
    x1, y1 = boxes_src[:, 2].max(), boxes_src[:, 3].max()
    w, h = x1 - x0, y1 - y0
    x0, x1 = int(max(0, x0 - 0.45 * h)), int(min(info.width, x1 + 0.45 * h))
    y0, y1 = int(max(0, y0 - 0.35 * h)), int(min(info.height, y1 + 0.12 * h))
    if x1 - x0 < 20 or y1 - y0 < 20:
        return None
    scale = max(1.0, 512.0 / (y1 - y0))
    start, end = max(0.0, t_hit - 1.0), t_hit + 0.7
    ts, xy, vis, world, det, crops = [], [], [], [], [], []
    for _, t, frame in iter_frames(video_path, info, start=start, end=end):
        crop = frame[y0:y1, x0:x1]
        if scale > 1.0:
            crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        ch, cw = crop.shape[:2]
        clock[0] += 17
        result = landmarker.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(crop[:, :, ::-1])), clock[0])
        ts.append(t)
        if result.pose_landmarks:
            lm = result.pose_landmarks[0]
            xy.append([(p.x * cw, p.y * ch) for p in lm])
            vis.append([p.visibility for p in lm])
            world.append([(p.x, p.y, p.z) for p in result.pose_world_landmarks[0]])
            det.append(True)
        else:
            xy.append(np.zeros((33, 2)))
            vis.append(np.zeros(33))
            world.append(np.zeros((33, 3)))
            det.append(False)
        crops.append(crop if keyframe_path else None)
    clock[0] += 1000
    det = np.array(det)
    if len(ts) < 12 or det.mean() < 0.6:
        return None
    seq = PoseSequence(np.array(ts), np.array(xy, np.float32), np.array(vis, np.float32), np.array(world, np.float32),
                       det, cw, ch, info.fps)
    from ..pose import _interpolate_gaps
    _interpolate_gaps(seq)
    analyzer = SwingAnalyzer(seq, height_m, hand)
    peaks = analyzer.find_swings()
    near = [p for p in peaks if abs(seq.t[p] - t_hit) < 0.3]
    if not near:
        return None
    peak = min(near, key=lambda p: abs(seq.t[p] - t_hit))
    swing = analyzer.analyze_swing(1, peak, 0, len(seq.t) - 1)
    fixes = swing.coaching.get("fixes", [])
    tip = dict(title=fixes[0]["title"], cue=fixes[0]["cue"]) if fixes and fixes[0]["severity"] == "fix" else None
    out = dict(stroke=swing.stroke, two_handed=swing.two_handed, score=swing.coaching.get("overall"), tip=tip,
               metrics={m.key: dict(label=m.label, value=m.value, unit=m.unit, status=m.status, typical=m.typical)
                        for m in swing.metrics if m.key in MOCAP_KEYS})
    if keyframe_path:
        k = swing.frames["contact"]
        img = crops[k].copy()
        draw_skeleton(img, analyzer.xy[k], seq.vis[k], max(2, img.shape[0] // 220))
        cv2.imwrite(keyframe_path, img, [cv2.IMWRITE_JPEG_QUALITY, 85])
        out["keyframe"] = Path(keyframe_path).name
    return out


def analyze_match(video_path: str, out_dir: str, fmt: str = "singles", names: list[str] | None = None,
                  hands: list[str] | None = None, corners: list[list[float]] | None = None, rules: Rules | None = None,
                  mocap: bool = True, height_m: float = 1.70, session: str = "match", progress=None) -> dict:
    """corners: doubles-court corners as fractions of the frame (x, y in 0-1), order far-left, far-right, near-right, near-left."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    report_progress = lambda lo, hi: (lambda f: progress(lo + (hi - lo) * f)) if progress else None
    info = probe(video_path)
    stride = max(1, round(info.fps / 30))
    size = scaled_size(info, ANALYSIS_SIDE)
    w, h = size
    times = np.array(info.pts[::stride])
    n = len(times)
    fps_a = info.fps / stride
    warnings: list[str] = []

    first = _first_frame(video_path, info)
    court = None
    if corners:
        px = [(c[0] * w, c[1] * h) for c in corners]
        court, lines_found = refine(Court.from_corners(px, size), first)
        if lines_found < 4:
            warnings.append("Few court lines were found, so the calibration relies on the tapped corners. Check the yellow lines in the overlay.")

    # ---- pass 1: ball candidates and player detections ---------------------
    detector = Detector("s")
    tracker = PlayerTracker()
    rackets: dict[int, np.ndarray] = {}
    ref_gray = cv2.cvtColor(cv2.resize(first, (480, 270)), cv2.COLOR_BGR2GRAY).astype(np.float32)
    max_shift = [0.0]
    min_person = 0.035 * h

    def stream():
        k = 0
        for i, _, frame in iter_frames(video_path, info, max_side=ANALYSIS_SIDE):
            if i % stride:
                continue
            if k >= n:
                break
            if k % 2 == 0:
                dets = detector.detect(frame, (PERSON, RACKET), tiles=court is not None)
                people = dets[dets[:, 5] == PERSON]
                people = people[(people[:, 3] - people[:, 1]) > min_person]
                if court is not None:
                    people = _on_court(people, court)
                rackets[k] = dets[dets[:, 5] == RACKET][:, :4]
                tracker.update(k, frame, people)
            if k % int(fps_a * 2) == 0 and k:
                max_shift[0] = max(max_shift[0], _camera_shift(ref_gray, frame))
            k += 1
            yield frame

    cands = detect_candidates(stream(), size, progress=report_progress(0.0, 0.7), total=n)
    n = min(n, len(cands))
    times = times[:n]
    static = max_shift[0] < 3.0
    if court is not None and not static:
        warnings.append("The camera moved during the video, so court positions cannot be trusted. Showing the stats that do not need them. Use a tripod or fence mount.")
        court = None
    mode = "calibrated" if court is not None else "uncalibrated"
    if mode == "uncalibrated" and not corners:
        warnings.append("No court corners were marked, so landing spots, in/out, speeds, scoring and positioning are not available for this video.")

    # ---- players -----------------------------------------------------------
    per_side = 2 if fmt == "doubles" else 1
    tracks = tracker.finish(max_players=12)
    chosen = []
    if court is not None:
        sides: dict[int, list] = {0: [], 1: []}
        for tr in tracks:
            b = boxes_array(tr, n)
            feet = _feet_court(b, court, fps_a)
            if np.isnan(feet[:, 0]).all():
                continue
            side = 0 if np.nanmedian(feet[:, 1]) < 0 else 1
            sides[side].append((tr, b, feet))
        for side in (0, 1):
            picked = sorted(sides[side], key=lambda x: -x[0].weight())[:per_side]
            picked.sort(key=lambda x: np.nanmedian(x[2][:20, 0]) if not np.isnan(x[2][:20, 0]).all() else np.nanmedian(x[2][:, 0]))
            chosen += [(tr, b, feet, side) for tr, b, feet in picked]
    else:
        if tracks:
            tallest = max(np.nanmedian([b[3] - b[1] for b in tr.boxes.values()]) for tr in tracks)
            for tr in tracks[: 2 * per_side]:
                height = np.nanmedian([b[3] - b[1] for b in tr.boxes.values()])
                if height >= 0.35 * tallest and len(tr.boxes) >= 0.05 * n / 2:
                    chosen.append((tr, boxes_array(tr, n), None, 0))
    if not chosen:
        raise ValueError("No players were found in the video.")
    default_names = ([f"Near {s}" for s in (["player"] if per_side == 1 else ["left", "right"])]
                     + [f"Far {s}" for s in (["player"] if per_side == 1 else ["left", "right"])]) if court is not None \
        else [f"Player {i + 1}" for i in range(len(chosen))]
    players: list[Player] = []
    for i, (tr, b, feet, side) in enumerate(chosen):
        name = names[i] if names and i < len(names) and names[i] else default_names[i]
        hand = hands[i] if hands and i < len(hands) and hands[i] else "right"
        players.append(Player(id=f"p{i + 1}", name=name, team=side, hand=hand))
    boxes = np.stack([c[1] for c in chosen])
    feet_all = [c[2] for c in chosen]

    # ---- ball and events ---------------------------------------------------
    track = build_track(cands[:n], size)
    sounds = impact_sounds(read_audio(video_path, 16000), 16000) if info.has_audio else []
    events = detect_events(track, times, boxes, size, sounds, court, rackets=rackets)

    landmarker = mp = None
    clock = [0]
    hits: list[Hit] = []
    extras: dict[float, dict] = {}
    sx, sy = info.width / w, info.height / h
    hit_events = [e for e in events if e.kind == "hit"]
    for j, e in enumerate(hit_events):
        pi = e.player
        player = players[pi]
        box = boxes[pi, e.frame]
        pos = positions = None
        if court is not None:
            f = feet_all[pi][e.frame]
            pos = None if np.isnan(f[0]) else (float(f[0]), float(f[1]))
            positions = {players[q].id: (float(feet_all[q][e.frame][0]), float(feet_all[q][e.frame][1]))
                         for q in range(len(players)) if not np.isnan(feet_all[q][e.frame][0])}
        above_head = bool(e.xy[1] < box[1] + 0.05 * (box[3] - box[1])) if not np.isnan(box[0]) else False
        stroke, detail = "unknown", None
        box_h_src = (box[3] - box[1]) * sy if not np.isnan(box[0]) else 0
        if mocap and box_h_src >= MOCAP_MIN_BOX_PX and not e.unsure_player:   # overlapping players confuse pose tracking
            if landmarker is None:
                landmarker, mp = make_landmarker("full")
            lo, hi = max(0, e.frame - int(fps_a)), min(n, e.frame + int(0.7 * fps_a) + 1)
            window = boxes[pi, lo:hi] * np.array([sx, sy, sx, sy])
            detail = shot_mocap(video_path, info, e.t, window, player.hand, height_m, landmarker, mp, clock,
                                keyframe_path=str(out / f"shot{j + 1}.jpg"))
            if detail:
                stroke = detail["stroke"]
                above_head = above_head or stroke == "serve/overhead"
        if stroke == "unknown" and court is not None and pos is not None and not np.isnan(box[0]):
            stroke = _lateral_stroke(e.xy, box, pos, court, player.hand)
        hits.append(Hit(t=e.t, player=player.id, pos=pos, positions=positions or {}, above_head=above_head,
                        stroke=stroke, unsure_player=e.unsure_player, frame=e.frame))
        extras[e.t] = dict(mocap=detail, unsure_player=e.unsure_player, heard=e.heard, frame=e.frame)
        if progress:
            progress(0.7 + 0.15 * (j + 1) / max(len(hit_events), 1))
    if landmarker is not None:
        landmarker.close()
    bounces = [Bounce(e.t, e.court_xy) for e in events if e.kind == "bounce"]

    # ---- rallies, shots, points -------------------------------------------
    rallies = split_rallies(hits, bounces)
    name_of = {p.id: p.name for p in players}
    rally_rows, all_shots = [], []
    lesson = session == "lesson"
    for k, rally in enumerate(rallies):
        shots = build_shots(rally, fmt, judge_all=lesson)
        all_shots += shots
        rows = []
        for s in shots:
            row = dict(player=s.player, name=name_of[s.player], t=round(s.t, 2), stroke=s.stroke, contact=s.contact,
                       result=s.result, speed_kmh=s.speed_kmh, hit_pos=s.hit_pos, bounce_pos=s.bounce_pos)
            row.update(extras.get(s.t, {}))
            rows.append(row)
        rally_rows.append(dict(n=k + 1, t_start=round(rally.t_start, 2), t_end=round(rally.t_end, 2), shots=rows))

    report = dict(
        kind="match", session=session, mode=mode, format=fmt, warnings=warnings,
        video=dict(width=info.width, height=info.height, fps=round(info.fps, 2), duration=round(info.duration, 2)),
        players=[dict(asdict(p), color=COLORS[i % len(COLORS)]) for i, p in enumerate(players)],
        tracking=dict(analysis_fps=round(fps_a, 1), frames=n, ball_seen_pct=round(100 * float((~np.isnan(track[:, 0])).mean()), 1),
                      hits=len(hits), bounces=len(bounces), impact_sounds=len(sounds), camera_static=bool(static)),
        rallies=rally_rows,
        shot_summary=shot_summary(all_shots, players),
    )
    # swing averages per player from the per-shot mocap
    session: dict[str, dict] = {}
    for p in players:
        rows = [extras[h.t]["mocap"] for h in hits if h.player == p.id and extras[h.t]["mocap"]]
        agg = {}
        for key in MOCAP_KEYS:
            vals = [r["metrics"][key]["value"] for r in rows if key in r["metrics"] and isinstance(r["metrics"][key]["value"], (int, float))]
            if vals:
                meta = next(r["metrics"][key] for r in rows if key in r["metrics"])
                agg[key] = dict(label=meta["label"], unit=meta["unit"], typical=meta["typical"], mean=round(float(np.mean(vals)), 1),
                                min=round(float(np.min(vals)), 1), max=round(float(np.max(vals)), 1), n=len(vals))
        session[p.id] = dict(name=p.name, swings_measured=len(rows), metrics=agg)
    report["session"] = session

    if lesson:
        report["lesson"] = lesson_breakdown(all_shots, players)
    if court is not None:
        report["court"] = court.to_dict()
        report["movement"] = {p.id: _movement(feet_all[i], times) for i, p in enumerate(players)}
    if court is not None and not lesson:
        points, review = build_points(rallies, players, fmt)
        for point in points:
            lo, hi = np.searchsorted(times, [point.t_start - 1.0, point.t_end + 0.5])
            for i, p in enumerate(players):
                seg = feet_all[i][lo:hi]
                seg = seg[~np.isnan(seg[:, 0])]
                if len(seg) > 1:
                    step = np.linalg.norm(np.diff(seg, axis=0), axis=1)
                    point.distance_m[p.id] = round(float(step[step < 0.5].sum()), 1)
        match = Match(format=fmt, players=players, points=points, rules=rules or Rules(), duration_s=info.duration)
        report["match"] = match.to_dict()
        report["review"] = [dict(t_start=r["t_start"], t_end=r["t_end"], reason=r["reason"], end_type=r["end_type"],
                                 shots=len(r["shots"])) for r in review]
        if points:
            stats = compute(match)
            pos = positioning(match)
            report["stats"] = stats
            report["positioning"] = pos
            report["recommendations"] = recommendations(match, stats, pos)
        # positioning from every rally, scored or not, so advice is available even before points are confirmed
        loose = Match(format=fmt, players=players, rules=rules or Rules())
        from ..stats.schema import Point
        for rally in rallies:
            shots = build_shots(rally, fmt)
            if shots:
                loose.points.append(Point(server=shots[0].player, winner_team=0, shots=shots))
        report["positioning_all_rallies"] = positioning(loose)

    render_match(video_path, str(out / "overlay.mp4"), info, stride, size, times, players, boxes, track, events, court,
                 [extras[h.t] | dict(t=h.t, player=h.player, stroke=h.stroke) for h in hits], feet_all if court is not None else None,
                 rackets=rackets, progress=report_progress(0.85, 1.0))
    report["files"] = dict(overlay="overlay.mp4")
    (out / "report.json").write_text(json.dumps(report, indent=1, default=lambda o: None))
    if progress:
        progress(1.0)
    return report


def main() -> None:
    ap = argparse.ArgumentParser(description="Tennis match / session tracking")
    ap.add_argument("video")
    ap.add_argument("--out", default="out/match")
    ap.add_argument("--format", default="singles", choices=["singles", "doubles"])
    ap.add_argument("--names", default="", help="comma-separated, near side first (left to right), then far side")
    ap.add_argument("--corners", default="", help="8 numbers: far-left, far-right, near-right, near-left as x,y fractions of the frame")
    ap.add_argument("--no-mocap", action="store_true")
    ap.add_argument("--lesson", action="store_true", help="lesson mode: judge every shot in or out on its own")
    args = ap.parse_args()
    from .. import ensure_ffmpeg
    ensure_ffmpeg()
    corners = None
    if args.corners:
        v = [float(x) for x in args.corners.split(",")]
        corners = [v[i:i + 2] for i in range(0, 8, 2)]
    report = analyze_match(args.video, args.out, args.format, [s for s in args.names.split(",") if s] or None,
                           corners=corners, mocap=not args.no_mocap, session="lesson" if args.lesson else "match")
    print(f"mode: {report['mode']}  players: {[p['name'] for p in report['players']]}  ball seen: {report['tracking']['ball_seen_pct']}%")
    for w_ in report["warnings"]:
        print("warning:", w_)
    for r in report["rallies"]:
        print(f"rally {r['n']} ({r['t_start']}-{r['t_end']}s)")
        for s in r["shots"]:
            print(f"   {s['t']:6.2f}s {s['name']:14} {s['stroke']:14} {s['contact']:12} -> {s['result']:8}"
                  f"{'' if not s['speed_kmh'] else str(s['speed_kmh']) + ' km/h'}{'  (check player)' if s.get('unsure_player') else ''}")
    for rec in report.get("recommendations", []):
        print(f"[{rec['priority']}] {rec['title']}: {rec['evidence']} -> {rec['advice']}")


if __name__ == "__main__":
    main()
