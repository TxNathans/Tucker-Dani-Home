from tennisvision.swing.coach import CATEGORIES, coach


def metric(key, value, status, unit="", label=None, typical="t"):
    return dict(key=key, label=label or key, value=value, unit=unit, status=status, typical=typical)


def base(**overrides):
    rows = {
        "stance_width": metric("stance_width", 1.8, "info"), "weight_shift": metric("weight_shift", 0.1, "info"),
        "front_foot_angle": metric("front_foot_angle", 40, "good", "deg"), "back_foot_angle": metric("back_foot_angle", 90, "good", "deg"),
        "shoulder_turn": metric("shoulder_turn", 95, "good", "deg"), "knee_bend_dom": metric("knee_bend_dom", 130, "good", "deg"),
        "extension": metric("extension", 55, "good", "cm"), "speed_carried": metric("speed_carried", 92, "good", "%"),
        "contact_in_front": metric("contact_in_front", 35, "good", "cm"), "trunk_lean": metric("trunk_lean", 10, "good", "deg"),
        "head_stability": metric("head_stability", 5, "good", "cm"), "follow_length": metric("follow_length", 1.3, "good", "m"),
    }
    rows.update(overrides)
    return list(rows.values())


def test_clean_swing_scores_full_marks_and_has_no_fixes():
    c = coach(base(), "forehand")
    assert c["overall"] == 100 and c["band"] == "Strong" and c["fixes"] == []
    assert len(c["strengths"]) == 10 and not c["stretched"] and c["context"] == ""
    assert [cat["id"] for cat in c["categories"]] == [cid for cid, _, _ in CATEGORIES]


def test_fixes_are_ranked_and_written_for_people():
    c = coach(base(
        contact_in_front=metric("contact_in_front", 2, "work", "cm", "Contact point ahead of the front hip"),
        front_foot_angle=metric("front_foot_angle", 100, "work", "deg"),
        head_stability=metric("head_stability", 12, "ok", "cm"),
    ), "forehand")
    titles = [f["title"] for f in c["fixes"]]
    assert titles == ["Meet the ball further in front", "Open your front foot toward the target", "Keep your head still at contact"]
    first = c["fixes"][0]
    assert first["severity"] == "fix" and first["category"] == "Contact point"
    assert "level with your front hip" in first["saw"] and first["cue"] and first["drill"] and first["why"]
    assert first["measured"] == "Contact point ahead of the front hip: 2 cm" and first["typical"] == "t"
    assert c["fixes"][2]["severity"] == "polish" and "5 inches" in c["fixes"][2]["saw"]
    assert c["headline"].startswith("One thing to work on first: meet the ball further in front")
    contact = next(cat for cat in c["categories"] if cat["id"] == "contact")
    assert contact["score"] == 35 and contact["band"] == "Needs work"
    assert 60 < c["overall"] < 90


def test_stretched_ball_softens_balance_but_not_technique():
    wide = base(
        stance_width=metric("stance_width", 2.8, "info"),
        trunk_lean=metric("trunk_lean", 33, "work", "deg"), speed_carried=metric("speed_carried", 60, "work", "%"),
    )
    c = coach(wide, "forehand")
    assert c["stretched"] and "pulled you wide" in c["context"]
    lean = next(f for f in c["fixes"] if f["key"] == "trunk_lean")
    speed = next(f for f in c["fixes"] if f["key"] == "speed_carried")
    assert lean["situational"] and not speed["situational"]
    assert c["fixes"][0]["key"] == "speed_carried"
    set_position = coach(base(trunk_lean=metric("trunk_lean", 33, "work", "deg")), "forehand")
    assert not set_position["fixes"][0]["situational"]


def test_backhand_gets_its_own_cue():
    turn = metric("shoulder_turn", 40, "work", "deg")
    assert "Chin on your front shoulder" in coach(base(shoulder_turn=turn), "backhand")["fixes"][0]["cue"]
    assert "Point your front shoulder" in coach(base(shoulder_turn=turn), "forehand")["fixes"][0]["cue"]
