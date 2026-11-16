from tennisvision.match.rally import Bounce, Hit, build_points, build_shots, landing_result, split_rallies
from tennisvision.stats.engine import compute
from tennisvision.stats.schema import Match, Player, Rules

PLAYERS = [Player("a", "Ann", 0), Player("b", "Bea", 1)]


def test_landing_calls():
    # hitter at the near end (negative y)
    assert landing_result((3.0, 11.0), -11.0, "singles") == "in"
    assert landing_result((4.2, 11.0), -11.0, "singles") == "in"          # on the line
    assert landing_result((4.6, 11.0), -11.0, "singles") == "wide"
    assert landing_result((4.6, 11.0), -11.0, "doubles") == "in"          # the alley is good in doubles
    assert landing_result((0.0, 12.3), -11.0, "singles") == "long"
    assert landing_result((0.0, -2.0), -11.0, "singles") == "net"
    # hitter at the far end: the same calls mirrored
    assert landing_result((0.0, -12.3), 11.0, "singles") == "long"
    assert landing_result((0.0, 2.0), 11.0, "singles") == "net"
    # serve from the deuce side (right of the centre mark) must land in the box to the server's left
    assert landing_result((-2.0, 5.0), -11.9, "singles", serve_from_x=1.0) == "in"
    assert landing_result((2.0, 5.0), -11.9, "singles", serve_from_x=1.0) == "wide"
    assert landing_result((-2.0, 7.0), -11.9, "singles", serve_from_x=1.0) == "long"
    assert landing_result((2.0, -5.0), 11.9, "singles", serve_from_x=-1.0) == "in"   # far-end server, deuce side


def test_rally_to_scored_points():
    hits, bounces = [], []
    # point 1 at t=0: first serve long, second serve in, return, Ann forehand winner
    hits += [Hit(0.0, "a", (1.0, -12.0), above_head=True)]
    bounces += [Bounce(0.6, (-2.0, 7.2))]
    hits += [Hit(8.0, "a", (1.0, -12.0), above_head=True), Hit(9.0, "b", (-2.5, 11.5), stroke="backhand"),
             Hit(10.2, "a", (-1.0, -11.0), stroke="forehand")]
    bounces += [Bounce(8.6, (-2.0, 5.5)), Bounce(9.8, (-1.0, -9.0)), Bounce(11.0, (3.5, 10.5)), Bounce(11.9, (4.5, 14.0))]
    # point 2 at t=30: ace
    hits += [Hit(30.0, "a", (-1.0, -12.0), above_head=True)]
    bounces += [Bounce(30.6, (0.3, 6.0))]
    # point 3 at t=50: double fault
    hits += [Hit(50.0, "a", (1.0, -12.0), above_head=True), Hit(58.0, "a", (1.0, -12.0), above_head=True)]
    bounces += [Bounce(50.5, (-1.0, -1.0)), Bounce(58.6, (-4.9, 5.0))]
    # point 4 at t=80: serve, return, Ann volleys long (no bounce before her shot)
    hits += [Hit(80.0, "a", (-1.0, -12.0), above_head=True), Hit(81.0, "b", (2.0, 11.5), stroke="forehand"),
             Hit(81.9, "a", (0.5, -3.0), stroke="backhand")]
    bounces += [Bounce(80.6, (1.5, 5.8)), Bounce(82.6, (1.0, 12.6))]
    # a rally with no serve seen (camera started late): goes to review
    hits += [Hit(100.0, "b", (0.0, 11.0), stroke="forehand"), Hit(101.2, "a", (0.0, -11.0), stroke="forehand")]
    bounces += [Bounce(100.8, (0.0, -8.0))]

    rallies = split_rallies(hits, bounces)
    assert len(rallies) == 7
    points, review = build_points(rallies, PLAYERS, "singles")
    assert [p.end_type for p in points] == ["winner", "ace", "double_fault", "unforced_error"]
    assert [p.winner_team for p in points] == [0, 0, 1, 1]
    p1 = points[0]
    assert [s.serve_number for s in p1.shots[:2]] == [1, 2] and p1.shots[0].result == "long"
    assert p1.shots[2].is_return and p1.receiver == "b" and p1.shots[3].contact == "groundstroke"
    assert points[3].shots[2].contact == "volley" and points[3].shots[2].result == "long"
    assert len(review) == 1 and review[0]["reason"] == "no serve seen at the start"
    assert 30 < p1.shots[1].speed_kmh < 130

    stats = compute(Match(format="singles", players=PLAYERS, points=points, rules=Rules(best_of=1)))
    ann = stats["players"]["a"]
    assert ann["serve"]["first_serve_in_pct"] == 50.0 and ann["serve"]["aces"] == 1 and ann["serve"]["double_faults"] == 1
    assert stats["timeline"][-1]["score"] == "30-15"
    assert stats["overview"]["points"] == 4


def test_mid_rally_start_is_not_a_serve():
    hits = [Hit(0.3, "a", (-1.0, -11.0), stroke="forehand"), Hit(1.9, "b", (0.0, 12.0), stroke="backhand")]
    shots = build_shots(split_rallies(hits, [Bounce(1.5, (0.0, 10.6))])[0], "singles")
    assert [s.stroke for s in shots] == ["forehand", "backhand"] and shots[0].result == "in"
