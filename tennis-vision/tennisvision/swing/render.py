"""Overlay video for swing mode: clean skeleton, hitting arm and racket path, foot-direction arrows, contact marker."""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from .. import pose as P
from ..video import VideoInfo, VideoWriter, iter_frames
from .analyze import Swing, SwingAnalyzer

BONE = (245, 245, 245)
OUTLINE = (24, 18, 12)
BLUE = (255, 125, 47)            # brand blue #2f7dff in BGR
RACKET = (255, 255, 255)
STATUS_BGR = {"good": (120, 205, 80), "ok": (70, 180, 235), "work": (70, 110, 255), "info": BONE}
PHASE_LABELS = [("takeback", "Takeback"), ("backswing_end", "Racket back"), ("forward_swing", "Forward swing"),
                ("contact", "Contact"), ("finish", "Finish")]
FONT_FILES = [
    "/usr/share/fonts/opentype/inter/Inter-SemiBold.otf", "C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/arialbd.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]
_fonts: dict[int, object] = {}


def _font(size: int):
    if size not in _fonts:
        _fonts[size] = None
        try:
            from PIL import ImageFont
            for path in FONT_FILES:
                if Path(path).is_file():
                    _fonts[size] = ImageFont.truetype(path, size)
                    break
        except Exception:
            pass
    return _fonts[size]


def chip(img: np.ndarray, text: str, org: tuple[int, int], size: int = 22, bg=(43, 15, 6), fg=(255, 255, 255)) -> None:
    """Rounded label. Uses a real typeface when one is installed, OpenCV's built-in font otherwise."""
    font = _font(size)
    x, y = org
    if font is None:
        (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_DUPLEX, size / 32, 1)
        cv2.rectangle(img, (x, y), (x + tw + 20, y + th + 16), bg, -1, cv2.LINE_AA)
        cv2.putText(img, text, (x + 10, y + th + 8), cv2.FONT_HERSHEY_DUPLEX, size / 32, fg, 1, cv2.LINE_AA)
        return
    from PIL import Image, ImageDraw
    left, top, right, bottom = font.getbbox(text)
    w, h = right - left + 2 * int(size * 0.6), int(size * 1.8)
    x1, y1 = min(x + w, img.shape[1]), min(y + h, img.shape[0])
    patch = Image.fromarray(img[y:y1, x:x1][:, :, ::-1])
    draw = ImageDraw.Draw(patch, "RGBA")
    draw.rounded_rectangle((0, 0, w - 1, h - 1), radius=h // 2, fill=(bg[2], bg[1], bg[0], 225))
    draw.text((int(size * 0.6) - left, (h - (bottom - top)) // 2 - top), text, font=font, fill=(fg[2], fg[1], fg[0]))
    img[y:y1, x:x1] = np.asarray(patch)[:, :, ::-1]


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


def _line(img, a, b, color, thick):
    a, b = tuple(np.int32(a)), tuple(np.int32(b))
    cv2.line(img, a, b, OUTLINE, thick + 3, cv2.LINE_AA)
    cv2.line(img, a, b, color, thick, cv2.LINE_AA)


def draw_skeleton(img: np.ndarray, pts: np.ndarray, vis: np.ndarray, thickness: int = 3, hitting: str | None = None) -> None:
    """White skeleton with a dark edge so it reads on any background; the hitting arm is drawn in blue."""
    arm = {"right": {P.R_SHOULDER, P.R_ELBOW, P.R_WRIST, P.R_INDEX}, "left": {P.L_SHOULDER, P.L_ELBOW, P.L_WRIST, P.L_INDEX}}.get(hitting, set())
    later = []
    for a, b in P.BONES:
        if vis[a] < 0.3 or vis[b] < 0.3 or {a, b} <= {P.L_ANKLE, P.L_HEEL, P.L_TOE} or {a, b} <= {P.R_ANKLE, P.R_HEEL, P.R_TOE}:
            continue
        if a in arm and b in arm and {a, b} != {P.L_SHOULDER, P.R_SHOULDER}:
            later.append((a, b))
            continue
        _line(img, pts[a], pts[b], BONE, thickness)
    for a, b in later:
        _line(img, pts[a], pts[b], BLUE, thickness + 1)
    for j in (P.L_SHOULDER, P.R_SHOULDER, P.L_ELBOW, P.R_ELBOW, P.L_WRIST, P.R_WRIST,
              P.L_HIP, P.R_HIP, P.L_KNEE, P.R_KNEE, P.L_ANKLE, P.R_ANKLE):
        if vis[j] >= 0.3:
            c = tuple(np.int32(pts[j]))
            cv2.circle(img, c, thickness + 2, OUTLINE, -1, cv2.LINE_AA)
            cv2.circle(img, c, thickness, BLUE if j in arm else BONE, -1, cv2.LINE_AA)
    head = pts[[P.L_EAR, P.R_EAR, P.NOSE]].mean(axis=0)
    radius = int(max(6, np.linalg.norm(pts[P.L_EAR] - pts[P.R_EAR]) * 0.9))
    cv2.circle(img, tuple(np.int32(head)), radius, OUTLINE, thickness + 2, cv2.LINE_AA)
    cv2.circle(img, tuple(np.int32(head)), radius, BONE, max(1, thickness - 1), cv2.LINE_AA)


def _foot_arrow(img, pts, vis, heel, toe, color, thick):
    if vis[heel] < 0.3 or vis[toe] < 0.3:
        return
    a, b = pts[heel], pts[toe]
    tip = b + (b - a) * 0.55
    cv2.arrowedLine(img, tuple(np.int32(a)), tuple(np.int32(tip)), OUTLINE, thick + 3, cv2.LINE_AA, tipLength=0.38)
    cv2.arrowedLine(img, tuple(np.int32(a)), tuple(np.int32(tip)), color, thick, cv2.LINE_AA, tipLength=0.38)


def _trail(img, points, ok, color, thick):
    """Path that fades out toward its older end (blended into the picture, so the tail goes clear rather than dark)."""
    if len(points) < 2:
        return
    alpha = np.zeros(img.shape[:2], np.uint8)
    for k in range(1, len(points)):
        if ok[k] and ok[k - 1]:
            f = k / len(points)
            cv2.line(alpha, tuple(np.int32(points[k - 1])), tuple(np.int32(points[k])), int(235 * f ** 1.5),
                     max(1, int(thick * (0.5 + f))), cv2.LINE_AA)
    ys, xs = np.nonzero(alpha)
    if not len(ys):
        return
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    a = alpha[y0:y1, x0:x1, None].astype(np.float32) / 255.0
    region = img[y0:y1, x0:x1].astype(np.float32)
    img[y0:y1, x0:x1] = (region * (1 - a) + np.array(color, np.float32) * a).astype(np.uint8)


def _phase_at(swings: list[Swing], frame: int) -> str:
    label = ""
    for s in swings:
        for key, name in (s.phases or PHASE_LABELS):
            if s.frames[key] <= frame <= s.frames["finish"] + 6:
                label = f"{s.index}. {name}" if len(swings) > 1 else name
    return label


def _foot_status(swings: list[Swing], frame: int) -> dict[str, str]:
    """Colour for each foot at this moment: back foot is judged while loading, front foot from the forward swing on."""
    out = {"left": "info", "right": "info"}
    for s in swings:
        if not s.topdown or not (s.frames["takeback"] <= frame <= s.frames["finish"] + 6):
            continue
        front = s.topdown["front"]
        rear = "left" if front == "right" else "right"
        status = {m.key: m.status for m in s.metrics}
        if frame < s.frames["forward_swing"]:
            out[rear] = status.get("back_foot_angle", "info")
        else:
            out[front] = status.get("front_foot_angle", "info")
            out[rear] = status.get("back_foot_pivot", "info")
    return out


def render_overlay(video_path: str, out_path: str, an: SwingAnalyzer, swings: list[Swing], info: VideoInfo,
                   keyframe_dir: str | None = None, out_height: int = 1080, progress=None,
                   crop: tuple[int, int, int, int] | None = None) -> dict:
    """Write the annotated video. Returns {"<swing>:<phase>": filename} for the exported key frames."""
    seq = an.seq
    x0, y0, x1, y1 = crop or crop_box(an)
    scale = out_height / (y1 - y0)
    ow, oh = int((x1 - x0) * scale) // 2 * 2, out_height // 2 * 2
    d = an.dom
    trail_len = max(3, int(0.5 * an.fps))
    thick = max(2, int(round(oh / 400)))
    wanted: dict[int, list] = {}
    for s in swings:
        for key, name in (s.phases or PHASE_LABELS)[1:]:
            wanted.setdefault(s.frames[key], []).append((s.index, key))
    contact_frames = {s.frames["contact"] for s in swings}
    keyframes: dict[str, str] = {}
    max_side = max(seq.width, seq.height)
    with VideoWriter(out_path, ow, oh, info.fps, crf=19) as writer:
        for i, _, frame in iter_frames(video_path, info, max_side=max_side):
            if i >= len(seq.t):
                break
            crop = frame[y0:y1, x0:x1]
            img = cv2.resize(crop, (ow, oh), interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC)
            pts = (an.xy[i] - (x0, y0)) * scale
            vis = seq.vis[i] if seq.detected[i] else np.ones(33)
            lo = max(0, i - trail_len)
            if an.racket is not None and an.racket["valid"][i]:
                heads = (an.racket["head"][lo:i + 1] - (x0, y0)) * scale
                _trail(img, heads, an.racket["valid"][lo:i + 1], RACKET, thick * 2)
                rb = (an.racket["boxes"][i] - (x0, y0, x0, y0)) * scale
                cv2.rectangle(img, (int(rb[0]), int(rb[1])), (int(rb[2]), int(rb[3])), RACKET, 1, cv2.LINE_AA)
            hand = (an.xy[lo:i + 1, d["wr"]] - (x0, y0)) * scale
            _trail(img, hand, np.ones(len(hand), bool), BLUE, thick * 2)
            draw_skeleton(img, pts, vis, thick, hitting=an.hand)
            feet = _foot_status(swings, i)
            _foot_arrow(img, pts, vis, P.L_HEEL, P.L_TOE, STATUS_BGR[feet["left"]], thick + 1)
            _foot_arrow(img, pts, vis, P.R_HEEL, P.R_TOE, STATUS_BGR[feet["right"]], thick + 1)
            if any(abs(i - c) <= 1 for c in contact_frames):
                centre = tuple(np.int32(pts[d["wr"]]))
                cv2.circle(img, centre, thick * 9, OUTLINE, thick + 3, cv2.LINE_AA)
                cv2.circle(img, centre, thick * 9, (255, 255, 255), thick, cv2.LINE_AA)
            phase = _phase_at(swings, i)
            if phase:
                chip(img, phase, (16, 16), size=max(18, oh // 42), bg=BLUE if i in contact_frames else (43, 15, 6))
            writer.write(img)
            if keyframe_dir and i in wanted:
                for swing_index, key in wanted[i]:
                    fname = f"swing{swing_index}_{key}.jpg"
                    cv2.imwrite(f"{keyframe_dir}/{fname}", img, [cv2.IMWRITE_JPEG_QUALITY, 90])
                    keyframes[f"{swing_index}:{key}"] = fname
            if progress and i % 10 == 0:
                progress(i / max(len(seq.t), 1))
    return keyframes
