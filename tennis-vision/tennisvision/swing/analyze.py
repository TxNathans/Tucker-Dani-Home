"""Swing analysis from a pose sequence: find swings, time the phases, measure the body.

Accuracy notes that shape the design:
- Image-plane measures (heights, hand speed, path) are scaled to metres from the player's height.
  Motion toward or away from the camera is not seen, so speeds are lower bounds.
- Rotation and joint angles come from the model's single-camera 3D estimate. Expect roughly
  +/-10 to 15 degrees, so read them as trends between swings, not lab numbers.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

import numpy as np
from scipy.signal import butter, find_peaks, savgol_filter, sosfiltfilt

from .. import pose as P
from ..pose import PoseSequence

SHOULDER_TO_ANKLE = 0.779      # fraction of stature (Winter anthropometric table)
SPEED_OF_SOUND = 343.0
PHONE_LONG_SIDE_FOV_DEG = 62.0  # iPhone 1x video, long side; used only to estimate sound delay


@dataclass
class Metric:
    key: str
    label: str
    value: float | str | None
    unit: str
    phase: str
    typical: str = ""
    status: str = "info"   # good | ok | work | info
    note: str = ""


@dataclass
class Swing:
    index: int
    stroke: str
    hand: str
    two_handed: bool
    times: dict[str, float]
    frames: dict[str, int]
    contact_source: str
    metrics: list[Metric] = field(default_factory=list)
    sequence: list[dict] = field(default_factory=list)
    findings: list[dict] = field(default_factory=list)

    def metric(self, key: str):
        for m in self.metrics:
            if m.key == key:
                return m.value
        return None

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


def _odd(n: float) -> int:
    n = max(3, int(round(n)))
    return n if n % 2 else n + 1


def _smooth(arr: np.ndarray, fps: float, seconds: float, order: int = 2) -> np.ndarray:
    win = min(_odd(seconds * fps), len(arr) - (1 - len(arr) % 2))
    if win <= order:
        return arr.copy()
    return savgol_filter(arr, win, order, axis=0)


def _angle(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> np.ndarray:
    u, v = a - b, c - b
    cos = (u * v).sum(-1) / (np.linalg.norm(u, axis=-1) * np.linalg.norm(v, axis=-1) + 1e-9)
    return np.degrees(np.arccos(np.clip(cos, -1, 1)))


def _plane_angle(world: np.ndarray, right: int, left: int) -> np.ndarray:
    """Rotation of the left->right line about the vertical axis, degrees, unwrapped."""
    d = world[:, right] - world[:, left]
    return np.degrees(np.unwrap(np.arctan2(d[:, 2], d[:, 0])))


def _segment_angular_speed(world: np.ndarray, a: int, b: int, dt: np.ndarray) -> np.ndarray:
    u = world[:, b] - world[:, a]
    u = u / (np.linalg.norm(u, axis=1, keepdims=True) + 1e-9)
    du = np.gradient(u, axis=0) / dt[:, None]
    return np.degrees(np.linalg.norm(np.cross(u, du), axis=1))


def impact_sounds(audio: np.ndarray, rate: int) -> list[tuple[float, float]]:
    """Sharp transients (ball on strings, ball on court): (onset_time_s, strength vs background)."""
    if len(audio) < rate // 4:
        return []
    hp = sosfiltfilt(butter(4, 1500, "hp", fs=rate, output="sos"), audio)
    hop, win = rate // 400, rate // 100
    n = (len(hp) - win) // hop
    if n < 10:
        return []
    env = np.sqrt(np.mean(np.lib.stride_tricks.sliding_window_view(hp, win)[::hop][:n] ** 2, axis=1))
    floor = np.median(env) + 1e-9
    peaks, props = find_peaks(env, height=floor * 3.5, distance=int(0.12 * rate / hop), prominence=floor * 2)
    out = []
    for p, height in zip(peaks, props["peak_heights"]):
        onset = p
        while onset > 0 and env[onset - 1] > floor + 0.35 * (height - floor):
            onset -= 1
        out.append((onset * hop / rate, float(height / floor)))
    return out


class SwingAnalyzer:
    def __init__(self, seq: PoseSequence, height_m: float = 1.70, handedness: str = "auto",
                 audio: np.ndarray | None = None, audio_rate: int = 16000):
        self.seq = seq
        self.fps = seq.fps
        self.t = seq.t
        self.dt = np.gradient(seq.t) if len(seq.t) > 1 else np.ones(1) / seq.fps
        self.height_m = height_m
        self.xy = _smooth(seq.xy.astype(float), self.fps, 0.10)
        self.world = _smooth(seq.world.astype(float), self.fps, 0.15)
        self.m_per_px = self._scale()
        self.distance_m = self._camera_distance()
        self.sounds = impact_sounds(audio, audio_rate) if audio is not None else []
        self.hand = self._dominant_hand() if handedness == "auto" else handedness
        self.side = dict(right=dict(sh=P.R_SHOULDER, el=P.R_ELBOW, wr=P.R_WRIST, hip=P.R_HIP, kn=P.R_KNEE, an=P.R_ANKLE),
                         left=dict(sh=P.L_SHOULDER, el=P.L_ELBOW, wr=P.L_WRIST, hip=P.L_HIP, kn=P.L_KNEE, an=P.L_ANKLE))
        self.dom = self.side[self.hand]
        self.off = self.side["left" if self.hand == "right" else "right"]
        self.hand_vel = np.gradient(self.xy[:, self.dom["wr"]], axis=0) / self.dt[:, None] * self.m_per_px
        self.hand_speed = np.linalg.norm(self.hand_vel, axis=1)
        self.pelvis_angle = _plane_angle(self.world, P.R_HIP, P.L_HIP)
        self.shoulder_angle = _plane_angle(self.world, P.R_SHOULDER, P.L_SHOULDER)
        self.pelvis_vel = np.gradient(self.pelvis_angle) / self.dt
        self.shoulder_vel = np.gradient(self.shoulder_angle) / self.dt
        self.upper_arm_vel = _segment_angular_speed(self.world, self.dom["sh"], self.dom["el"], self.dt)
        self.forearm_vel = _segment_angular_speed(self.world, self.dom["el"], self.dom["wr"], self.dt)
        self.ground_y = self._ground_line()

    # ---- calibration -------------------------------------------------------
    def _scale(self) -> float:
        xy = self.xy
        seg = lambda a, b: np.linalg.norm(xy[:, a] - xy[:, b], axis=1)
        left = seg(P.L_ANKLE, P.L_KNEE) + seg(P.L_KNEE, P.L_HIP) + seg(P.L_HIP, P.L_SHOULDER)
        right = seg(P.R_ANKLE, P.R_KNEE) + seg(P.R_KNEE, P.R_HIP) + seg(P.R_HIP, P.R_SHOULDER)
        body_px = np.percentile(np.maximum(left, right), 90)   # least foreshortened view of the body
        return self.height_m * SHOULDER_TO_ANKLE / max(body_px, 1.0)

    def _camera_distance(self) -> float:
        stature_px = self.height_m / self.m_per_px
        long_side = max(self.seq.width, self.seq.height)
        half = np.radians(PHONE_LONG_SIDE_FOV_DEG / 2)
        angle = 2 * np.arctan(stature_px / long_side * np.tan(half))
        return float(self.height_m / 2 / np.tan(angle / 2))

    def _ground_line(self) -> np.ndarray:
        feet = self.xy[:, [P.L_HEEL, P.R_HEEL, P.L_TOE, P.R_TOE], 1]
        return feet.max(axis=1)

    def _dominant_hand(self) -> str:
        best = {}
        for name, wrist in (("right", P.R_WRIST), ("left", P.L_WRIST)):
            path = _smooth(self.seq.xy[:, wrist].astype(float), self.fps, 0.25)
            speed = np.linalg.norm(np.gradient(path, axis=0), axis=1) / self.dt
            best[name] = np.max(speed * (self.seq.vis[:, wrist] > 0.5))
        return max(best, key=best.get)

    # ---- swing finding -----------------------------------------------------
    def find_swings(self) -> list[int]:
        speed = self.hand_speed
        if len(speed) < 5:
            return []
        threshold = max(3.0, 0.5 * np.percentile(speed, 99.5))
        peaks, _ = find_peaks(speed, height=threshold, distance=max(1, int(0.7 * self.fps)))
        return peaks.tolist()

    def _contact(self, peak: int) -> tuple[int, str]:
        speed = self.hand_speed
        hi = min(len(speed) - 1, peak + int(0.12 * self.fps))
        plateau_end = peak
        for i in range(peak, hi + 1):
            if speed[i] >= 0.93 * speed[peak]:
                plateau_end = i
        delay = self.distance_m / SPEED_OF_SOUND
        t_lo, t_hi = self.t[peak] - 0.03, self.t[hi] + 0.03
        candidates = [(s - delay, k) for s, k in self.sounds if t_lo <= s - delay <= t_hi]
        if candidates:
            t_audio = max(candidates, key=lambda c: c[1])[0]
            frame = int(np.argmin(np.abs(self.t - t_audio)))
            frame = int(np.clip(frame, peak, plateau_end))
            return min(frame, len(speed) - 1), "audio+pose"
        return plateau_end, "pose"

    def _classify(self, start: int, contact: int) -> tuple[str, bool]:
        d, w = self.dom, self.world
        head_y = self.xy[contact, P.NOSE, 1]
        wrist_y = self.xy[contact, d["wr"], 1]
        stature_px = self.height_m / self.m_per_px
        if wrist_y < head_y - 0.05 * stature_px:
            return "serve/overhead", False
        lo = max(start, contact - int(0.45 * self.fps))
        hi = max(lo + 1, contact - int(0.10 * self.fps))
        lateral = w[lo:hi, P.R_SHOULDER] - w[lo:hi, P.L_SHOULDER]
        lateral[:, 1] = 0
        lateral /= np.linalg.norm(lateral, axis=1, keepdims=True) + 1e-9
        mid = (w[lo:hi, P.R_SHOULDER] + w[lo:hi, P.L_SHOULDER]) / 2
        side = np.mean(((w[lo:hi, d["wr"]] - mid) * lateral).sum(1))
        if self.hand == "left":
            side = -side
        hands_gap = np.linalg.norm(w[contact, P.R_WRIST] - w[contact, P.L_WRIST])
        if side >= 0:
            return "forehand", False
        return "backhand", bool(hands_gap < 0.22)

    def _hitting_direction(self, contact: int) -> np.ndarray:
        """Horizontal unit vector (x, z) of the hand's travel into contact: the best pose-only proxy for the hitting line."""
        a = max(contact - 3, 0)
        across = self.hand_vel[a:contact + 1, 0].mean()   # image plane, includes the body's own travel
        depth = (self.world[contact, self.dom["wr"], 2] - self.world[a, self.dom["wr"], 2]) / max(self.t[contact] - self.t[a], 1e-3)
        u = np.array([across, depth])
        return u / (np.linalg.norm(u) + 1e-9)

    def _turn(self, frame: int, u: np.ndarray, left: int, right: int, stroke: str) -> float:
        """Rotation of a left-right body line away from square-on to the hitting line. 0 = facing the target, 90 = side-on."""
        s = (self.world[frame, left] - self.world[frame, right])[[0, 2]]
        sign = 1.0 if (self.hand == "right") == (stroke != "backhand") else -1.0
        left_of_u = np.array([-u[1], u[0]])
        return float(np.degrees(np.arctan2(sign * np.dot(s, u), np.dot(s, left_of_u))))

    # ---- one swing ---------------------------------------------------------
    def analyze_swing(self, index: int, peak: int, lo: int, hi: int) -> Swing:
        d, o = self.dom, self.off
        fps, t, xy, w = self.fps, self.t, self.xy, self.world
        contact, source = self._contact(peak)
        stroke, two_handed = self._classify(lo, contact)

        # swing direction in the image at contact; backswing ends where the hand is furthest back along it
        v = self.hand_vel[max(contact - 2, 0):contact + 1].mean(axis=0)
        direction = v / (np.linalg.norm(v) + 1e-9)
        mid_hip = (xy[:, P.L_HIP] + xy[:, P.R_HIP]) / 2
        progress = ((xy[:, d["wr"]] - mid_hip) * direction).sum(1) * self.m_per_px
        search_lo = max(lo, contact - int(1.2 * fps))
        back = search_lo + int(np.argmin(progress[search_lo:contact])) if contact > search_lo else contact
        if contact - back < 2:
            back = max(lo, contact - int(0.25 * fps))
        # forward swing starts once the hand is clearly accelerating out of the backswing
        fwd = back
        for i in range(back, contact):
            if self.hand_speed[i] > 0.2 * self.hand_speed[peak]:
                fwd = i
                break
        # takeback start: hand leaves its ready position
        span = progress[search_lo:back + 1]
        take = search_lo
        if len(span) > 2:
            ready = np.median(span[: max(2, len(span) // 4)])
            total = ready - progress[back]
            if total > 0.05:
                moved = np.where(span < ready - 0.15 * total)[0]
                take = search_lo + int(moved[0]) if len(moved) else search_lo
        # finish: hand has slowed right down
        finish = hi
        for i in range(contact + 1, hi + 1):
            if self.hand_speed[i] < 0.2 * self.hand_speed[peak]:
                finish = i
                break

        frames = dict(takeback=take, backswing_end=back, forward_swing=fwd, contact=contact, finish=finish)
        times = {k: float(t[f]) for k, f in frames.items()}
        swing = Swing(index=index, stroke=stroke, hand=self.hand, two_handed=two_handed, times=times,
                      frames=frames, contact_source=source)
        m = swing.metrics
        add = lambda *a, **k: m.append(Metric(*a, **k))
        stature_px = self.height_m / self.m_per_px

        # --- timing
        backswing_s = times["backswing_end"] - times["takeback"]
        forward_s = times["contact"] - times["forward_swing"]
        add("prep_time", "Preparation time (takeback start to contact)", round(times["contact"] - times["takeback"], 2), "s", "Preparation",
            typical="0.6 s or more on a rally ball", status="good" if times["contact"] - times["takeback"] >= 0.55 else "ok",
            note="Longer means the racket got back early instead of being rushed.")
        add("forward_swing_time", "Forward swing time", round(forward_s, 2), "s", "Forward swing", typical="0.15-0.35 s")
        if forward_s > 0.03 and backswing_s > 0.03:
            add("tempo_ratio", "Tempo (backswing : forward swing)", round(backswing_s / forward_s, 1), ":1", "Preparation",
                typical="about 2:1 to 4:1", note="Smooth takeback, fast swing.")

        # --- loading (takeback start to contact)
        load = slice(take, contact + 1)
        knee_dom = _angle(w[:, d["hip"]], w[:, d["kn"]], w[:, d["an"]])
        knee_off = _angle(w[:, o["hip"]], w[:, o["kn"]], w[:, o["an"]])
        deepest = min(knee_dom[load].min(), knee_off[load].min())
        flex_status = "good" if deepest <= 140 else "ok" if deepest <= 155 else "work"
        add("knee_bend_dom", f"Deepest knee bend, {self.hand} leg (180 = straight)", round(float(knee_dom[load].min())), "deg", "Loading",
            typical="110-145", status=flex_status)
        add("knee_bend_off", "Deepest knee bend, other leg", round(float(knee_off[load].min())), "deg", "Loading", typical="110-145")
        ankle_gap = np.linalg.norm(xy[:, P.L_ANKLE] - xy[:, P.R_ANKLE], axis=1) * self.m_per_px
        shoulder_w = np.median(np.linalg.norm(w[:, P.L_SHOULDER] - w[:, P.R_SHOULDER], axis=1))
        add("stance_width", "Stance width at contact", round(float(ankle_gap[contact] / max(shoulder_w, 0.2)), 1), "x shoulders", "Loading",
            typical="1.5-2.5", note=f"{ankle_gap[contact]:.2f} m between the ankles as seen by the camera.")
        swing_sign = np.sign(self.shoulder_angle[contact] - self.shoulder_angle[back]) or 1.0
        u = self._hitting_direction(contact)
        sh_turn = self._turn(back, u, P.L_SHOULDER, P.R_SHOULDER, stroke)
        hip_turn = self._turn(back, u, P.L_HIP, P.R_HIP, stroke)
        if stroke != "serve/overhead":
            add("shoulder_turn", "Shoulder turn at end of backswing (90 = side-on to the shot)", round(sh_turn), "deg", "Loading",
                typical="90-110", status="good" if sh_turn >= 80 else "ok" if sh_turn >= 55 else "work",
                note="Measured against the direction the hand travels into contact. Single-camera estimate, +/-15 deg.")
            add("hip_turn", "Hip turn at end of backswing", round(hip_turn), "deg", "Loading", typical="45-80")
            sep_val = sh_turn - hip_turn
            add("separation", "Hip-shoulder separation at end of backswing (coil)", round(sep_val), "deg", "Loading", typical="20-40",
                status="good" if sep_val >= 20 else "ok" if sep_val >= 8 else "work",
                note="Shoulders wound back further than the hips stores energy for the swing.")

        # --- forward swing
        window = slice(max(back - int(0.1 * fps), 0), contact + 1)
        base = window.start

        def peak_of(series: np.ndarray, signed: bool) -> tuple[float, int]:
            seg = series[window] * (swing_sign if signed else 1.0)
            k = int(np.argmax(seg))
            return float(seg[k]), base + k

        pel_v, pel_i = peak_of(self.pelvis_vel, True)
        sho_v, sho_i = peak_of(self.shoulder_vel, True)
        arm_v, arm_i = peak_of(self.upper_arm_vel, False)
        fore_v, fore_i = peak_of(self.forearm_vel, False)
        hand_v, hand_i = peak_of(self.hand_speed, False)
        swing.sequence = [
            dict(segment="Hips", peak=round(pel_v), unit="deg/s", t=float(t[pel_i])),
            dict(segment="Shoulders", peak=round(sho_v), unit="deg/s", t=float(t[sho_i])),
            dict(segment="Upper arm", peak=round(arm_v), unit="deg/s", t=float(t[arm_i])),
            dict(segment="Forearm", peak=round(fore_v), unit="deg/s", t=float(t[fore_i])),
            dict(segment="Hand", peak=round(hand_v, 1), unit="m/s", t=float(t[hand_i])),
        ]
        for s in swing.sequence:
            s["ms_before_contact"] = round((times["contact"] - s["t"]) * 1000)
        tol = max(2, int(round(0.035 * fps)))   # frame-rate limit on what order can be resolved
        chain = [pel_i, sho_i, max(arm_i, fore_i)]
        worst = max(chain[0] - chain[1], chain[1] - chain[2])
        order = "in order" if worst <= 0 else "in order (within frame-rate limits)" if worst <= tol else "out of order"
        add("sequence", "Kinetic chain order (hips, shoulders, arm)", order, "", "Forward swing",
            typical="hips peak first, arm last", status="work" if worst > tol else "good",
            note="Each segment should reach top speed after the one below it. Higher frame rates (120/240 fps) resolve this better.")
        add("hip_rotation_speed", "Peak hip rotation speed", round(pel_v), "deg/s", "Forward swing", typical="300-600")
        add("shoulder_rotation_speed", "Peak shoulder rotation speed", round(sho_v), "deg/s", "Forward swing", typical="500-900")
        add("hand_speed_peak", "Peak hand speed", round(hand_v, 1), "m/s", "Forward swing",
            note=f"{hand_v * 2.237:.0f} mph, measured across the camera view. Racket-head speed is higher (not tracked yet).")
        add("hand_speed_contact", "Hand speed at contact", round(float(self.hand_speed[contact]), 1), "m/s", "Contact",
            status="good" if self.hand_speed[contact] >= 0.9 * hand_v else "ok",
            note="Should still be near peak: accelerating through the ball, not slowing into it.")
        a, b = max(contact - 2, 0), min(contact + 2, len(t) - 1)
        dxy = xy[b, d["wr"]] - xy[a, d["wr"]]
        path_angle = float(np.degrees(np.arctan2(-dxy[1], abs(dxy[0]) + 1e-9)))
        if stroke != "serve/overhead":
            add("swing_path", "Swing path through contact (up from level)", round(path_angle), "deg", "Contact", typical="15-45 for topspin",
                status="good" if 15 <= path_angle <= 45 else "ok" if 5 <= path_angle < 15 else "work" if path_angle < 5 else "ok",
                note="Low-to-high angle of the hand. Flatter than 15 gives a driven ball with less spin and net clearance.")
        path = np.linalg.norm(np.diff(xy[back:contact + 1, d["wr"]], axis=0), axis=1).sum() * self.m_per_px
        add("swing_length", "Hand travel, backswing to contact", round(float(path), 2), "m", "Forward swing", typical="1.2-2.0 on a full forehand")

        # --- contact
        elbow = _angle(w[:, d["sh"]], w[:, d["el"]], w[:, d["wr"]])
        el = float(elbow[contact])
        style = "straight arm" if el >= 155 else "double bend" if el >= 100 else "cramped"
        add("elbow_contact", "Hitting elbow angle at contact", round(el), "deg", "Contact", typical="100-150 double bend or 160-180 straight arm",
            status="work" if el < 100 else "info", note=f"{style.capitalize()}. Both bent and straight styles work; under 100 means the ball got too close.")
        contact_h = float((self.ground_y[contact] - xy[contact, d["wr"], 1]) * self.m_per_px)
        frac = contact_h / self.height_m
        zone = ("above the shoulders" if frac > 0.82 else "chest high" if frac > 0.66 else "waist high" if frac > 0.5
                else "thigh high" if frac > 0.36 else "knee high or lower")
        if stroke == "serve/overhead":
            add("contact_height", "Contact height (hand above ground)", round(contact_h, 2), "m", "Contact",
                typical="about 1.35-1.5x your height at the hand", note=f"{frac:.2f}x body height. Higher is better: full reach.",
                status="good" if frac >= 1.2 else "ok" if frac >= 1.1 else "work")
        else:
            add("contact_height", "Contact height (hand above ground)", round(contact_h, 2), "m", "Contact", typical="waist to chest",
                status="good" if 0.5 < frac <= 0.82 else "ok", note=f"{zone.capitalize()} ({frac:.0%} of body height).")
        chest_mid = (w[contact, P.L_SHOULDER] + w[contact, P.R_SHOULDER]) / 2
        hip_mid = (w[contact, P.L_HIP] + w[contact, P.R_HIP]) / 2
        front_hip = max((P.L_HIP, P.R_HIP), key=lambda h: float(np.dot(w[contact, h][[0, 2]], u)))
        rel = (w[contact, d["wr"]] - w[contact, front_hip])[[0, 2]]
        ahead = float(np.dot(rel, u))
        spacing = float(abs(np.dot((w[contact, d["wr"]] - hip_mid)[[0, 2]], np.array([-u[1], u[0]]))))
        if stroke != "serve/overhead":
            add("contact_in_front", "Contact point ahead of the front hip", round(ahead * 100), "cm", "Contact", typical="20-50",
                status="good" if ahead >= 0.2 else "ok" if ahead >= 0.05 else "work",
                note="Along the hitting line. Meeting the ball out in front lets body weight go through it.")
            add("contact_spacing", "Spacing: hand out to the side of the body", round(spacing * 100), "cm", "Contact", typical="35-70",
                status="good" if 0.35 <= spacing <= 0.75 else "ok",
                note="Small means jammed, very large means reaching.")
            sh_contact = self._turn(contact, u, P.L_SHOULDER, P.R_SHOULDER, stroke)
            add("shoulders_at_contact", "Shoulder angle at contact (0 = facing the target)", round(sh_contact), "deg", "Contact", typical="0-40",
                note="How much rotation is still left when the ball is struck.")
        trunk = chest_mid - hip_mid
        lean = float(np.degrees(np.arccos(np.clip(-trunk[1] / (np.linalg.norm(trunk) + 1e-9), -1, 1))))
        add("trunk_lean", "Trunk lean from vertical at contact", round(lean), "deg", "Contact", typical="0-20 on a groundstroke",
            status="good" if lean <= 20 else "ok" if lean <= 30 else "work", note="Large lean usually means reaching or falling off the shot.")
        k0, k1 = max(contact - int(0.1 * fps), 0), min(contact + int(0.1 * fps), len(t) - 1)
        head = xy[k0:k1 + 1, P.NOSE]
        head_move = float(np.linalg.norm(head.max(axis=0) - head.min(axis=0)) * self.m_per_px * 100)
        add("head_stability", "Head movement around contact (0.2 s)", round(head_move), "cm", "Contact", typical="under 8 when set; more on the run",
            status="good" if head_move <= 8 else "ok" if head_move <= 15 else "work", note="A quiet head keeps the eyes on the ball.")
        hip_x = mid_hip[contact, 0]
        ax = sorted([xy[contact, P.L_ANKLE, 0], xy[contact, P.R_ANKLE, 0]])
        base_w = max(ax[1] - ax[0], 1.0)
        centre = float((hip_x - ax[0]) / base_w)
        add("balance", "Hips over the base at contact (50% = centred)", round(centre * 100), "%", "Contact", typical="30-70",
            status="good" if 0.3 <= centre <= 0.7 else "ok" if 0.1 <= centre <= 0.9 else "work",
            note="Where the hips sit between the two feet. Outside 0-100 means the hips are past a foot.")
        drive = float(knee_dom[contact] - knee_dom[load].min())
        add("leg_drive", f"Leg drive: {self.hand} knee extension into contact", round(drive), "deg", "Forward swing", typical="15-40",
            status="good" if drive >= 15 else "ok" if drive >= 5 else "work", note="Legs straightening is where the swing starts.")
        shift = (mid_hip[contact] - mid_hip[back]) * self.m_per_px
        add("weight_shift", "Hip travel during forward swing", round(float(np.linalg.norm(shift)), 2), "m", "Forward swing",
            note=f"Hips rose {-shift[1] * 100:+.0f} cm. Large sideways travel means the ball was hit on the move.")
        rot_to_contact = float((self.shoulder_angle[contact] - self.shoulder_angle[back]) * swing_sign)
        add("shoulder_rotation", "Shoulder rotation, backswing to contact", round(rot_to_contact), "deg", "Forward swing", typical="70-110")

        # --- follow-through
        opp_shoulder_y = xy[finish, o["sh"], 1]
        finish_h = float((opp_shoulder_y - xy[finish, d["wr"], 1]) * self.m_per_px * 100)
        if stroke != "serve/overhead":
            add("finish_height", "Finish: hand relative to opposite shoulder", round(finish_h), "cm", "Follow-through", typical="-10 to +20",
                status="good" if finish_h >= -10 else "ok" if finish_h >= -30 else "work",
                note="Positive is above the shoulder. A low finish goes with a flat swing path.")
        follow = np.linalg.norm(np.diff(xy[contact:finish + 1, d["wr"]], axis=0), axis=1).sum() * self.m_per_px
        add("follow_length", "Hand travel after contact", round(float(follow), 2), "m", "Follow-through", typical="1.0 or more",
            status="good" if follow >= 1.0 else "ok" if follow >= 0.6 else "work", note="A full follow-through means no braking before the ball.")
        rot_after = float((self.shoulder_angle[finish] - self.shoulder_angle[contact]) * swing_sign)
        add("rotation_after", "Shoulder rotation after contact", round(rot_after), "deg", "Follow-through", typical="30-70")

        swing.findings = self._findings(swing)
        return swing

    def _findings(self, swing: Swing) -> list[dict]:
        strengths = [dict(kind="strength", text=f"{m.label}: {m.value} {m.unit}".strip() + (f". {m.note}" if m.note else ""))
                     for m in swing.metrics if m.status == "good"]
        work = [dict(kind="work", text=f"{m.label}: {m.value} {m.unit} (typical {m.typical}). {m.note}".strip())
                for m in swing.metrics if m.status == "work"]
        return strengths + work

    # ---- whole clip --------------------------------------------------------
    def analyze(self) -> list[Swing]:
        peaks = self.find_swings()
        n = len(self.t)
        swings = []
        for k, peak in enumerate(peaks):
            lo = 0 if k == 0 else (peaks[k - 1] + peak) // 2
            hi = n - 1 if k == len(peaks) - 1 else (peak + peaks[k + 1]) // 2
            hi = min(hi, peak + int(1.2 * self.fps))
            swings.append(self.analyze_swing(k + 1, peak, lo, hi))
        return swings

    def series(self) -> dict:
        """Time series for charts."""
        d, w = self.dom, self.world
        r = lambda a, nd=1: [round(float(x), nd) for x in a]
        return dict(
            t=r(self.t, 3), hand_speed=r(self.hand_speed, 2),
            hip_rotation_speed=r(np.abs(self.pelvis_vel), 0), shoulder_rotation_speed=r(np.abs(self.shoulder_vel), 0),
            elbow=r(_angle(w[:, d["sh"]], w[:, d["el"]], w[:, d["wr"]]), 0),
            knee=r(_angle(w[:, d["hip"]], w[:, d["kn"]], w[:, d["an"]]), 0),
            separation=r(self.shoulder_angle - self.pelvis_angle, 0),
        )


def session_summary(swings: list[Swing]) -> dict:
    """Averages and consistency across the swings in one clip."""
    by_stroke: dict[str, list[Swing]] = {}
    for s in swings:
        by_stroke.setdefault(s.stroke, []).append(s)
    out = {}
    for stroke, group in by_stroke.items():
        rows = {}
        for key in ("hand_speed_peak", "swing_path", "elbow_contact", "contact_height", "contact_in_front", "knee_bend_dom",
                    "separation", "head_stability", "forward_swing_time"):
            vals = [s.metric(key) for s in group if isinstance(s.metric(key), (int, float))]
            if vals:
                rows[key] = dict(mean=round(float(np.mean(vals)), 2), sd=round(float(np.std(vals)), 2),
                                 min=round(float(np.min(vals)), 2), max=round(float(np.max(vals)), 2))
        out[stroke] = dict(count=len(group), metrics=rows)
    return out
