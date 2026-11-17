import numpy as np

from tennisvision import pose as P
from tennisvision.pose import PoseSequence
from tennisvision.swing.coach import coach
from tennisvision.swing.serve import ServeAnalyzer, serve_hand
from tennisvision.swing.serve_coach import SERVE_BOOK, SERVE_CATEGORIES, SERVE_METERS, SERVE_PROBLEMS, SERVE_TIPS


def test_serve_type_read():
    read = ServeAnalyzer._serve_type
    assert read(45, 20, None)[:2] == ("kick", "medium")          # steep upward brush, met close to the head
    assert read(34, None, 5)[0] == "kick"
    assert read(10, None, 45)[0] == "slice"                      # met well out to the hitting side
    assert read(12, 50, None)[:2] == ("flat", "medium")          # met out in front, swinging forward
    assert read(15, 10, None)[:2] == ("flat", "low")             # nothing decisive: say so


def test_hitting_hand_is_the_one_that_peaks_last():
    n = 60
    xy = np.zeros((n, 33, 2), np.float32)
    xy[:, P.L_SHOULDER] = xy[:, P.R_SHOULDER] = (100, 200)
    xy[:, P.L_WRIST] = xy[:, P.R_WRIST] = (100, 300)
    xy[20:30, P.L_WRIST, 1] = 120       # tossing arm goes up first
    xy[40:44, P.R_WRIST, 1] = 60        # hitting arm reaches higher, later
    seq = PoseSequence(np.arange(n) / 30, xy, np.ones((n, 33), np.float32), np.zeros((n, 33, 3), np.float32), np.ones(n, bool), 400, 400, 30.0)
    assert serve_hand(seq) == "right"
    xy[:, [P.L_WRIST, P.R_WRIST]] = xy[:, [P.R_WRIST, P.L_WRIST]]
    assert serve_hand(seq) == "left"


def test_every_graded_serve_number_has_coaching_and_a_meter():
    graded = {key for _, _, keys in SERVE_CATEGORIES for key in keys}
    assert graded <= set(SERVE_TIPS) | {"serve_coil"}
    assert set(SERVE_TIPS) == set(SERVE_PROBLEMS)
    assert graded <= set(SERVE_METERS)


def test_serve_coaching_uses_the_serve_book():
    rows = [
        dict(key="serve_knee_lead", label="Lead leg: deepest knee bend", value=165, unit="deg", status="work", typical="100-135"),
        dict(key="serve_contact_height", label="Hand height at contact", value=1.25, unit="x height", status="good", typical="1.18 or more"),
        dict(key="serve_toss_arm_straight", label="Tossing arm", value=172, unit="deg", status="good", typical="160-180"),
    ]
    c = coach(rows, "serve", SERVE_BOOK)
    assert [cat["name"] for cat in c["categories"]] == ["Stance and toss", "Trophy position", "Contact"]
    assert c["fixes"][0]["problem"] == "Your legs stay straight on the serve." and c["fixes"][0]["grade"] == "priority"
    assert "Toss, sit, then explode up." == c["fixes"][0]["cue"]
    assert c["counts"] == dict(priority=1, building=0, on_target=2, strength=0, graded=3) and c["light"] == "red"
    assert c["meters"]["serve_knee_lead"] == dict(min=80, max=180, lo=100, hi=135)
    assert not c["stretched"]
