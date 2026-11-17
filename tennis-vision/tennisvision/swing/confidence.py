"""How sure the app is of each number, and a check of the video itself.

One phone camera sees some things directly (a knee angle from the side, how far the head moved) and has to estimate
others (how far the shoulders turned, where the racket head is). Coaching should lean on the first kind. Every metric
gets one of three levels:

    high      seen directly in the picture; graded normally
    estimate  worked out in 3D, read from the racket's outline, or timed between frames; graded, but never the
              reason a swing is marked Priority
    low       the body part or the racket was hidden or blurred at that moment; shown but not graded

The base level for each number comes from how it is measured. It is then lowered for the clip in hand: a low frame
rate, no ball sound to pin contact, a hidden foot, a racket the detector lost.
"""
from __future__ import annotations

import numpy as np

from .. import pose as P

LEVELS = ("low", "estimate", "high")

# Numbers that rest on the 3D body estimate (depth from one camera), whatever the camera angle.
DEPTH = {"shoulder_turn", "hip_turn", "separation", "shoulders_at_contact", "shoulder_rotation", "rotation_after",
         "hip_rotation_speed", "shoulder_rotation_speed", "sequence", "front_foot_angle", "back_foot_angle", "back_foot_pivot",
         "elbow_contact", "weight_on_lead", "weight_on_lead_back", "balance", "stance_type",
         "serve_coil", "serve_elbow_trophy", "serve_elbow_drop", "serve_elbow_contact", "serve_stance"}
# Distances measured along the hitting line: seen directly from the side, estimated from behind.
ALONG = {"contact_in_front", "extension", "weight_through", "chest_lead", "step_in", "weight_shift"}
# Distances measured across the hitting line: seen directly from behind, estimated from the side.
ACROSS = {"contact_spacing"}
# Numbers read from the racket's outline.
RACKET = {"racket_head_speed", "racket_drop", "racket_angle_back", "racket_angle_low", "racket_angle_contact", "racket_lag",
          "approach_angle", "swing_plane", "serve_racket_drop", "serve_racket_speed"}
# Hand speed across the picture stands in for what the racket is doing.
PROXY = {"speed_carried", "hand_speed_contact", "serve_type"}
# Numbers that depend on knowing the exact moment of contact.
TIMED = {"contact_in_front", "extension", "speed_carried", "hand_speed_contact", "elbow_contact", "swing_path", "contact_spacing",
         "shoulders_at_contact", "approach_angle", "racket_angle_contact", "serve_elbow_contact", "serve_shoulder_over",
         "serve_contact_front", "serve_contact_side", "serve_swing_up"}

FEET = {"stance_type", "front_foot_angle", "back_foot_angle", "back_foot_pivot", "step_in", "stance_width", "balance",
        "weight_on_lead", "weight_on_lead_back", "serve_stance", "serve_stance_width", "serve_into_court", "serve_feet_off"}
LEGS = {"knee_bend_dom", "knee_bend_off", "leg_drive", "lead_knee_back", "lead_knee_contact", "lead_brace", "trail_knee_back",
        "trail_knee_contact", "trail_drive", "serve_knee_lead", "serve_knee_trail", "serve_leg_drive_lead", "serve_leg_drive_trail"}
ARM = {"elbow_contact", "contact_in_front", "contact_spacing", "contact_height", "extension", "speed_carried", "swing_path",
       "follow_length", "finish_height", "hand_speed_peak", "hand_speed_contact", "serve_contact_height", "serve_elbow_contact",
       "serve_elbow_trophy", "serve_elbow_height", "serve_swing_up", "serve_hand_speed"}
TOSS_ARM = {"serve_toss_arm_straight", "serve_toss_arm_up", "serve_toss_arm_hold"}

WHY = {
    "high": "Seen directly in the picture.",
    "depth": "Worked out in 3D from one camera, so treat it as a guide rather than an exact number.",
    "view_side": "Measured toward or away from the camera, which one camera can only estimate. Film from behind to read it directly.",
    "view_behind": "Measured toward or away from the camera, which one camera can only estimate. Film from the side to read it directly.",
    "racket": "Read from the racket's outline in the picture, so treat it as a guide.",
    "proxy": "Read from the hand, which stands in for the racket here, so treat it as a guide.",
    "fps": "At {fps} frames a second the moment of contact falls between frames, so this is a guide. Film at 60 or in slow-motion to firm it up.",
    "sound": "No clear ball sound was found, so the moment of contact is an estimate and so is this.",
    "racket_blur": "Not graded: at {fps} frames a second the racket is a blur through the hitting zone. Film at 60 or in slow-motion.",
    "racket_lost": "Not graded: the racket could not be followed through this part of the swing.",
    "feet_hidden": "Not graded: the feet were hidden or out of the picture.",
    "legs_hidden": "Not graded: the knees were hidden or out of the picture.",
    "arm_hidden": "Not graded: the hitting arm was hidden at this moment.",
    "toss_hidden": "Not graded: the tossing arm was hidden or left the picture.",
}


def _lower(level: str, steps: int = 1) -> str:
    return LEVELS[max(0, LEVELS.index(level) - steps)]


def _seen(vis: np.ndarray, frames: slice, joints: list[int]) -> float:
    """Typical visibility of a group of joints over a span of frames (0 to 1)."""
    part = vis[frames][:, joints]
    return float(np.median(part)) if part.size else 0.0


def view_of(analyzer, swing) -> tuple[str, float]:
    """("side" | "behind" | "angled", share of the hitting line that points toward or away from the camera)."""
    if swing.serve:
        return ("side" if "side" in str(swing.serve.get("view", "")) else "behind"), 0.0
    u = analyzer._hitting_direction(swing.frames["contact"])
    depth = abs(float(u[1]))
    return ("side" if depth < 0.45 else "behind" if depth > 0.8 else "angled"), depth


def assess(swing, analyzer) -> None:
    """Set confidence and the plain-words reason on every metric of a swing."""
    fps, vis = analyzer.fps, analyzer.seq.vis
    f = swing.frames
    start, contact, finish = f.get("takeback", 0), f["contact"], f["finish"]
    span = slice(start, finish + 1)
    dom = analyzer.dom
    off = analyzer.off
    feet_seen = _seen(vis, span, [P.L_HEEL, P.R_HEEL, P.L_TOE, P.R_TOE])
    legs_seen = _seen(vis, span, [P.L_KNEE, P.R_KNEE, P.L_ANKLE, P.R_ANKLE])
    near = slice(max(contact - max(1, int(round(0.05 * fps))), 0), contact + max(2, int(round(0.05 * fps))))
    arm_seen = _seen(vis, near, [dom["sh"], dom["el"], dom["wr"]])
    toss_seen = _seen(vis, slice(start, contact + 1), [off["el"], off["wr"]])
    view, _ = view_of(analyzer, swing)
    heard = "audio" in (swing.contact_source or "")
    racket = analyzer.racket
    valid = racket["valid"] if racket is not None else None
    racket_swing = float(valid[f.get("backswing_end", start):contact + 1].mean()) if valid is not None else 0.0
    racket_zone = float(valid[near].mean()) if valid is not None else 0.0
    say = lambda key: WHY[key].format(fps=int(round(fps)))

    for m in swing.metrics:
        key = m.key
        level, why = "high", say("high")
        if key in DEPTH:
            level, why = "estimate", say("depth")
        if key in ALONG and view != "side":
            level, why = "estimate", say("view_behind")
        if key in ACROSS and view == "side":
            level, why = "estimate", say("view_side")
        if key in PROXY:
            level, why = "estimate", say("proxy")
        if key in RACKET:
            level, why = "estimate", say("racket")
            zone = key in ("approach_angle", "racket_angle_contact", "swing_plane", "racket_drop", "serve_racket_drop")
            if fps < 45 and zone:
                level, why = "low", say("racket_blur")
            elif racket_swing < 0.5 or (zone and racket_zone < 0.5):
                level, why = "low", say("racket_lost")
        if key in TIMED and level != "low":
            if fps < 45:
                level, why = _lower(level) if level == "high" else level, say("fps")
            elif not heard:
                level, why = _lower(level) if level == "high" else level, say("sound")
        if key in FEET and feet_seen < 0.4:
            level, why = "low", say("feet_hidden")
        if key in LEGS and legs_seen < 0.4:
            level, why = "low", say("legs_hidden")
        if key in ARM and arm_seen < 0.35:
            level, why = "low", say("arm_hidden")
        if key in TOSS_ARM and toss_seen < 0.35:
            level, why = "low", say("toss_hidden")
        m.confidence, m.seen = level, why


def video_checks(analyzer, info, swings, pose_detected: float) -> list[dict]:
    """What the video itself allows: each check is good, warn or bad with one line on what to change next time."""
    out = []
    add = lambda cid, label, status, text, tip="": out.append(dict(id=cid, label=label, status=status, text=text, tip=tip))
    fps = analyzer.fps
    if fps >= 100:
        add("fps", "Frame rate", "good", f"{fps:.0f} frames a second (slow-motion). Contact timing and the racket are sharp.")
    elif fps >= 45:
        add("fps", "Frame rate", "good", f"{fps:.0f} frames a second. Good for everything except the fastest racket numbers.",
            "Slow-motion (120 or 240) sharpens the racket.")
    else:
        add("fps", "Frame rate", "warn", f"{fps:.0f} frames a second. Contact falls between frames, so contact and racket numbers are guides.",
            "In the iPhone camera, set video to 60 fps or use Slo-mo.")
    if pose_detected >= 0.95:
        add("body", "Body in view", "good", "The whole body was tracked through the clip.")
    else:
        add("body", "Body in view", "warn" if pose_detected >= 0.75 else "bad",
            f"The body was tracked in {pose_detected * 100:.0f}% of frames.", "Keep the whole body in the picture from start to finish.")
    size = (analyzer.height_m / analyzer.m_per_px) / max(analyzer.seq.height, 1)
    if size < 0.22:
        add("size", "Player size", "warn", f"The player fills only {size * 100:.0f}% of the picture height, so small movements are hard to read.",
            "Stand closer or zoom in so the player fills about half the picture.")
    elif size > 0.92:
        add("size", "Player size", "warn", "The player nearly fills the picture, so the racket and feet may leave it.",
            "Step back so there is room above the head and below the feet.")
    else:
        add("size", "Player size", "good", f"The player fills {size * 100:.0f}% of the picture height.")
    if swings:
        vis = analyzer.seq.vis
        s = swings[0]
        span = slice(s.frames.get("takeback", 0), s.frames["finish"] + 1)
        feet = _seen(vis, span, [P.L_HEEL, P.R_HEEL, P.L_TOE, P.R_TOE])
        if feet < 0.4:
            add("feet", "Feet in view", "bad", "The feet were hidden or cut off, so footwork is not graded.", "Tilt the phone down so both feet stay in the picture.")
        else:
            add("feet", "Feet in view", "good", "Both feet were in view.")
        if analyzer.racket is None:
            add("racket", "Racket", "bad", "The racket could not be followed, so racket numbers are left out.",
                "A plain background behind the swing and a higher frame rate both help.")
        else:
            seen = float(analyzer.racket["valid"][s.frames.get("backswing_end", 0):s.frames["contact"] + 1].mean())
            if seen >= 0.7:
                add("racket", "Racket", "good", f"The racket was followed through {seen * 100:.0f}% of the swing.")
            else:
                add("racket", "Racket", "warn" if seen >= 0.5 else "bad", f"The racket was followed through only {seen * 100:.0f}% of the swing.",
                    "A plain background behind the swing and a higher frame rate both help.")
        if "audio" in (s.contact_source or ""):
            add("contact", "Contact", "good", "Contact was pinned to the sound of the ball.")
        else:
            add("contact", "Contact", "warn", "No clear ball sound, so contact was estimated from the swing.",
                "Film with sound on and the phone within about 30 feet.")
        view, _ = view_of(analyzer, s)
        if s.serve:
            add("view", "Camera angle", "good", f"Filmed from {s.serve.get('view', 'the side')}." + (
                " This angle shows how far out to the side the ball is met." if view == "behind" else " This angle shows how far into the court the ball is met."))
        elif view == "side":
            add("view", "Camera angle", "good", "Filmed from the side: contact point, extension and weight shift are seen directly.")
        elif view == "behind":
            add("view", "Camera angle", "good", "Filmed from behind: spacing from the ball is seen directly; contact point and extension are estimates.",
                "Film from the side to read contact point and extension directly.")
        else:
            add("view", "Camera angle", "warn", "Filmed at an angle to the shot, so distances along and across the hitting line are estimates.",
                "Stand level with the player, square to the side fence or directly behind.")
    return out
