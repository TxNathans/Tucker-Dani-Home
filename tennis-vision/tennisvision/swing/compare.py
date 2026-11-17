"""Compare two analysed swings: scores side by side and the differences that matter, in plain words.

Works on the swing dictionaries stored in a report, so any two swings can be compared: before and after,
two swings from one clip, or a player against a model swing.
"""
from __future__ import annotations

from .coach import CATEGORIES
from .serve_coach import SERVE_CATEGORIES

RANK = {"work": 0, "ok": 1, "good": 2}
CM_PER_INCH = 2.54


def _length(cm: float) -> str:
    inches = abs(cm) / CM_PER_INCH
    return f"{inches:.0f} inch{'es' if round(inches) != 1 else ''}"


# key -> (smallest difference worth mentioning, wording when B is higher, wording when B is lower, how to print the gap)
WORDS = {
    "contact_in_front": (5, "meets the ball {d} further out in front", "lets the ball get {d} closer to the body", "cm"),
    "extension": (6, "swings {d} further out toward the target after contact", "cuts the swing off {d} sooner after contact", "cm"),
    "speed_carried": (6, "holds {d} more of its speed just past the ball", "loses {d} more of its speed right after contact", "pct"),
    "weight_through": (4, "moves the body {d} further into the shot", "moves the body {d} less into the shot", "cm"),
    "chest_lead": (5, "keeps the chest {d} further over the ball", "has the chest {d} further back", "cm"),
    "shoulder_turn": (10, "turns the shoulders {d} more", "turns the shoulders {d} less", "deg"),
    "separation": (8, "coils the shoulders {d} further past the hips", "has {d} less coil between shoulders and hips", "deg"),
    "knee_bend_dom": (8, "stays {d} straighter in the legs", "bends the knees {d} deeper", "deg"),
    "leg_drive": (8, "drives up {d} more with the legs", "drives up {d} less with the legs", "deg"),
    "front_foot_angle": (12, "has the front foot turned {d} further away from the target", "points the front foot {d} more toward the target", "deg"),
    "back_foot_angle": (12, "has the back foot turned {d} further round when the racket is back", "has the back foot {d} less turned when the racket is back", "deg"),
    "back_foot_pivot": (12, "releases the back foot {d} more through the finish", "releases the back foot {d} less through the finish", "deg"),
    "step_in": (8, "steps {d} further into the ball", "steps {d} less into the ball", "cm"),
    "swing_path": (6, "swings {d} steeper from low to high", "swings {d} flatter", "deg"),
    "racket_drop": (6, "drops the racket {d} further under the ball", "drops the racket {d} less under the ball", "cm"),
    "hand_speed_peak": (0.5, "swings the hand {d} faster", "swings the hand {d} slower", "mps"),
    "racket_head_speed": (1.0, "has {d} more racket-head speed", "has {d} less racket-head speed", "mps"),
    "contact_height": (0.08, "meets the ball {d} higher", "meets the ball {d} lower", "m"),
    "contact_spacing": (6, "hits with {d} more room from the body", "hits {d} closer to the body", "cm"),
    "elbow_contact": (10, "has the hitting arm {d} straighter at contact", "has the hitting arm {d} more bent at contact", "deg"),
    "trunk_lean": (6, "leans {d} further off vertical", "stays {d} more upright", "deg"),
    "head_stability": (4, "moves the head {d} more around contact", "keeps the head {d} stiller around contact", "cm"),
    "follow_length": (0.12, "follows through {d} further", "follows through {d} shorter", "m"),
    "finish_height": (8, "finishes {d} higher", "finishes {d} lower", "cm"),
    "prep_time": (0.1, "starts preparing {d} earlier", "starts preparing {d} later", "s"),
    "forward_swing_time": (0.04, "takes {d} longer on the forward swing", "is {d} quicker on the forward swing", "s"),
    "racket_lag": (8, "has {d} more racket lag", "has {d} less racket lag", "deg"),
    "approach_angle": (6, "brings the racket up into the ball {d} steeper", "brings the racket into the ball {d} flatter", "deg"),
    "swing_plane": (6, "swings on a plane {d} steeper", "swings on a plane {d} flatter", "deg"),
    "lead_knee_contact": (8, "has the lead leg {d} straighter at contact", "has the lead leg {d} more bent at contact", "deg"),
    "trail_drive": (8, "pushes {d} more out of the trail leg", "pushes {d} less out of the trail leg", "deg"),
    "serve_contact_height": (0.04, "reaches {d} higher at contact", "meets the ball {d} lower", "ratio"),
    "serve_knee_lead": (8, "stays {d} straighter in the lead leg", "bends the lead knee {d} deeper", "deg"),
    "serve_knee_trail": (8, "stays {d} straighter in the trail leg", "bends the trail knee {d} deeper", "deg"),
    "serve_trunk_tilt": (5, "tilts the trunk {d} further at trophy", "stays {d} more upright at trophy", "deg"),
    "serve_shoulder_tilt": (6, "tilts the shoulders {d} more at trophy", "tilts the shoulders {d} less at trophy", "deg"),
    "serve_coil": (6, "coils {d} more at trophy", "coils {d} less at trophy", "deg"),
    "serve_racket_drop": (6, "drops the racket {d} deeper behind the back", "drops the racket {d} less behind the back", "cm"),
    "serve_rise": (5, "drives the hips up {d} more", "drives the hips up {d} less", "cm"),
    "serve_elbow_contact": (8, "has the arm {d} straighter at contact", "has the arm {d} more bent at contact", "deg"),
    "serve_shoulder_over": (6, "gets the hitting shoulder {d} further over the top", "gets the hitting shoulder {d} less over the top", "deg"),
    "serve_contact_front": (8, "meets the ball {d} further into the court", "meets the ball {d} further back", "cm"),
    "serve_contact_side": (8, "meets the ball {d} further out to the side", "meets the ball {d} closer to the head", "cm"),
    "serve_swing_up": (6, "swings up into the ball {d} steeper", "swings into the ball {d} flatter", "deg"),
    "serve_hand_speed": (0.5, "swings the hand {d} faster", "swings the hand {d} slower", "mps"),
    "serve_racket_speed": (1.0, "has {d} more racket-head speed", "has {d} less racket-head speed", "mps"),
    "serve_into_court": (8, "lands {d} further into the court", "lands {d} less into the court", "cm"),
}


def _gap(delta: float, kind: str) -> str:
    d = abs(delta)
    if kind == "cm":
        return _length(d)
    if kind == "m":
        return _length(d * 100)
    if kind == "deg":
        return f"{d:.0f} degrees"
    if kind == "pct":
        return f"{d:.0f}%"
    if kind == "ratio":
        return f"{d * 100:.0f}% of body height"
    if kind == "mps":
        return f"{d * 2.237:.0f} mph"
    return f"{d:.2f} seconds"


def _off(meters: dict, key: str, value) -> float | None:
    """How far a value sits outside its target range, as a share of its meter. 0 = inside the range."""
    m = meters.get(key)
    if not m or not isinstance(value, (int, float)):
        return None
    gap = m["lo"] - value if value < m["lo"] else value - m["hi"] if value > m["hi"] else 0.0
    return gap / (m["max"] - m["min"])


def _moved(meters: dict, key: str, va, vb, sa: str, sb: str) -> str:
    """better / worse / no_change for the second swing against the first."""
    if sa in RANK and sb in RANK and RANK[sa] != RANK[sb]:
        return "better" if RANK[sb] > RANK[sa] else "worse"
    oa, ob = _off(meters, key, va), _off(meters, key, vb)
    if oa is None or ob is None or abs(oa - ob) < 0.03:
        return "no_change"
    return "better" if ob < oa else "worse"


def _category_names() -> dict[str, str]:
    return {key: name for _, name, keys in list(CATEGORIES) + list(SERVE_CATEGORIES) for key in keys}


def compare_swings(a: dict, b: dict, name_a: str = "Swing A", name_b: str = "Swing B") -> dict:
    """a, b: swing dictionaries from a report (metrics, coaching, stroke...). Differences are stated as B relative to A."""
    ma = {m["key"]: m for m in a["metrics"]}
    mb = {m["key"]: m for m in b["metrics"]}
    cat_of = _category_names()
    differences, unchanged = [], 0
    for key, row_a in ma.items():
        row_b = mb.get(key)
        if row_b is None:
            continue
        va, vb = row_a["value"], row_b["value"]
        sa, sb = row_a["status"], row_b["status"]
        base = dict(key=key, label=row_a["label"], unit=row_a["unit"], a=va, b=vb, status_a=sa, status_b=sb,
                    category=cat_of.get(key, row_a.get("phase", "")), typical=row_a.get("typical", ""))
        if not isinstance(va, (int, float)) or not isinstance(vb, (int, float)):
            if va != vb and key == "stance_type":
                differences.append(dict(base, verdict="different", size=1.0, delta=None,
                                        sentence=f"{name_b} hits from a {vb} stance; {name_a} from a {va} stance."))
            continue
        delta = vb - va
        threshold, more, less, kind = WORDS.get(key, (None, "", "", ""))
        if sa in RANK and sb in RANK and RANK[sa] != RANK[sb]:
            verdict = "b_better" if RANK[sb] > RANK[sa] else "a_better"
        else:
            verdict = "different"
        meaningful = threshold is not None and abs(delta) >= threshold
        if not meaningful and verdict == "different":
            unchanged += 1
            continue
        if threshold is not None and abs(delta) > 0:
            phrase = (more if delta > 0 else less).format(d=_gap(delta, kind))
            sentence = f"{name_b} {phrase} than {name_a}." if " more " in f" {phrase} " or "er " in phrase + " " else f"{name_b} {phrase}."
        else:
            sentence = f"{row_a['label']}: {name_a} {va} {row_a['unit']}, {name_b} {vb} {row_a['unit']}.".replace("  ", " ")
        size = abs(delta) / threshold if threshold else 1.0
        differences.append(dict(base, delta=round(delta, 2), verdict=verdict, size=round(size, 2), sentence=sentence))
    order = {"b_better": 0, "a_better": 0, "different": 1}
    differences.sort(key=lambda d: (order[d["verdict"]], -d["size"]))

    ca, cb = a.get("coaching") or {}, b.get("coaching") or {}
    cats_a = {c["id"]: c for c in ca.get("categories", [])}
    cats_b = {c["id"]: c for c in cb.get("categories", [])}
    categories = [dict(id=cid, name=c["name"], a=c["score"], b=cats_b[cid]["score"], delta=cats_b[cid]["score"] - c["score"])
                  for cid, c in cats_a.items() if cid in cats_b and c["name"] == cats_b[cid]["name"]]
    oa, ob = ca.get("overall"), cb.get("overall")
    b_wins = [d for d in differences if d["verdict"] == "b_better"]
    a_wins = [d for d in differences if d["verdict"] == "a_better"]
    if oa is None or ob is None:
        headline = "Side by side."
    elif abs(ob - oa) < 3:
        headline = f"The two swings score about the same ({oa} and {ob})."
    else:
        better, worse, gap = (name_b, name_a, ob - oa) if ob > oa else (name_a, name_b, oa - ob)
        headline = f"{better} scores {gap} points higher than {worse}."
    notes = []
    if a.get("stroke") != b.get("stroke"):
        notes.append(f"These are different strokes ({a.get('stroke')} and {b.get('stroke')}), so compare the shapes rather than the numbers.")
    type_a, type_b = (a.get("serve") or {}).get("type"), (b.get("serve") or {}).get("type")
    if type_a and type_b and type_a != type_b:
        notes.append(f"These are different serves ({type_a} and {type_b}). The toss and the swing up are meant to differ between them.")
    if a.get("hand") != b.get("hand"):
        notes.append("One player is right-handed and the other left-handed, so the pictures are mirror images of each other.")
    if ca.get("stretched") != cb.get("stretched"):
        who = name_a if ca.get("stretched") else name_b
        notes.append(f"{who} was hit on the stretch and the other from a set position, which explains part of the balance and finish gap.")
    meters = {**(ca.get("meters") or {}), **(cb.get("meters") or {})}
    grades_a, grades_b = ca.get("grades") or {}, cb.get("grades") or {}
    worked_on = []
    for fix in (ca.get("fixes") or [])[:3]:
        key = fix["key"]
        if key not in mb:
            continue
        va, vb = ma[key]["value"], mb[key]["value"]
        worked_on.append(dict(key=key, title=fix["title"], problem=fix.get("problem", fix["title"]), label=ma[key]["label"],
                              unit=ma[key]["unit"], a=va, b=vb, typical=ma[key].get("typical", ""),
                              verdict=_moved(meters, key, va, vb, ma[key]["status"], mb[key]["status"]),
                              grade_a=grades_a.get(key), grade_b=grades_b.get(key), cue=fix["cue"]))
    worked_keys = {x["key"] for x in worked_on}
    also_better = [d["sentence"] for d in differences if d["verdict"] == "b_better" and d["key"] not in worked_keys]
    slipped = [d["sentence"] for d in differences if d["verdict"] == "a_better" and d["key"] not in worked_keys]
    still = next((x for x in worked_on if x["grade_b"] not in ("on_target", "strength")), None)
    if still:
        keep = dict(title=still["title"], cue=still["cue"], lead="Keep working on")
    elif cb.get("fixes"):
        keep = dict(title=cb["fixes"][0]["title"], cue=cb["fixes"][0]["cue"], lead="Next to work on")
    else:
        keep = None
    return dict(
        worked_on=worked_on, moved_right=sum(x["verdict"] == "better" for x in worked_on),
        also_better=also_better, slipped=slipped, keep_working=keep,
        counts=dict(a=ca.get("counts"), b=cb.get("counts")),
        name_a=name_a, name_b=name_b, headline=headline, notes=notes,
        overall=dict(a=oa, b=ob, delta=None if oa is None or ob is None else ob - oa),
        categories=categories, differences=differences, unchanged=unchanged,
        b_better=len(b_wins), a_better=len(a_wins),
    )
