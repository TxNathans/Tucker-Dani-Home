"""Draw the mocap skeleton, hand trail and live readouts onto the video; export key frames."""
from __future__ import annotations

import cv2
import numpy as np

from .. import pose as P
from ..video import VideoInfo, VideoWriter, iter_frames
from .analyze import Swing, SwingAnalyzer, _angle

LEFT_COLOR = (255, 170, 60)     # BGR: blue-ish for the left side
RIGHT_COLOR = (60, 200, 255)    # amber for the right side
MID_COLOR = (235, 235, 235)
TRAIL_COLOR = (80, 255, 160)
PHASE_LABELS = [("takeback", "Takeback"), ("backswing_end", "Backswing set"), ("forward_swing", "Forward swing"),
                ("contact", "Contact"), ("finish", "Follow-through")]


def crop_box(an: SwingAnalyzer, margin: float = 0.45, aspect: float = 3 / 4) -> tuple[int, int, int, int]:
    """One fixed crop that keeps the player in view for the whole clip (x0, y0, x1, y1 in analysis pixels)."""
    xy, w, h = an.xy, an.seq.width, an.seq.height
    x0, y0 = xy[..., 0].min(), xy[..., 1].min()
    x1, y1 = xy[..., 0].max(), xy[..., 1].max()
    pad = margin * (an.height_m / an.m_per_px)
    x0, x1, y0, y1 = x0 - pad, x1 + pad, y0 - pad, y1 + pad * 0.6
    cw, ch = x1 - x0, y1 - y0
    if cw / ch < aspect:
        grow = ch * aspect - cw
        x0, x1 = x0 - grow / 2, x1 + grow / 2
    else:
        grow = cw / aspect - ch
        y0, y1 = y0 - grow / 2, y1 + grow / 2
    cw, ch = min(x1 - x0, w), min(y1 - y0, h)
    x0 = float(np.clip(x0, 0, w - cw))
    y0 = float(np.clip(y0, 0, h - ch))
    return int(x0), int(y0), int(x0 + cw), int(y0 + ch)


def _text(img, text, org, scale=0.6, color=(255, 255, 255), thick=1):
    cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), thick + 3, cv2.LINE_AA)
    cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, scale, color, thick, cv2.LINE_AA)


def _chip(img, text, org, scale=0.6, bg=(30, 30, 30), fg=(255, 255, 255)):
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, 2)
    x, y = org
    cv2.rectangle(img, (x, y), (x + tw + 16, y + th + 14), bg, -1, cv2.LINE_AA)
    cv2.putText(img, text, (x + 8, y + th + 6), cv2.FONT_HERSHEY_SIMPLEX, scale, fg, 2, cv2.LINE_AA)


def draw_skeleton(img: np.ndarray, pts: np.ndarray, vis: np.ndarray, thickness: int = 3) -> None:
    for a, b in P.BONES:
        if vis[a] < 0.3 or vis[b] < 0.3:
            continue
        left, right = a % 2 == 1, b % 2 == 1
        color = MID_COLOR if left != right else LEFT_COLOR if left else RIGHT_COLOR
        cv2.line(img, tuple(np.int32(pts[a])), tuple(np.int32(pts[b])), color, thickness, cv2.LINE_AA)
    for j in (P.L_SHOULDER, P.R_SHOULDER, P.L_ELBOW, P.R_ELBOW, P.L_WRIST, P.R_WRIST,
              P.L_HIP, P.R_HIP, P.L_KNEE, P.R_KNEE, P.L_ANKLE, P.R_ANKLE):
        if vis[j] >= 0.3:
            cv2.circle(img, tuple(np.int32(pts[j])), thickness + 2, (255, 255, 255), -1, cv2.LINE_AA)
            cv2.circle(img, tuple(np.int32(pts[j])), thickness + 2, (40, 40, 40), 1, cv2.LINE_AA)
    head = pts[[P.L_EAR, P.R_EAR, P.NOSE]].mean(axis=0)
    radius = int(max(6, np.linalg.norm(pts[P.L_EAR] - pts[P.R_EAR]) * 0.9))
    cv2.circle(img, tuple(np.int32(head)), radius, MID_COLOR, 2, cv2.LINE_AA)


def _phase_at(swings: list[Swing], frame: int) -> str:
    label = ""
    for s in swings:
        for key, name in PHASE_LABELS:
            if frame >= s.frames[key] and frame <= s.frames["finish"] + 6:
                label = f"{s.stroke.capitalize()} {s.index}: {name}" if len(swings) > 1 else name
    return label


def _angle_label(img, pts, a, b, c, value):
    _text(img, f"{value:.0f}", (int(pts[b][0]) + 10, int(pts[b][1]) - 8), 0.55, (120, 255, 255), 2)


def render_overlay(video_path: str, out_path: str, an: SwingAnalyzer, swings: list[Swing], info: VideoInfo,
                   keyframe_dir: str | None = None, out_height: int = 960, progress=None) -> dict:
    """Write the annotated video. Returns {key: filename} for exported key frames of each swing."""
    seq = an.seq
    x0, y0, x1, y1 = crop_box(an)
    scale = out_height / (y1 - y0)
    ow, oh = int((x1 - x0) * scale) // 2 * 2, out_height // 2 * 2
    d, w3 = an.dom, an.world
    elbow = _angle(w3[:, d["sh"]], w3[:, d["el"]], w3[:, d["wr"]])
    knee = _angle(w3[:, d["hip"]], w3[:, d["kn"]], w3[:, d["an"]])
    trail_len = max(3, int(0.45 * an.fps))
    thick = max(2, int(round(oh / 380)))
    wanted = {}
    for s in swings:
        for key, name in PHASE_LABELS[1:]:
            wanted.setdefault(s.frames[key], []).append((s.index, key, name))
    keyframes: dict[str, str] = {}
    max_side = max(seq.width, seq.height)
    with VideoWriter(out_path, ow, oh, info.fps) as writer:
        for i, _, frame in iter_frames(video_path, info, max_side=max_side):
            if i >= len(seq.t):
                break
            crop = frame[y0:y1, x0:x1]
            img = cv2.resize(crop, (ow, oh), interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR)
            pts = (an.xy[i] - (x0, y0)) * scale
            lo = max(0, i - trail_len)
            trail = (an.xy[lo:i + 1, d["wr"]] - (x0, y0)) * scale
            for k in range(1, len(trail)):
                alpha = k / len(trail)
                cv2.line(img, tuple(np.int32(trail[k - 1])), tuple(np.int32(trail[k])),
                         tuple(int(c * alpha) for c in TRAIL_COLOR), max(1, int(thick * 1.5 * alpha)), cv2.LINE_AA)
            draw_skeleton(img, pts, seq.vis[i] if seq.detected[i] else np.ones(33), thick)
            _angle_label(img, pts, d["sh"], d["el"], d["wr"], elbow[i])
            _angle_label(img, pts, d["hip"], d["kn"], d["an"], knee[i])
            phase = _phase_at(swings, i)
            if phase:
                is_contact = any(i == s.frames["contact"] for s in swings)
                _chip(img, phase, (12, 12), 0.7, bg=(40, 40, 220) if is_contact else (30, 30, 30))
            cv2.rectangle(img, (0, oh - 44), (ow, oh), (20, 20, 20), -1)
            readout = f"hand {an.hand_speed[i]:4.1f} m/s   elbow {elbow[i]:3.0f}   knee {knee[i]:3.0f}   t {an.t[i]:.2f}s"
            cv2.putText(img, readout, (12, oh - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
            writer.write(img)
            if keyframe_dir and i in wanted:
                for swing_index, key, name in wanted[i]:
                    fname = f"swing{swing_index}_{key}.jpg"
                    cv2.imwrite(f"{keyframe_dir}/{fname}", img, [cv2.IMWRITE_JPEG_QUALITY, 88])
                    keyframes[f"{swing_index}:{key}"] = fname
            if progress and i % 10 == 0:
                progress(i / max(len(seq.t), 1))
    return keyframes
