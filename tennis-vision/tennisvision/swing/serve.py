"""Serve analysis: find each serve, time its parts, measure them, and estimate the serve type.

Parts of the serve: start, toss release, trophy position, racket drop, contact, finish.
Benchmarks: the trophy-position ranges follow a 2024 meta-analysis of serve kinematics (front knee bent about
65 degrees, trunk tilted about 25 degrees). The flat / slice / kick differences follow motion-capture work showing
the kick serve swings most sideways and upward and the flat serve most forward.
"""
from __future__ import annotations

import numpy as np
from scipy.signal import find_peaks

from .. import pose as P
from ..pose import PoseSequence
from .analyze import Metric, Swing, SwingAnalyzer, _angle
from .coach import coach
from .confidence import assess
from .serve_coach import SERVE_BOOK

SERVE_PHASES = [["start", "Start"], ["toss", "Toss"], ["trophy", "Trophy"], ["racket_drop", "Racket drop"],
                ["contact", "Contact"], ["finish", "Finish"]]
RACKET_REACH_M = 0.48            # hand to the middle of the strings
# suggested contact and swing for each serve type: (contact in front cm, contact to the hitting side of the head cm, upward swing deg)
TYPE_TARGETS = {
    "flat": dict(front=(30, 70), side=(10, 40), up=(0, 25)),
    "slice": dict(front=(20, 60), side=(25, 60), up=(5, 30)),
    "kick": dict(front=(0, 35), side=(-15, 20), up=(30, 60)),
}


def serve_hand(seq: PoseSequence) -> str:
    """The hitting hand on a serve is the one that reaches its highest point last (the toss arm goes up first)."""
    best, latest = "right", -1
    for name, wrist, shoulder in (("right", P.R_WRIST, P.R_SHOULDER), ("left", P.L_WRIST, P.L_SHOULDER)):
        above = seq.xy[:, shoulder, 1] - seq.xy[:, wrist, 1]
        k = int(np.argmax(above))
        if above[k] > 0 and k > latest:
            best, latest = name, k
    return best


def _status(value: float, good, ok) -> str:
    """good and ok are (low, high) ranges."""
    if good[0] <= value <= good[1]:
        return "good"
    return "ok" if ok[0] <= value <= ok[1] else "work"


class ServeAnalyzer:
    def __init__(self, an: SwingAnalyzer, declared_type: str = "auto"):
        self.an = an
        self.declared = declared_type if declared_type in TYPE_TARGETS else "auto"
        self.hit = an.dom
        self.toss = an.off
        self.lead = "left" if an.hand == "right" else "right"       # the front foot on a serve is opposite the hitting hand
        self.trail = an.hand
        self.leg = {"left": (P.L_HIP, P.L_KNEE, P.L_ANKLE), "right": (P.R_HIP, P.R_KNEE, P.R_ANKLE)}
        xy = an.xy
        self.stature_px = an.height_m / an.m_per_px
        self.height_of = lambda joint, ground: (ground - xy[:, joint, 1]) * an.m_per_px

    # ---- finding serves ----------------------------------------------------
    def find(self) -> list[int]:
        """Frames where the hitting hand peaks well above the head."""
        an = self.an
        above_head = (an.xy[:, P.NOSE, 1] - an.xy[:, self.hit["wr"], 1]) / self.stature_px
        peaks, _ = find_peaks(above_head, height=0.08, distance=max(1, int(1.5 * an.fps)), prominence=0.15)
        return peaks.tolist()

    def _contact(self, peak: int) -> tuple[int, str]:
        an = self.an
        delay = an.distance_m / 343.0
        # the top of the reach is a strong cue on its own; the hit sound may only nudge it by a frame or two
        near = [(s - delay, k) for s, k in an.sounds if abs(s - delay - an.t[peak]) <= 0.05]
        if near:
            t_hit = max(near, key=lambda c: c[1])[0]
            return int(np.argmin(np.abs(an.t - t_hit))), "audio+pose"
        return peak, "pose"

    # ---- one serve ---------------------------------------------------------
    def analyze(self, index: int, peak: int, lo: int, hi: int) -> Swing:
        an, xy, w, t, fps = self.an, self.an.xy, self.an.world, self.an.t, self.an.fps
        hit, toss = self.hit, self.toss
        n = len(t)
        contact, source = self._contact(peak)
        ground = float(np.median(an.ground_y[max(lo, contact - int(2.5 * fps)):max(lo + 1, contact - int(0.8 * fps))]))
        hit_h, toss_h = self.height_of(hit["wr"], ground), self.height_of(toss["wr"], ground)
        head_h = self.height_of(P.NOSE, ground)

        # phases
        search_lo = max(lo, contact - int(1.2 * fps))
        toss_peak = search_lo + int(np.argmax(toss_h[search_lo:contact + 1]))
        toss_shoulder_h = self.height_of(toss["sh"], ground)
        release = toss_peak
        while release > max(lo, toss_peak - int(1.0 * fps)) and toss_h[release - 1] >= toss_shoulder_h[release - 1]:
            release -= 1                                                   # the tossing hand passing shoulder height on the way up
        lift_lo = max(lo, release - int(1.0 * fps))
        start = lift_lo + int(np.argmin(toss_h[lift_lo:release + 1]))      # tossing hand at its lowest: the lift begins here
        knee = {side: _angle(w[:, h], w[:, k], w[:, a]) for side, (h, k, a) in self.leg.items()}
        bend_window = slice(release, max(release + 1, contact - max(1, int(0.08 * fps))))
        both = knee[self.lead][bend_window] + knee[self.trail][bend_window]
        deepest = release + int(np.argmin(both)) if len(both) else toss_peak
        knee_range = float(knee[self.lead][bend_window].max() - knee[self.lead][bend_window].min()) if len(both) else 0.0
        # trophy: knees at their deepest with the tossing arm fully up, whichever comes later
        trophy = max(deepest, toss_peak) if knee_range >= 6 else toss_peak
        trophy = int(np.clip(trophy, release, contact - max(2, int(0.1 * fps))))
        drop_window = slice(trophy, contact)
        hit_elbow = _angle(w[:, hit["sh"]], w[:, hit["el"]], w[:, hit["wr"]])
        drop = trophy + int(np.argmin(hit_elbow[drop_window])) if contact > trophy else trophy
        drop = int(np.clip(drop, trophy, contact - 1))
        finish = min(n - 1, contact + int(0.7 * fps), hi)
        low_after = contact + int(np.argmin(hit_h[contact:finish + 1]))
        finish = max(low_after, min(contact + 2, n - 1))

        frames = dict(start=start, toss=release, trophy=trophy, racket_drop=drop, contact=contact, finish=finish)
        # keep the keys the shared renderer and reports expect
        frames.update(takeback=start, backswing_end=trophy, forward_swing=drop)
        times = {k: float(t[f]) for k, f in frames.items()}
        swing = Swing(index=index, stroke="serve", hand=an.hand, two_handed=False, times=times, frames=frames,
                      contact_source=source, phases=[list(p) for p in SERVE_PHASES])
        add = lambda *a, **k: swing.metrics.append(Metric(*a, **k))
        cm = an.m_per_px * 100

        # view: side-on if the hitting hand travels a long way across the picture during the swing
        travel_x = float(np.ptp(xy[trophy:finish + 1, hit["wr"], 0]) * an.m_per_px)
        side_on = travel_x >= 0.6
        forward = float(np.sign(xy[min(contact + 2, n - 1), hit["wr"], 0] - xy[max(contact - 2, 0), hit["wr"], 0]) or 1.0)

        # --- stance and toss
        ankle = {"left": P.L_ANKLE, "right": P.R_ANKLE}
        gap = np.linalg.norm(xy[:, P.L_ANKLE] - xy[:, P.R_ANKLE], axis=1) * an.m_per_px
        shoulder_w = float(np.median(np.linalg.norm(w[:, P.L_SHOULDER] - w[:, P.R_SHOULDER], axis=1)))
        closing = gap[trophy] / max(gap[start], 0.05)
        stance = "pinpoint" if closing < 0.6 and gap[start] - gap[trophy] > 0.12 else "platform"
        add("serve_stance", "Stance", stance, "", "Stance and toss", typical="either works",
            note="Platform: feet stay apart. Pinpoint: the back foot slides up beside the front foot before the push."
                 + ("" if side_on else " Read from this camera angle, so treat it as a guess."))
        add("serve_stance_width", "Feet apart at the start", round(float(gap[start] / max(shoulder_w, 0.2)), 1), "x shoulders",
            "Stance and toss", typical="1.0-1.6")
        toss_elbow = _angle(w[:, toss["sh"]], w[:, toss["el"]], w[:, toss["wr"]])
        straight = float(toss_elbow[release])
        add("serve_toss_arm_straight", "Tossing arm straightness at release (180 = straight)", round(straight), "deg", "Stance and toss",
            typical="160-180", status=_status(straight, (155, 181), (140, 181)),
            note="A straight arm lifts the ball like an elevator. A bent elbow flicks it and the toss wanders.")
        arm = xy[trophy, toss["wr"]] - xy[trophy, toss["sh"]]
        from_vertical = float(np.degrees(np.arctan2(abs(arm[0]), -arm[1]))) if arm[1] < 0 else 90.0 + float(np.degrees(np.arctan2(arm[1], abs(arm[0]) + 1e-9)))
        add("serve_toss_arm_up", "Tossing arm at trophy (0 = straight up)", round(from_vertical), "deg", "Stance and toss",
            typical="0-25", status=_status(from_vertical, (0, 25), (0, 45)),
            note="The tossing arm should stay up, pointing at the ball, until the racket starts to drop.")
        above = float((toss_h[drop] - head_h[drop]) * 100)
        add("serve_toss_arm_hold", "Tossing hand height when the racket drops (above the head)", round(above), "cm", "Stance and toss",
            typical="0 or more", status=_status(above, (0, 200), (-25, 200)),
            note="If the tossing arm falls early the front shoulder drops with it and the chest opens too soon.")
        add("serve_rhythm", "Toss release to contact", round(times["contact"] - times["toss"], 2), "s", "Stance and toss",
            note="Your serve tempo. The useful thing is that it stays the same from serve to serve.")

        # --- trophy position
        lead_knee = float(knee[self.lead][bend_window].min()) if len(both) else float(knee[self.lead][trophy])
        trail_knee = float(knee[self.trail][bend_window].min()) if len(both) else float(knee[self.trail][trophy])
        add("serve_knee_lead", "Lead leg: deepest knee bend (180 = straight)", round(lead_knee), "deg", "Trophy position",
            typical="100-135", status=_status(lead_knee, (80, 140), (80, 155)),
            note="The front leg. Measured players bend to about 115. Straighter legs cost racket speed.")
        add("serve_knee_trail", "Trail leg: deepest knee bend", round(trail_knee), "deg", "Trophy position", typical="100-140",
            note="The back leg loads with the front one.")
        chest = (w[trophy, P.L_SHOULDER] + w[trophy, P.R_SHOULDER]) / 2 - (w[trophy, P.L_HIP] + w[trophy, P.R_HIP]) / 2
        tilt = float(np.degrees(np.arccos(np.clip(-chest[1] / (np.linalg.norm(chest) + 1e-9), -1, 1))))
        add("serve_trunk_tilt", "Trunk tilt at trophy (from vertical)", round(tilt), "deg", "Trophy position", typical="15-35",
            status=_status(tilt, (12, 40), (5, 50)),
            note="Leaning back and away loads the trunk like a bow. Measured players average about 25.")

        def shoulder_tilt(frame: int) -> float:
            line = xy[frame, hit["sh"]] - xy[frame, toss["sh"]]
            return float(np.degrees(np.arctan2(line[1], np.hypot(line[0], shoulder_w / an.m_per_px * 0.25) + 1e-9)))

        tilt_trophy = shoulder_tilt(trophy)          # positive = hitting shoulder below the tossing shoulder
        add("serve_shoulder_tilt", "Shoulder tilt at trophy (tossing shoulder above hitting shoulder)", round(tilt_trophy), "deg",
            "Trophy position", typical="20-45", status=_status(tilt_trophy, (15, 80), (5, 80)),
            note="Front shoulder up, back shoulder down. The shoulders then swap places through contact.")
        sep = float(abs((an.shoulder_angle[trophy] - an.pelvis_angle[trophy])))
        add("serve_coil", "Hip-shoulder coil at trophy", round(sep), "deg", "Trophy position", typical="15-35",
            status="good" if sep >= 12 else "ok", note="Shoulders turned further from the net than the hips. Single-camera estimate.")
        elbow_trophy = float(hit_elbow[trophy])
        add("serve_elbow_trophy", "Hitting elbow angle at trophy", round(elbow_trophy), "deg", "Trophy position", typical="70-110",
            status=_status(elbow_trophy, (55, 125), (40, 150)), note="Roughly a right angle, racket tip up.")
        elbow_up = float((xy[trophy, hit["sh"], 1] - xy[trophy, hit["el"], 1]) * cm)
        add("serve_elbow_height", "Hitting elbow height at trophy (against the shoulder)", round(elbow_up), "cm", "Trophy position",
            typical="-8 or higher", status=_status(elbow_up, (-8, 60), (-18, 60)),
            note="The elbow should sit level with the shoulder line. A low elbow shortens the swing and loads the shoulder.")

        # --- racket drop and drive
        racket = an.racket
        drop_depth = None
        if racket is not None and racket["valid"][trophy:contact + 1].sum() >= 2:
            head_y = np.where(racket["valid"], racket["head"][:, 1], np.nan)
            below = (head_y[trophy:contact + 1] - xy[trophy:contact + 1, hit["wr"], 1]) * cm
            if np.isfinite(below).any():
                drop_depth = float(np.nanmax(below))
        if drop_depth is not None:
            share = drop_depth / (an.height_m * 100)
            add("serve_racket_drop", "Racket drop: racket head below the hand at its lowest", round(drop_depth), "cm",
                "Racket drop and leg drive", typical=f"{round(0.17 * an.height_m * 100)} or more",
                status=_status(share, (0.17, 1.0), (0.08, 1.0)),
                note="A deep drop gives the racket a long runway up to the ball. Read from the racket's outline.")
        bend = float(hit_elbow[drop])
        add("serve_elbow_drop", "Hitting elbow bend at racket drop", round(bend), "deg", "Racket drop and leg drive", typical="50-90",
            status=_status(bend, (30, 95), (30, 115)), note="A tightly folded elbow, pointing up, means the racket has dropped behind the back.")
        for side, key, label in ((self.lead, "serve_leg_drive_lead", "Lead leg"), (self.trail, "serve_leg_drive_trail", "Trail leg")):
            deep = float(knee[side][bend_window].min()) if len(both) else float(knee[side][trophy])
            drive = float(knee[side][contact] - deep)
            graded = dict(status=_status(drive, (20, 120), (8, 120))) if side == self.lead else {}
            add(key, f"{label}: push from deepest bend to contact", round(drive), "deg", "Racket drop and leg drive", typical="20-60",
                note="How far the leg straightens as it drives up into the ball.", **graded)
        hip_h = self.height_of(P.L_HIP, ground) / 2 + self.height_of(P.R_HIP, ground) / 2
        rise = float((hip_h[contact] - hip_h[bend_window].min()) * 100) if len(both) else 0.0
        add("serve_rise", "Hips rising from the deepest bend to contact", round(rise), "cm", "Racket drop and leg drive", typical="15-40",
            status=_status(rise, (15, 120), (6, 120)), note="The legs should throw the body up toward the ball.")
        feet_h = (ground - an.ground_y) * cm
        air = float(feet_h[max(contact - 2, 0):min(contact + 3, n)].max())
        add("serve_feet_off", "Feet off the ground at contact", round(max(air, 0.0)), "cm", "Racket drop and leg drive", typical="5-30",
            note="A sign of full leg drive. Not required for a sound serve.")

        # --- contact
        near = slice(max(contact - 1, 0), min(contact + 2, n))       # at 30 frames a second contact can fall between frames
        reach = float(hit_h[near].max())
        ratio = reach / an.height_m
        add("serve_contact_height", "Hand height at contact", round(ratio, 2), "x height", "Contact", typical="1.18 or more",
            status=_status(ratio, (1.18, 2.0), (1.08, 2.0)),
            note=f"{reach:.2f} m at the hand, so the ball is met at about {reach + RACKET_REACH_M:.2f} m. Full reach is the goal.")
        elbow_contact = float(hit_elbow[near].max())
        add("serve_elbow_contact", "Hitting arm at contact (180 = straight)", round(elbow_contact), "deg", "Contact", typical="155-180",
            status=_status(elbow_contact, (155, 181), (140, 181)), note="Reach up with a long arm. A bent elbow lowers contact and costs speed.")
        tilt_contact = -shoulder_tilt(contact)       # positive = hitting shoulder above the tossing shoulder
        add("serve_shoulder_over", "Shoulder over shoulder at contact (hitting shoulder above)", round(tilt_contact), "deg", "Contact",
            typical="25-55", status=_status(tilt_contact, (20, 85), (8, 85)),
            note="The shoulders should have swapped: hitting shoulder high, tossing shoulder low.")
        a = max(contact - max(2, int(round(0.07 * fps))), 0)
        step = xy[contact, hit["wr"]] - xy[a, hit["wr"]]
        up_angle = float(np.degrees(np.arctan2(-step[1], abs(step[0]) + 1e-9)))
        front_cm = side_cm = None
        if side_on:
            front_cm = float((xy[contact, hit["wr"], 0] - xy[contact, ankle[self.lead], 0]) * forward * cm)
        else:
            head_x = xy[contact, P.NOSE, 0]
            hitting_side = 1.0 if (xy[contact, hit["sh"], 0] - xy[contact, toss["sh"], 0]) >= 0 else -1.0
            side_cm = float((xy[contact, hit["wr"], 0] - head_x) * hitting_side * cm)
        estimate, confidence, basis = self._serve_type(up_angle, front_cm, side_cm)
        kind = self.declared if self.declared != "auto" else estimate
        target = TYPE_TARGETS[kind]
        if front_cm is not None:
            lo_f, hi_f = target["front"]
            add("serve_contact_front", "Contact in front of the lead foot (into the court)", round(front_cm), "cm", "Contact",
                typical=f"{lo_f}-{hi_f} for a {kind} serve", status=_status(front_cm, (lo_f, hi_f + 15), (lo_f - 20, hi_f + 40)),
                note="Where the hand is at contact, measured along the court from the front foot. Flat serves are met furthest in front, kick serves closest to the head.")
        if side_cm is not None:
            lo_s, hi_s = target["side"]
            add("serve_contact_side", "Contact to the hitting side of the head", round(side_cm), "cm", "Contact",
                typical=f"{lo_s} to {hi_s} for a {kind} serve", status=_status(side_cm, (lo_s - 5, hi_s + 5), (lo_s - 25, hi_s + 25)),
                note="Kick serves are met over or behind the head, slice serves furthest out to the hitting side.")
        lo_u, hi_u = target["up"]
        add("serve_swing_up", "Hand path into contact (up from level)", round(up_angle), "deg", "Contact",
            typical=f"{lo_u}-{hi_u} for a {kind} serve",
            note="Flat serves go mostly forward through the ball. Kick serves brush steeply upward.")
        window = slice(drop, min(contact + 2, n))
        add("serve_hand_speed", "Peak hand speed", round(float(an.hand_speed[window].max()), 1), "m/s", "Contact",
            note=f"{float(an.hand_speed[window].max()) * 2.237:.0f} mph across the camera view. At 30 frames a second a serve blurs, so this reads low; film in slow-motion for a truer number.")
        if an.racket_speed is not None and np.isfinite(an.racket_speed[window]).sum() >= 2:
            head_peak = float(np.nanmax(an.racket_speed[window]))
            add("serve_racket_speed", "Racket-head speed, peak (estimate)", round(head_peak, 1), "m/s", "Contact", typical="35-45 at a high level",
                note=f"{head_peak * 2.237:.0f} mph. A floor, for the same reason as hand speed.")
        add("serve_type", "Serve type", kind, "", "Contact",
            note=("You told us this was a " + kind + " serve." if self.declared != "auto"
                  else f"Our read from the swing: {estimate} ({confidence} confidence). {basis}"))

        # --- finish and landing
        hips_x = (xy[:, P.L_HIP, 0] + xy[:, P.R_HIP, 0]) / 2
        if side_on:
            into_court = float((hips_x[finish] - hips_x[trophy]) * forward * cm)
            add("serve_into_court", "Body travel into the court (trophy to finish)", round(into_court), "cm", "Finish and landing",
                typical="30-90", status=_status(into_court, (30, 250), (10, 250)),
                note="A serve should carry you forward into the court, landing on the front foot.")
        down = float((hit_h[contact] - hit_h[finish]) * 100)
        add("serve_follow_through", "Follow-through: hand drop after contact", round(down), "cm", "Finish and landing", typical="90 or more",
            status=_status(down, (90, 400), (50, 400)), note="The racket should finish down across the body, not stop up high.")

        swing.serve = dict(type=kind, declared=self.declared, estimate=estimate, confidence=confidence, basis=basis,
                           view="side-on" if side_on else "behind or front-on", stance=stance, lead=self.lead, targets=TYPE_TARGETS)
        assess(swing, an)
        swing.coaching = coach(swing.metrics, "serve", SERVE_BOOK)
        return swing

    @staticmethod
    def _serve_type(up_angle: float, front_cm: float | None, side_cm: float | None) -> tuple[str, str, str]:
        """Rough read of flat / slice / kick from the swing direction and where the ball was met."""
        if up_angle >= 32 and (front_cm is None or front_cm <= 35):
            return "kick", "medium" if up_angle >= 42 else "low", f"The hand was travelling {up_angle:.0f} degrees upward into contact, which is a brushing, kick-serve swing."
        if side_cm is not None and side_cm >= 30:
            return "slice", "low", f"The ball was met {side_cm:.0f} cm out to the hitting side, where a slice serve is struck."
        if front_cm is not None and front_cm >= 30 and up_angle <= 25:
            return "flat", "medium", f"The ball was met {front_cm:.0f} cm in front with the hand moving forward more than up."
        return "flat", "low", "Nothing in the swing pointed clearly to spin, so this is read as a flat serve. One camera cannot see spin directly."

    def analyze_all(self) -> list[Swing]:
        peaks = self.find()
        n = len(self.an.t)
        out = []
        for k, peak in enumerate(peaks):
            lo = 0 if k == 0 else (peaks[k - 1] + peak) // 2
            hi = n - 1 if k == len(peaks) - 1 else (peak + peaks[k + 1]) // 2
            out.append(self.analyze(k + 1, peak, lo, hi))
        return out
