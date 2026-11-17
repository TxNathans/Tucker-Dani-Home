from tennisvision.match.lesson import lesson_breakdown, shot_kind
from tennisvision.match.rally import Bounce, Hit, build_shots, split_rallies
from tennisvision.stats.schema import Player

PLAYERS = [Player("s", "Student", 0), Player("c", "Coach", 1)]


def feed_and_reply(t, student_pos, stroke, landing, coach_pos=(0.0, 11.5), volley=False):
    """Coach feeds from the far end; the student replies. A volley has no bounce before the student's hit."""
    hits = [Hit(t, "c", coach_pos, stroke="forehand"), Hit(t + 1.2, "s", student_pos, stroke=stroke)]
    bounces = [] if volley else [Bounce(t + 0.8, (student_pos[0], student_pos[1] + 2.0))]
    if landing is not None:
        bounces.append(Bounce(t + 2.0, landing))
    return hits, bounces


def test_every_shot_is_judged_on_its_own_landing():
    hits, bounces = [], []
    drills = [
        (0.0, (2.0, -11.5), "forehand", (3.0, 10.0), False),     # forehand from the baseline, deep and in
        (2.5, (2.0, -11.5), "forehand", (4.8, 9.0), False),      # forehand wide
        (5.0, (-2.0, -11.5), "backhand", (0.0, 12.6), False),    # backhand long
        (7.5, (-2.0, -11.5), "backhand", (-1.0, -2.0), False),   # backhand into the net (lands on own side)
        (10.0, (0.5, -2.5), "forehand", (2.0, 4.0), True),       # forehand volley at the net, short and in
        (12.5, (0.5, -2.5), "backhand", None, True),             # backhand volley, landing not seen
    ]
    for t, pos, stroke, landing, volley in drills:
        h, b = feed_and_reply(t, pos, stroke, landing, volley=volley)
        hits += h
        bounces += b
    rallies = split_rallies(hits, bounces)
    assert len(rallies) == 1                                      # continuous feeding is one long sequence
    shots = build_shots(rallies[0], "singles", judge_all=True)
    mine = [s for s in shots if s.player == "s"]
    assert [s.result for s in mine] == ["in", "wide", "long", "net", "in", "unknown"]
    assert [shot_kind(s) for s in mine] == ["forehand", "forehand", "backhand", "backhand", "forehand volley", "backhand volley"]

    # in match mode the same sequence would have called the wide and long balls good because play went on
    assert [s.result for s in build_shots(rallies[0], "singles") if s.player == "s"][:3] == ["in", "in", "in"]

    report = lesson_breakdown(shots, PLAYERS)["s"]
    assert report["total"] == dict(shots=6, judged=5, made=2, in_pct=40.0, net=1, long=1, wide=1, not_seen=1,
                                   avg_speed_kmh=report["total"]["avg_speed_kmh"])
    assert report["by_kind"]["forehand"]["shots"] == 2 and report["by_kind"]["forehand"]["in_pct"] == 50.0
    assert report["by_kind"]["backhand"]["in_pct"] == 0.0 and report["by_kind"]["backhand"]["net"] == 1
    assert report["by_kind"]["forehand volley"]["in_pct"] == 100.0
    assert report["by_kind"]["backhand volley"]["not_seen"] == 1 and report["by_kind"]["backhand volley"]["in_pct"] is None
    assert report["by_hit_zone"]["baseline"]["shots"] == 4 and report["by_hit_zone"]["at the net"]["shots"] == 2
    assert report["by_depth"] == {"deep": report["by_depth"]["deep"], "short": report["by_depth"]["short"]}
    assert report["by_depth"]["deep"]["shots"] == 1 and report["by_depth"]["short"]["shots"] == 1
    assert report["shots"][1]["result"] == "wide" and report["shots"][4]["hit_zone"] == "at the net"
