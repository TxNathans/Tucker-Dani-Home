from tennisvision.stats.engine import compute
from tennisvision.stats.positioning import ideal_recovery_x, positioning, zone_of
from tennisvision.stats.schema import Match, Player, Point, Rules, Shot
from tennisvision.stats.strategy import recommendations


def test_ideal_recovery_is_crosscourt_of_centre():
    assert abs(ideal_recovery_x((0.0, 11.885))) < 0.01
    wide_right = ideal_recovery_x((4.0, 11.885))       # opponent out wide on my right
    assert -1.5 < wide_right < -0.5                     # so I shade left, toward the crosscourt
    assert abs(ideal_recovery_x((-4.0, 11.885)) + wide_right) < 0.01


def test_zones():
    assert zone_of((0, -2.0)) == "net"
    assert zone_of((0, -8.0)) == "no_mans_land"
    assert zone_of((0, -12.0)) == "baseline"
    assert zone_of((0, -15.5)) == "deep_behind"


def singles_match(ann_x_when_bea_hits: float, ann_y: float = -12.2, n_points: int = 8) -> Match:
    """Bea (far end) hits every rally ball from her right corner (x=-4 in court coordinates). Ann stands where told."""
    m = Match(format="singles", players=[Player("a", "Ann", 0), Player("b", "Bea", 1)], rules=Rules(best_of=1))
    for k in range(n_points):
        pos_serve = {"a": (1.0, -12.0), "b": (-3.0, 12.5)}
        shots = [Shot("a", stroke="serve", contact="serve", serve_number=1, hit_pos=(1.0, -12.0), bounce_pos=(-2.0, 5.5),
                      player_positions=pos_serve)]
        for i in range(3):
            snap = {"a": (ann_x_when_bea_hits, ann_y), "b": (-4.0, 11.9)}
            shots.append(Shot("b", stroke="forehand", hit_pos=(-4.0, 11.9), bounce_pos=(3.0, -10.0), player_positions=snap))
            shots.append(Shot("a", stroke="backhand", hit_pos=(3.0, -11.5), bounce_pos=(-3.5, 10.5),
                              player_positions={"a": (3.0, -11.5), "b": (-4.0, 11.9)}))
        winner = k % 2
        m.points.append(Point(server="a", winner_team=winner, end_type="winner", end_player="a" if winner == 0 else "b",
                              shots=shots, receiver="b"))
    return m


def test_recovery_feedback_singles():
    # Bea is at court x=-4, far end. From Ann's end that is Ann's left, so the ideal spot is about +1 (right of centre).
    bad = singles_match(ann_x_when_bea_hits=-2.5)        # Ann parks on the same side as Bea: crosscourt wide open
    pos = positioning(bad)
    rec = pos["players"]["a"]["recovery"]
    assert rec["samples"] == 24 and rec["avg_error_m"] > 3.0 and rec["lean_m"] > 3.0
    recs = recommendations(bad, compute(bad), pos)
    top = next(r for r in recs if r["title"].startswith("Ann: recover"))
    assert top["priority"] == 1 and "crosscourt" in top["evidence"]

    good = singles_match(ann_x_when_bea_hits=1.0)
    pos = positioning(good)
    assert pos["players"]["a"]["recovery"]["avg_error_m"] < 0.3
    assert not any(r["title"].startswith("Ann: recover") for r in recommendations(good, compute(good), pos))


def test_no_mans_land_and_deep_feedback():
    nml = singles_match(ann_x_when_bea_hits=1.0, ann_y=-8.5)
    pos = positioning(nml)
    assert pos["players"]["a"]["zones"]["no_mans_land"]["share_pct"] == 100.0
    assert any("no-man's land" in r["title"] for r in recommendations(nml, compute(nml), pos))
    deep = singles_match(ann_x_when_bea_hits=1.0, ann_y=-15.0)
    pos = positioning(deep)
    assert pos["players"]["a"]["recovery"]["avg_depth_m"] < -3.0
    assert any("move up to the baseline" in r["title"] for r in recommendations(deep, compute(deep), pos))


def doubles_match(gap: float, partner_x: float) -> Match:
    m = Match(format="doubles", rules=Rules(best_of=1), players=[
        Player("d", "Dani", 0), Player("p", "Pat", 0), Player("x", "Xi", 1), Player("y", "Yu", 1)])
    for k in range(10):
        serve_snap = {"d": (1.5, -12.0), "p": (-partner_x, -3.0), "x": (-3.0, 12.0), "y": (2.5, 6.4)}
        shots = [Shot("d", stroke="serve", contact="serve", serve_number=1, hit_pos=(1.5, -12.0), bounce_pos=(-2.0, 5.5),
                      player_positions=serve_snap)]
        for i in range(2):
            snap = {"d": (gap / 2, -11.5), "p": (-gap / 2, -11.5), "x": (-4.0, 11.5), "y": (2.5, 6.0)}
            shots.append(Shot("x", stroke="forehand", hit_pos=(-4.0, 11.5), bounce_pos=(0.2, -9.0), player_positions=snap))
            shots.append(Shot("d", stroke="forehand", hit_pos=(0.5, -11.0), bounce_pos=(-3.0, 10.0),
                              player_positions={"d": (0.5, -11.0), "p": (-gap / 2, -11.5), "x": (-4.0, 11.5), "y": (2.5, 6.0)}))
        m.points.append(Point(server="d", winner_team=k % 2, end_type="winner", end_player="d" if k % 2 == 0 else "x",
                              shots=shots, receiver="x"))
    return m


def test_doubles_spacing_and_net_player_feedback():
    m = doubles_match(gap=7.0, partner_x=4.5)
    pos = positioning(m)
    team = pos["teams"]["0"]
    assert team["partner_gap"]["avg_m"] == 7.0 and team["partner_gap"]["middle_open_pct"] == 100.0
    assert team["shapes"]["both_back"]["share_pct"] == 100.0
    assert team["server_partner"]["from_centre_m"] == 4.5
    titles = [r["title"] for r in recommendations(m, compute(m), pos) if r["title"].startswith("Dani / Pat")]
    assert any("close the middle" in t for t in titles)
    assert any("come off the alley" in t for t in titles)
    assert any("poach" in t for t in titles)

    ok = doubles_match(gap=4.0, partner_x=2.0)
    titles = [r["title"] for r in recommendations(ok, compute(ok), positioning(ok)) if r["title"].startswith("Dani / Pat")]
    assert not any("close the middle" in t or "come off the alley" in t for t in titles)
