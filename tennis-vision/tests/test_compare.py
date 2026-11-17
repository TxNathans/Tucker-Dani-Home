from tennisvision.swing.coach import coach
from tennisvision.swing.compare import compare_swings


def metric(key, value, status, unit="", label=None):
    return dict(key=key, label=label or key, value=value, unit=unit, status=status, typical="t", phase="p")


def swing(stroke="forehand", hand="right", **values):
    rows = {
        "stance_type": metric("stance_type", "neutral", "info"), "stance_width": metric("stance_width", 1.8, "info"),
        "contact_in_front": metric("contact_in_front", 30, "good", "cm"), "extension": metric("extension", 50, "good", "cm"),
        "speed_carried": metric("speed_carried", 90, "good", "%"), "shoulder_turn": metric("shoulder_turn", 95, "good", "deg"),
        "hand_speed_peak": metric("hand_speed_peak", 8.0, "info", "m/s"), "head_stability": metric("head_stability", 5, "good", "cm"),
        "front_foot_angle": metric("front_foot_angle", 40, "good", "deg"),
    }
    rows.update(values)
    metrics = list(rows.values())
    return dict(stroke=stroke, hand=hand, metrics=metrics, coaching=coach(metrics, stroke))


def test_identical_swings_have_no_differences():
    c = compare_swings(swing(), swing())
    assert c["differences"] == [] and c["unchanged"] == 8
    assert c["overall"]["delta"] == 0 and "about the same" in c["headline"] and c["notes"] == []


def test_differences_are_ranked_and_worded_as_b_against_a():
    before = swing(contact_in_front=metric("contact_in_front", 2, "work", "cm"), extension=metric("extension", 20, "work", "cm"),
                   hand_speed_peak=metric("hand_speed_peak", 7.0, "info", "m/s"))
    after = swing(contact_in_front=metric("contact_in_front", 32, "good", "cm"), extension=metric("extension", 48, "good", "cm"),
                  hand_speed_peak=metric("hand_speed_peak", 9.0, "info", "m/s"), head_stability=metric("head_stability", 14, "ok", "cm"),
                  shoulder_turn=metric("shoulder_turn", 97, "good", "deg"))
    c = compare_swings(before, after, "Before", "After")
    by_key = {d["key"]: d for d in c["differences"]}
    assert set(by_key) == {"contact_in_front", "extension", "hand_speed_peak", "head_stability"}       # a 2 degree turn change is noise
    assert by_key["contact_in_front"]["verdict"] == "b_better" and by_key["head_stability"]["verdict"] == "a_better"
    assert by_key["hand_speed_peak"]["verdict"] == "different"
    assert by_key["contact_in_front"]["sentence"] == "After meets the ball 12 inches further out in front than Before."
    assert by_key["extension"]["sentence"] == "After swings 11 inches further out toward the target after contact than Before."
    assert by_key["hand_speed_peak"]["sentence"] == "After swings the hand 4 mph faster than Before."
    assert by_key["head_stability"]["sentence"] == "After moves the head 4 inches more around contact than Before."
    assert [d["verdict"] for d in c["differences"]][-1] == "different"                                # status changes come first
    assert c["b_better"] == 2 and c["a_better"] == 1
    assert c["overall"]["b"] > c["overall"]["a"] and c["headline"].startswith("After scores")
    contact = next(x for x in c["categories"] if x["id"] == "contact")
    assert contact["a"] == 35 and contact["b"] == 100 and contact["delta"] == 65


def test_notes_flag_unlike_comparisons():
    c = compare_swings(swing(), swing(stroke="backhand", hand="left", stance_type=metric("stance_type", "open", "info"),
                                      stance_width=metric("stance_width", 2.9, "info")), "Dani", "Coach")
    assert len(c["notes"]) == 3
    assert "different strokes" in c["notes"][0] and "mirror images" in c["notes"][1] and "Coach was hit on the stretch" in c["notes"][2]
    stance = next(d for d in c["differences"] if d["key"] == "stance_type")
    assert stance["sentence"] == "Coach hits from a open stance; Dani from a neutral stance."


def test_retest_view_tracks_what_was_being_worked_on():
    before = swing(contact_in_front=metric("contact_in_front", 2, "work", "cm"), extension=metric("extension", 20, "work", "cm"),
                   speed_carried=metric("speed_carried", 60, "work", "%"))
    after = swing(contact_in_front=metric("contact_in_front", 32, "good", "cm"), extension=metric("extension", 30, "work", "cm"),
                  speed_carried=metric("speed_carried", 59, "work", "%"), head_stability=metric("head_stability", 14, "ok", "cm"))
    c = compare_swings(before, after, "Baseline", "Retest")
    worked = {x["key"]: x for x in c["worked_on"]}
    assert list(worked) == ["contact_in_front", "extension", "speed_carried"]             # the baseline's top three, in order
    assert worked["contact_in_front"]["verdict"] == "better" and worked["contact_in_front"]["grade_b"] == "on_target"
    assert worked["extension"]["verdict"] == "better"                                    # still short, but closer to the target
    assert worked["speed_carried"]["verdict"] == "no_change"
    assert c["moved_right"] == 2
    assert c["slipped"] == ["Retest moves the head 4 inches more around contact than Baseline."] and c["also_better"] == []
    assert c["keep_working"]["lead"] == "Keep working on" and c["keep_working"]["title"] == "Swing out through the ball"
    assert c["counts"]["a"]["priority"] == 3 and c["counts"]["b"]["priority"] == 2
