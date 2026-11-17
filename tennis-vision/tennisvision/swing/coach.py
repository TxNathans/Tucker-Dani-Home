"""Coaching layer: turn swing measurements into feedback a beginner can act on and a coach can check.

Every fix has the same parts: what we saw (plain words), why it matters, one cue to think about, one drill,
and the measurement behind it for coaches.
"""
from __future__ import annotations

from .cues import cue_for

CATEGORIES = [
    ("feet", "Feet and stance", ("stance_type", "front_foot_angle", "back_foot_angle", "back_foot_pivot", "step_in", "stance_width")),
    ("load", "Turn and load", ("prep_time", "shoulder_turn", "separation", "knee_bend_dom", "leg_drive", "sequence")),
    ("through", "Through the ball", ("extension", "speed_carried", "weight_through", "chest_lead", "swing_path", "racket_drop")),
    ("contact", "Contact point", ("contact_in_front", "contact_spacing", "contact_height", "elbow_contact")),
    ("balance", "Balance", ("trunk_lean", "head_stability", "balance")),
    ("finish", "Finish", ("follow_length", "finish_height")),
]
POINTS = {"good": 100, "ok": 70, "work": 35}
SITUATIONAL = {"trunk_lean", "head_stability", "balance", "contact_spacing", "contact_height", "follow_length", "finish_height"}


GRADE_WORDS = {"strength": "Strength", "on_target": "On target", "building": "Building", "priority": "Priority",
               "not_graded": "Not graded"}

# What is off, said to the player in one short line. Shown as the headline for the thing to work on.
PROBLEMS = {
    "contact_in_front": lambda v: "You're meeting the ball too close to your body.",
    "extension": lambda v: "Your swing stops short of the target.",
    "speed_carried": lambda v: "Your swing slows down right at the ball.",
    "weight_through": lambda v: "Your weight is falling back off the shot.",
    "chest_lead": lambda v: "You're leaning back at contact.",
    "shoulder_turn": lambda v: "Your shoulders don't turn far enough.",
    "separation": lambda v: "Your shoulders and hips turn as one piece.",
    "knee_bend_dom": lambda v: "Your legs stay straight.",
    "leg_drive": lambda v: "Your legs don't push into the shot.",
    "front_foot_angle": lambda v: "Your front foot blocks your hips.",
    "back_foot_angle": lambda v: "Your back foot doesn't set the turn.",
    "back_foot_pivot": lambda v: "Your back foot stays stuck to the court.",
    "trunk_lean": lambda v: "Your upper body tips over at contact.",
    "head_stability": lambda v: "Your head moves as you hit.",
    "balance": lambda v: "Your hips drift outside your feet.",
    "swing_path": lambda v: "Your swing comes through too flat.",
    "racket_drop": lambda v: "Your racket doesn't get under the ball.",
    "contact_spacing": lambda v: "You're crowding the ball." if v < 35 else "You're reaching for the ball.",
    "elbow_contact": lambda v: "Your hitting arm is jammed.",
    "follow_length": lambda v: "Your swing stops right after the ball.",
    "finish_height": lambda v: "Your swing finishes low.",
    "prep_time": lambda v: "Your racket gets back late.",
    "sequence": lambda v: "Your arm starts before your hips.",
}

# key -> (meter start, meter end, target low, target high)
METERS = {
    "contact_in_front": (-20, 70, 20, 50), "extension": (0, 90, 40, 70), "speed_carried": (30, 110, 75, 105),
    "weight_through": (-15, 35, 5, 25), "chest_lead": (-20, 35, 0, 20), "shoulder_turn": (0, 130, 90, 110),
    "hip_turn": (0, 110, 45, 80), "separation": (-10, 50, 20, 40), "knee_bend_dom": (90, 180, 110, 145),
    "knee_bend_off": (90, 180, 110, 145), "leg_drive": (0, 50, 15, 40), "front_foot_angle": (0, 130, 20, 70),
    "back_foot_angle": (0, 180, 60, 120), "back_foot_pivot": (-10, 100, 30, 90), "step_in": (-10, 80, 20, 60),
    "stance_width": (0.5, 3.5, 1.5, 2.5), "swing_path": (-10, 70, 15, 45), "racket_drop": (0, 70, 20, 50),
    "contact_height": (0.2, 1.6, 0.85, 1.35), "contact_spacing": (0, 100, 35, 70), "elbow_contact": (60, 180, 100, 180),
    "shoulders_at_contact": (-20, 90, 0, 40), "trunk_lean": (0, 50, 0, 20), "head_stability": (0, 30, 0, 8),
    "balance": (-20, 120, 30, 70), "follow_length": (0, 2.2, 1.0, 2.0), "finish_height": (-60, 40, -10, 20),
    "prep_time": (0, 1.5, 0.6, 1.3), "forward_swing_time": (0, 0.6, 0.15, 0.35), "tempo_ratio": (0, 5, 2, 4),
    "hip_rotation_speed": (0, 800, 300, 600), "shoulder_rotation_speed": (0, 1100, 500, 900),
    "racket_head_speed": (0, 40, 25, 35), "shoulder_rotation": (0, 130, 70, 110), "rotation_after": (0, 90, 30, 70),
    "swing_length": (0, 2.5, 1.2, 2.0),
    "lead_knee_back": (90, 180, 120, 160), "lead_knee_contact": (90, 180, 135, 175), "lead_brace": (-30, 50, 5, 30),
    "trail_knee_back": (90, 180, 110, 145), "trail_knee_contact": (90, 180, 130, 170), "trail_drive": (0, 50, 15, 40),
    "weight_on_lead_back": (0, 100, 25, 50), "weight_on_lead": (0, 120, 55, 85),
    "racket_angle_back": (-30, 90, 20, 80), "racket_angle_low": (-90, 30, -90, -20), "racket_angle_contact": (-60, 60, -25, 15),
    "racket_lag": (0, 120, 50, 90), "approach_angle": (-10, 70, 15, 35), "swing_plane": (0, 90, 20, 45),
}

# A number this far past its target counts as a strength rather than just on target: key -> (direction, value)
STRENGTH_AT = {
    "contact_in_front": (1, 35), "extension": (1, 55), "speed_carried": (1, 90), "shoulder_turn": (1, 95), "separation": (1, 30),
    "knee_bend_dom": (-1, 125), "head_stability": (-1, 4), "step_in": (1, 30), "leg_drive": (1, 25), "follow_length": (1, 1.4),
    "weight_through": (1, 12), "back_foot_pivot": (1, 45), "racket_drop": (1, 30), "trunk_lean": (-1, 8),
}


def grade_of(key: str, value, status: str, situational: bool = False, strength_at: dict | None = None,
             confidence: str = "high") -> str:
    """The five grades used everywhere: strength, on_target, building, priority, not_graded.

    A number the camera could not see clearly is not graded. A number that is an estimate can be Building but never
    Priority: the one thing a player is told to fix first has to rest on something seen directly.
    """
    if confidence == "low":
        return "not_graded"
    if status == "work":
        return "building" if situational or confidence != "high" else "priority"
    if status == "ok":
        return "building"
    if status != "good":
        return "not_graded"
    rule = (STRENGTH_AT if strength_at is None else strength_at).get(key)
    if rule and isinstance(value, (int, float)) and (value - rule[1]) * rule[0] >= 0:
        return "strength"
    return "on_target"


def off_target(key: str, value) -> float | None:
    """How far a value sits outside its target range, as a share of the meter. 0 = inside the range."""
    if key not in METERS or not isinstance(value, (int, float)):
        return None
    lo_m, hi_m, lo, hi = METERS[key]
    gap = lo - value if value < lo else value - hi if value > hi else 0.0
    return gap / (hi_m - lo_m)


def _inches(cm: float) -> str:
    return f"{abs(cm) / 2.54:.0f} inches"


# key -> (priority, builder). The builder gets the metric value and stroke and returns the card text.
def _tips() -> dict:
    return {
        "contact_in_front": (10, lambda v, s: dict(
            title="Meet the ball further in front",
            saw=f"You made contact {'level with' if v <= 3 else 'only ' + _inches(v) + ' ahead of'} your front hip, so the ball got in on you.",
            why="When the ball gets beside or behind you, the arm does all the work and the racket face opens. Out in front, your whole body is behind the shot.",
            cue="Catch it early. Reach out and meet the ball where you could shake someone's hand.",
            drill="Drop-feed yourself and freeze at contact. Check the racket is ahead of your front foot before you finish the swing. 10 balls.")),
        "extension": (9, lambda v, s: dict(
            title="Swing out through the ball",
            saw=f"After contact your hand travelled about {_inches(v)} toward the target, then pulled up and across.",
            why="The ball stays on the strings longer and goes where you aim when the racket keeps travelling along the target line. Cutting across early costs depth and control.",
            cue="Hit through three balls in a row. Imagine two more balls lined up behind the real one and swing through all of them.",
            drill="Stand a cone or racket cover an arm's length in front of your contact point. Shadow-swing so the racket passes over it before it comes around your shoulder. 15 reps, then 15 with a fed ball.")),
        "speed_carried": (6, lambda v, s: dict(
            title="Accelerate past the ball, not up to it",
            saw=f"Just after contact your hand was down to {v:.0f}% of the speed it had at the ball. Some drop is normal; this much suggests the swing was easing off.",
            why="A racket that is still speeding up at contact is stable and heavy. One that is slowing down twists in your hand and the ball lands short.",
            cue="Swoosh after the ball. The loudest part of the swing should be in front of you, not beside you.",
            drill="Hold the racket upside down by the throat and swing so the whoosh sound comes after your contact point. Then hit 10 balls trying to copy that sound.")),
        "weight_through": (8, lambda v, s: dict(
            title="Move your weight into the shot",
            saw="Your hips were drifting back, away from the target, as you hit.",
            why="Falling back takes your body weight out of the shot and tips the racket face open, so balls float long or drop short.",
            cue="Finish with your belt buckle closer to the net than where it started.",
            drill="Hit from a step behind the service line and walk forward through every shot, landing on your front foot. 12 balls.")),
        "chest_lead": (7, lambda v, s: dict(
            title="Stay over the ball",
            saw="Your chest was behind your hips at contact: you were leaning back.",
            why="Leaning back lifts the ball without control and takes the legs out of the swing.",
            cue="Nose over your front knee at contact.",
            drill="Hit low fed balls with a deeper knee bend, keeping your chest level. Have a partner call out if your head rises before contact.")),
        "shoulder_turn": (8, lambda v, s: dict(
            title="Turn your shoulders before you swing",
            saw=f"Your shoulders had turned about {v:.0f} degrees when the racket was back. Side-on to the ball is 90.",
            why="The turn is where the power comes from. Without it the arm has to swing on its own, which is weaker and harder to repeat.",
            cue=("Point your front shoulder at the ball. Show your back to the net for a moment." if s != "backhand"
                 else "Chin on your front shoulder. Let the net see your back for a moment."),
            drill="Hold the racket throat with your other hand and turn until that hand points at the side fence. Only then let go and swing. 15 shadow swings, then feeds.")),
        "separation": (5, lambda v, s: dict(
            title="Coil the shoulders past the hips",
            saw=f"Your shoulders and hips turned back almost together ({v:.0f} degrees apart).",
            why="Winding the shoulders further than the hips stretches the trunk like a spring. That stretch is free racket speed.",
            cue="Turn the shoulders, quiet the hips.",
            drill="Sit on a bench or stool and shadow-swing: the hips cannot turn, so you feel the trunk coil. 10 reps, then stand and copy the feeling.")),
        "knee_bend_dom": (7, lambda v, s: dict(
            title="Bend your knees to load",
            saw=f"Your legs stayed almost straight (deepest knee bend {v:.0f} degrees; a loaded leg is 110 to 145).",
            why="Straight legs mean the swing is all arm. Bent knees let you push up and into the ball and reach low balls without bending at the waist.",
            cue="Sit before you hit. Feel your back thigh take your weight.",
            drill="Hit with a ball held between your knees for 5 feeds to feel the bend, then 10 more keeping the same height.")),
        "leg_drive": (5, lambda v, s: dict(
            title="Push up from the ground",
            saw="Your legs stayed at the same bend through the swing instead of driving up into contact.",
            why="The swing should start from the ground: legs, then hips, then shoulders, then arm.",
            cue="Push the court away as you swing.",
            drill="Shadow-swing starting from a deep bend and finish tall on your toes. 10 reps, then add the ball.")),
        "front_foot_angle": (7, lambda v, s: dict(
            title="Open your front foot toward the target",
            saw=f"Your front foot was pointing at the side fence ({v:.0f} degrees off the target line).",
            why="A front foot turned sideways blocks the hip. The hips cannot rotate through the shot, so the arm has to pull across instead.",
            cue="Front toes to the net post.",
            drill="Lay a racket on the court pointing at the opposite net post and step so your front foot lands along it. 10 shadow steps, then 10 fed balls.")),
        "back_foot_angle": (5, lambda v, s: dict(
            title="Turn your back foot sideways as you prepare",
            saw=f"When the racket was back, your back foot was still pointing {'toward the net' if v < 55 else 'away from the court'} ({v:.0f} degrees; sideways is 90).",
            why="The back foot sets the turn. If it stays pointing forward, the hips never turn and there is nothing to unwind.",
            cue="Back foot parallel to the baseline as the racket goes back.",
            drill="From the ready position, pivot the back foot and turn the shoulders together on the word 'turn'. 20 reps with no ball.")),
        "back_foot_pivot": (5, lambda v, s: dict(
            title="Let the back foot release",
            saw="Your back foot stayed planted and flat through the finish.",
            why="When the back foot rolls up onto its toe and turns, the hips are free to come all the way through. A planted foot holds them back.",
            cue="Finish with your back shoelaces facing the net.",
            drill="Shadow-swing and hold the finish: back heel up, toe on the ground, knee pointing at the target. 15 reps.")),
        "trunk_lean": (6, lambda v, s: dict(
            title="Stay tall through the shot",
            saw=f"Your upper body was tilted {v:.0f} degrees off vertical at contact.",
            why="Leaning over throws off your balance and your view of the ball, and it usually means the feet did not get you close enough.",
            cue="Move your feet, not your shoulders. Head on top of your hips.",
            drill="Have a partner feed wide balls. Take one extra small step before every hit so you can hit standing tall. 12 balls.")),
        "head_stability": (6, lambda v, s: dict(
            title="Keep your head still at contact",
            saw=f"Your head moved about {_inches(v)} in the instant around contact.",
            why="When the head moves, the eyes move, and the contact point moves with them. A still head is the simplest fix for mishits.",
            cue="Eyes on the contact point until the ball is gone.",
            drill="After each hit, keep looking at the spot where you met the ball and say 'one' before you look up. 15 balls.")),
        "balance": (6, lambda v, s: dict(
            title="Keep your hips between your feet",
            saw=("At contact your hips were past your foot rather than between your feet." if not 0 <= v <= 100
                 else "At contact your hips had drifted toward one foot instead of sitting between them."),
            why="Once the hips are outside the feet you are falling, and the swing turns into a save rather than a shot.",
            cue="Wide base, belt buckle in the middle.",
            drill="Hit and hold the finish for two seconds without taking a step. If you cannot hold it, the feet were too close together or too late.")),
        "swing_path": (6, lambda v, s: dict(
            title="Swing low to high",
            saw=f"Your swing came through almost level ({v:.0f} degrees upward).",
            why="A level swing gives a flat ball with little margin over the net. Brushing up adds topspin, which lets you swing hard and still keep the ball in.",
            cue="Start below the ball, finish above it.",
            drill="Hit over a rope or a second net strap held a foot above the net, aiming to land the ball inside the baseline. 15 balls.")),
        "racket_drop": (5, lambda v, s: dict(
            title="Let the racket drop below the ball",
            saw=f"The racket head only got {_inches(v)} below the ball before swinging forward.",
            why="Topspin comes from the racket travelling up through the ball. It can only travel up if it starts underneath.",
            cue="Pat the dog: let the racket head fall to knee height before you swing.",
            drill="Shadow-swing and touch the racket tip to a ball can on the ground beside your back foot before every swing. 15 reps.")),
        "contact_spacing": (6, lambda v, s: dict(
            title="Give yourself room from the ball",
            saw=f"Your hand was {'only ' + _inches(v) + ' from your body' if v < 35 else _inches(v) + ' out from your body'} at contact.",
            why=("A cramped swing has no room to extend. " if v < 35 else "Reaching leaves you off balance with no body behind the ball. ")
                + "A comfortable arm's-length gap lets the racket travel through freely.",
            cue="Hit at arm's length, elbow away from your ribs." if v < 35 else "Take one more step so the ball comes to you.",
            drill="Self-feed and let the ball bounce twice. On the second bounce, adjust your feet so you can hit with a relaxed, extended arm. 10 balls.")),
        "elbow_contact": (7, lambda v, s: dict(
            title="Free your hitting arm",
            saw=f"Your elbow was tightly bent at contact ({v:.0f} degrees), so the ball was too close.",
            why="A cramped arm cannot swing out, so the wrist flicks to make up for it.",
            cue="Elbow off the ribs. Give the ball some space.",
            drill="Tuck a ball under your hitting-arm armpit, start your swing, and let it fall out before contact. 10 reps.")),
        "follow_length": (6, lambda v, s: dict(
            title="Finish the swing",
            saw=f"Your hand travelled only {v * 100 / 2.54:.0f} inches after contact before it stopped.",
            why="A short finish means the brakes went on before the ball was gone. A full finish is proof you swung through.",
            cue="Racket over your shoulder, elbow pointing at the target." if s != "backhand" else "Finish high with both hands by your ear.",
            drill="Hit 10 balls and catch the racket with your free hand at the end of every swing.")),
        "finish_height": (5, lambda v, s: dict(
            title="Finish higher",
            saw="Your swing ended low, around your waist." if v < -30 else "Your swing ended a little below shoulder height.",
            why="A low finish goes with a flat, risky ball. Finishing high pulls the racket up the back of the ball for spin and net clearance.",
            cue="Kiss your bicep: finish with your hitting hand by the opposite ear.",
            drill="Shadow-swing 10 times, checking that your racket hand ends above your opposite shoulder. Then 10 balls.")),
        "prep_time": (5, lambda v, s: dict(
            title="Get the racket back earlier",
            saw=f"You started taking the racket back only {v:.1f} seconds before contact.",
            why="Late preparation rushes everything after it. The turn should be finished by the time the ball bounces on your side.",
            cue="Turn when the ball crosses the net. Bounce, hit.",
            drill="Say 'turn' out loud the moment your partner hits, and 'hit' at your contact. 20 balls.")),
        "sequence": (4, lambda v, s: dict(
            title="Let the swing start from the hips",
            saw="Your arm reached top speed before your hips and shoulders had finished turning.",
            why="Power travels up the body in order: hips, shoulders, arm. When the arm goes first it loses the push from everything below it.",
            cue="Hips fire, arm follows.",
            drill="Throw a ball sidearm across the court, stepping and turning the hips first. Then swing with the same feeling. 10 throws, 10 swings.")),
    }


PRAISE = {
    "contact_in_front": "You met the ball well out in front of your body.",
    "extension": "You swung out through the ball toward the target before coming around.",
    "speed_carried": "The racket was still accelerating as it went through the ball.",
    "weight_through": "Your weight was moving into the shot.",
    "chest_lead": "You stayed over the ball instead of leaning back.",
    "shoulder_turn": "Full shoulder turn: you were side-on with the racket back.",
    "separation": "Good coil: your shoulders wound back past your hips.",
    "knee_bend_dom": "Your legs were bent and loaded.",
    "leg_drive": "You pushed up from the ground into the shot.",
    "front_foot_angle": "Your front foot opened toward the target, so the hips could turn through.",
    "back_foot_angle": "Your back foot turned sideways as you prepared.",
    "back_foot_pivot": "Your back foot released and turned as you finished.",
    "step_in": "You stepped into the ball.",
    "trunk_lean": "You stayed tall and balanced through contact.",
    "head_stability": "Your head stayed still through contact.",
    "balance": "Your hips stayed between your feet.",
    "swing_path": "Clear low-to-high swing path for topspin.",
    "racket_drop": "The racket head dropped under the ball before swinging up.",
    "contact_spacing": "Comfortable spacing between your body and the ball.",
    "contact_height": "You met the ball in the ideal strike zone, between waist and chest.",
    "follow_length": "Full, relaxed follow-through.",
    "finish_height": "High finish.",
    "prep_time": "Early preparation: the racket was back in plenty of time.",
    "sequence": "The swing fired in the right order: hips, then shoulders, then arm.",
}


def band(score: float) -> str:
    return "Strong" if score >= 85 else "Solid" if score >= 70 else "Developing" if score >= 55 else "Needs work"


def coach(metrics: list, stroke: str, book: dict | None = None) -> dict:
    """metrics: objects or dicts with key, label, value, unit, status, typical. Returns scores, fixes and strengths.

    book: the coaching tables to use (categories, tips, problems, praise, situational, meters, strength_at).
    Defaults to the groundstroke tables; the serve module passes its own.
    """
    book = book or {}
    CATEGORIES = book.get("categories", globals()["CATEGORIES"])
    PROBLEMS = book.get("problems", globals()["PROBLEMS"])
    PRAISE = book.get("praise", globals()["PRAISE"])
    SITUATIONAL = book.get("situational", globals()["SITUATIONAL"])
    METERS = book.get("meters", globals()["METERS"])
    strength_at = book.get("strength_at", STRENGTH_AT)
    get = (lambda m, k: m[k]) if metrics and isinstance(metrics[0], dict) else (lambda m, k: getattr(m, k))
    by_key = {get(m, "key"): m for m in metrics}

    def sure(m) -> str:
        try:
            return get(m, "confidence") or "high"
        except (KeyError, AttributeError):
            return "high"
    confidence = {k: sure(m) for k, m in by_key.items()}
    value = lambda key: get(by_key[key], "value") if key in by_key else None

    stretched = False
    width, travel = value("stance_width"), value("weight_shift")
    if isinstance(width, (int, float)) and width >= 2.4:
        stretched = True
    if isinstance(travel, (int, float)) and travel >= 0.25:
        stretched = True

    categories = []
    for cid, name, keys in CATEGORIES:
        rows = [(k, get(by_key[k], "status")) for k in keys
                if k in by_key and get(by_key[k], "status") in POINTS and confidence[k] != "low"]
        if not rows:
            continue
        score = round(sum(POINTS[s] for _, s in rows) / len(rows))
        categories.append(dict(id=cid, name=name, score=score, band=band(score), checks=len(rows),
                               passed=sum(s == "good" for _, s in rows), keys=[k for k, _ in rows]))
    overall = round(sum(c["score"] for c in categories) / len(categories)) if categories else None
    category_of = {k: c["name"] for c in categories for k in c["keys"]}

    tips = book.get("tips") or _tips()
    fixes = []
    for key, m in by_key.items():
        status = get(m, "status")
        if key not in tips or status not in ("work", "ok") or confidence[key] == "low":
            continue
        val = get(m, "value")
        if not isinstance(val, (int, float)):
            if key != "sequence":
                continue
            val = 0
        priority, build = tips[key]
        situational = stretched and key in SITUATIONAL
        rank = priority * (1.0 if status == "work" else 0.45) * (0.6 if situational else 1.0) * (1.0 if confidence[key] == "high" else 0.7)
        card = build(val, stroke)
        book_cue = cue_for(key, val, stroke)
        if book_cue:
            card.update(cue_more=card["cue"], cue=book_cue["cue"], alts=book_cue["alts"], check=book_cue["check"])
        else:
            card.update(cue_more="", alts=[], check="")
        card.update(key=key, severity="fix" if status == "work" else "polish", category=category_of.get(key, ""),
                    situational=situational, rank=round(rank, 2), problem=PROBLEMS[key](val),
                    grade=grade_of(key, val, status, situational, strength_at, confidence[key]), value=get(m, "value"),
                    unit=get(m, "unit"), confidence=confidence[key], label=get(m, "label"),
                    measured=f"{get(m, 'label')}: {val if key != 'sequence' else get(m, 'value')} {get(m, 'unit')}".strip(),
                    typical=get(m, "typical"))
        fixes.append(card)
    fixes.sort(key=lambda c: (c["grade"] != "priority", -c["rank"]))      # anything seen directly and clearly off comes first

    grades = {k: grade_of(k, get(m, "value"), get(m, "status"), stretched and k in SITUATIONAL, strength_at, confidence[k])
              for k, m in by_key.items()}
    strengths = [dict(key=k, text=PRAISE[k], category=category_of.get(k, ""), grade=grades[k], value=get(m, "value"),
                      unit=get(m, "unit")) for k, m in by_key.items()
                 if get(m, "status") == "good" and k in PRAISE and confidence[k] != "low"]
    strengths.sort(key=lambda w: (confidence[w["key"]] != "high", w["grade"] != "strength", -tips.get(w["key"], (0,))[0]))
    counts = dict(priority=sum(g == "priority" for g in grades.values()), building=sum(g == "building" for g in grades.values()),
                  on_target=sum(g in ("on_target", "strength") for g in grades.values()),
                  strength=sum(g == "strength" for g in grades.values()))
    counts["graded"] = counts["priority"] + counts["building"] + counts["on_target"]
    counts["estimates"] = sum(confidence[k] == "estimate" and g != "not_graded" for k, g in grades.items())
    counts["unclear"] = sum(c == "low" for c in confidence.values())
    light = "red" if counts["priority"] else "yellow" if counts["building"] else "green"
    meters = {k: dict(min=v[0], max=v[1], lo=v[2], hi=v[3]) for k, v in METERS.items() if k in by_key}

    if fixes and fixes[0]["severity"] == "fix":
        headline = f"One thing to work on first: {fixes[0]['title'].lower()}."
    elif fixes:
        headline = f"A sound swing. Polish to add: {fixes[0]['title'].lower()}."
    else:
        headline = "A clean swing on every checkpoint we measure."
    context = ("This ball pulled you wide and you hit it on the stretch, so balance and finish are judged more gently here. "
               "Film a ball hit from a set position to see your normal swing.") if stretched else ""
    return dict(overall=overall, band=band(overall) if overall is not None else None, headline=headline, context=context,
                stretched=stretched, categories=categories, fixes=fixes, strengths=strengths,
                grades=grades, counts=counts, light=light, meters=meters, confidence=confidence)
