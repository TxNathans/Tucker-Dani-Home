"""Video in, swing report out."""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from ..pose import extract_pose
from ..video import probe, read_audio
from .analyze import SwingAnalyzer, session_summary
from .racket import track_racket
from .serve import ServeAnalyzer, serve_hand
from .render import crop_box, render_overlay

AUDIO_RATE = 16000


def analyze_video(video_path: str, out_dir: str, height_m: float = 1.70, handedness: str = "auto",
                  model: str = "heavy", track_rackets: bool = True, mode: str = "swing", serve_type: str = "auto",
                  progress=None) -> dict:
    """mode: "swing" for groundstrokes and volleys, "serve" for the serve breakdown. serve_type: auto, flat, slice or kick."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    step = lambda lo, hi: (lambda f: progress(lo + (hi - lo) * f)) if progress else None
    info = probe(video_path)
    seq = extract_pose(video_path, variant=model, info=info, progress=step(0.0, 0.6))
    seq.save(str(out / "pose.npz"))
    if seq.detected.mean() < 0.5:
        raise ValueError("Could not find a player in most frames. Film so the whole body is visible.")
    audio = read_audio(video_path, AUDIO_RATE) if info.has_audio else None
    serve = mode == "serve"
    if serve and handedness == "auto":
        handedness = serve_hand(seq)
    analyzer = SwingAnalyzer(seq, height_m, handedness, audio, AUDIO_RATE)
    if track_rackets:
        racket = track_racket(video_path, info, analyzer, crop_box(analyzer, margin=1.1 if serve else 0.9), progress=step(0.6, 0.8))
        if racket["seen"].mean() > 0.15:
            analyzer.set_racket(racket)
    if serve:
        swings = ServeAnalyzer(analyzer, serve_type).analyze_all()
        if not swings:
            raise ValueError("No serve was found. Film the whole serve with the full body and the raised arm in view.")
    else:
        swings = analyzer.analyze()
    crop = crop_box(analyzer, margin=0.8 if serve else 0.45)
    keyframes = render_overlay(video_path, str(out / "overlay.mp4"), analyzer, swings, info,
                               keyframe_dir=str(out), progress=step(0.8, 1.0), crop=crop, clean_path=str(out / "clean.mp4"))
    cx0, cy0, cx1, cy1 = crop
    norm = lambda p: [round(float((p[0] - cx0) / (cx1 - cx0)), 4), round(float((p[1] - cy0) / (cy1 - cy0)), 4)]
    wrist = analyzer.xy[:, analyzer.dom["wr"]]
    trace = dict(hand=[norm(p) for p in wrist], head=None)
    if analyzer.racket is not None:
        trace["head"] = [norm(p) if ok else None for p, ok in zip(analyzer.racket["head"], analyzer.racket["valid"])]
    # Everything the app needs to draw its own layers on the clean video: one row per frame, in thousandths of the picture.
    grid = lambda p: [int(round(1000 * float((p[0] - cx0) / (cx1 - cx0)))), int(round(1000 * float((p[1] - cy0) / (cy1 - cy0))))]
    tracks = dict(
        fps=float(f"{info.fps:.4f}"), frames=len(seq.t), aspect=round((cx1 - cx0) / (cy1 - cy0), 4), hand=analyzer.hand,
        pose=[[v for p in frame for v in grid(p)] for frame in analyzer.xy],
        hidden=[[int(j) for j in range(33) if seq.detected[i] and seq.vis[i][j] < 0.3] for i in range(len(seq.t))],
        racket_head=None, racket_box=None,
    )
    if analyzer.racket is not None:
        rk = analyzer.racket
        tracks["racket_head"] = [grid(p) if ok else None for p, ok in zip(rk["head"], rk["valid"])]
        tracks["racket_box"] = [grid(b[:2]) + grid(b[2:]) if ok else None for b, ok in zip(rk["boxes"], rk["valid"])]
    (out / "tracks.json").write_text(json.dumps(tracks, separators=(",", ":")))
    report = dict(
        kind="swing", mode=mode, trace=trace,
        video=dict(width=info.width, height=info.height, fps=round(info.fps, 2), duration=round(info.duration, 2),
                   frames=info.n_frames, pose_frames_detected=int(seq.detected.sum())),
        player=dict(height_m=height_m, hand=analyzer.hand, metres_per_pixel=round(analyzer.m_per_px, 5),
                    camera_distance_m=round(analyzer.distance_m, 1),
                    racket_seen_pct=round(100 * float(analyzer.racket["seen"].mean())) if analyzer.racket else None),
        swings=[asdict(s) for s in swings],
        summary=session_summary(swings),
        keyframes=keyframes,
        series=analyzer.series(),
        files=dict(overlay="overlay.mp4", clean="clean.mp4", tracks="tracks.json", pose="pose.npz"),
        caveats=[
            "One camera: speeds are measured across the camera view, so motion toward or away from the phone is under-counted.",
            "Rotation and joint angles use a single-camera 3D estimate, good to about +/-10-15 degrees. Compare swings filmed from the same spot.",
            "Typical ranges are coaching reference values, not pass/fail grades.",
        ],
    )
    (out / "report.json").write_text(json.dumps(report, indent=1))
    if progress:
        progress(1.0)
    return report


def main() -> None:
    ap = argparse.ArgumentParser(description="Tennis swing mocap analysis")
    ap.add_argument("video")
    ap.add_argument("--out", default="out/swing")
    ap.add_argument("--height", type=float, default=1.70, help="player height in metres")
    ap.add_argument("--hand", default="auto", choices=["auto", "right", "left"])
    ap.add_argument("--model", default="heavy", choices=["lite", "full", "heavy"])
    ap.add_argument("--serve", action="store_true", help="serve analysis instead of groundstroke analysis")
    ap.add_argument("--serve-type", default="auto", choices=["auto", "flat", "slice", "kick"])
    args = ap.parse_args()
    from .. import ensure_ffmpeg
    ensure_ffmpeg()
    report = analyze_video(args.video, args.out, args.height, args.hand, args.model,
                           mode="serve" if args.serve else "swing", serve_type=args.serve_type)
    for s in report["swings"]:
        print(f"Swing {s['index']}: {s['stroke']} ({s['hand']}-handed), contact at {s['times']['contact']:.2f}s [{s['contact_source']}]")
        for m in s["metrics"]:
            print(f"  {m['status']:5} {m['phase']:15} {m['label']}: {m['value']} {m['unit']}")
    print(f"Report: {args.out}/report.json   Overlay: {args.out}/overlay.mp4")


if __name__ == "__main__":
    main()
