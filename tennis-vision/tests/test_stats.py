from tennisvision.stats.engine import compute, formation_of, rally_length, serve_placement
from tennisvision.stats.schema import Match, Player, Point, Rules, Shot
from tennisvision.stats.scoring import replay, score_line


def serve(player, n=1, result="in", hit=(1.0, -11.9), bounce=(-0.5, 5.5), speed=None, positions=None):
    return Shot(player=player, stroke="serve", contact="serve", serve_number=n, result=result, hit_pos=hit,
                bounce_pos=bounce, speed_kmh=speed, player_positions=positions or {})


def shot(player, stroke="forehand", result="in", hit=(0.0, 11.0), bounce=(2.0, -9.5), contact="groundstroke", positions=None):
    return Shot(player=player, stroke=stroke, contact=contact, result=result, hit_pos=hit, bounce_pos=bounce,
                player_positions=positions or {})


def singles():
    return Match(format="singles", players=[Player("a", "Ann", 0), Player("b", "Bea", 1)], rules=Rules(best_of=1))


def test_game_scoring_and_break_points():
    m = singles()
    # Ann serves: 15-0, 15-15, 15-30, 15-40 (two break points), 30-40, deuce, ad-out, break
    for winner in (0, 1, 1, 1, 0, 0, 1, 1):
        m.points.append(Point(server="a", winner_team=winner, shots=[serve("a")]))
    sits, state = replay(m)
    assert [s.score_text for s in sits] == ["0-0", "15-0", "15-15", "15-30", "15-40", "30-40", "Deuce", "Ad-Out"]
    assert [s.break_point for s in sits] == [False, False, False, False, True, True, False, True]
    assert sits[-1].game_won_by == 1 and state.games == [0, 1]
    stats = compute(m)
    assert stats["teams"]["0"]["serve"]["break_points_faced"] == 3
    assert stats["teams"]["0"]["serve"]["break_points_saved"] == 2
    assert stats["teams"]["1"]["ret"]["break_points_converted"] == 1
    assert stats["teams"]["0"]["serve"]["hold_pct"] == 0.0
    assert stats["teams"]["1"]["ret"]["breaks"] == 1


def test_set_tiebreak_and_match():
    m = singles()
    server = "a"
    for game in range(12):                       # hold every game to 6-6
        team = 0 if server == "a" else 1
        for _ in range(4):
            m.points.append(Point(server=server, winner_team=team))
        server = "b" if server == "a" else "a"
    for i in range(7):                           # tiebreak 7-0 to Ann
        m.points.append(Point(server="a", winner_team=0))
    sits, state = replay(m)
    assert sits[48].tiebreak and sits[48].score_text == "0-0"
    assert sits[-1].set_point_team == 0 and sits[-1].match_point_team == 0
    assert state.winner == 0 and score_line(state) == "7-6"


def test_no_ad_and_match_tiebreak():
    m = Match(format="doubles", players=[Player("a", "A", 0), Player("b", "B", 0), Player("c", "C", 1), Player("d", "D", 1)],
              rules=Rules(best_of=3, no_ad=True, final_set_tiebreak_points=10))
    for winner in (0, 0, 0, 1, 1, 1, 1):         # 40-40 then deciding point to the returners
        m.points.append(Point(server="a", winner_team=winner))
    sits, state = replay(m)
    assert sits[6].break_point and sits[6].game_point and state.games == [0, 1]


def test_serve_and_rally_numbers():
    m = singles()
    # 1: ace out wide on the deuce side
    m.points.append(Point(server="a", winner_team=0, end_type="ace", end_player="a",
                          shots=[serve("a", bounce=(-3.6, 5.0), speed=170)]))
    # 2: first serve fault, second serve in, 4-shot rally, Bea nets a backhand (unforced)
    m.points.append(Point(server="a", winner_team=0, end_type="unforced_error", end_player="b", shots=[
        serve("a", 1, "net", hit=(-1.0, -11.9), bounce=None, speed=165),
        serve("a", 2, "in", hit=(-1.0, -11.9), bounce=(0.4, 5.8), speed=120),
        shot("b", "backhand", hit=(1.0, 11.5), bounce=(-2.5, -10.5)),
        shot("a", "forehand", hit=(-2.5, -11.5), bounce=(3.0, 10.0)),
        shot("b", "backhand", "net", hit=(3.0, 11.0), bounce=None),
    ]))
    # 3: double fault
    m.points.append(Point(server="a", winner_team=1, end_type="double_fault", end_player="a",
                          shots=[serve("a", 1, "long", bounce=(-1.0, 7.0)), serve("a", 2, "net", bounce=None)]))
    # 4: Bea hits a return winner off a first serve
    m.points.append(Point(server="a", winner_team=1, end_type="winner", end_player="b", shots=[
        serve("a", hit=(-1.0, -11.9), bounce=(2.0, 5.5)), shot("b", "forehand", hit=(2.5, 11.0), bounce=(3.5, -10.0))]))
    assert [rally_length(p) for p in m.points] == [1, 3, 0, 2]
    assert serve_placement(m.points[0].shots[0]) == "wide"
    assert serve_placement(m.points[1].shots[1]) == "T"
    s = compute(m)
    ann, bea = s["players"]["a"], s["players"]["b"]
    assert ann["serve"]["first_serve_in_pct"] == 50.0
    assert ann["serve"]["first_serve_won_pct"] == 50.0
    assert ann["serve"]["second_serve_won_pct"] == 50.0
    assert ann["serve"]["aces"] == 1 and ann["serve"]["double_faults"] == 1
    assert ann["serve"]["unreturned_pct"] == 25.0
    assert ann["serve"]["first_serve_avg_kmh"] == 167.5
    assert ann["serve"]["placement"]["deuce"]["wide"] == {"count": 1, "won_pct": 100.0}
    assert ann["serve"]["placement"]["ad"]["T"] == {"count": 1, "won_pct": 100.0}
    assert ann["serve"]["serve_plus_one"] == {"points": 1, "forehand_pct": 100.0, "won_pct": 100.0}
    assert bea["ret"]["points"] == 3 and bea["ret"]["returns_in_pct"] == 100.0 and bea["ret"]["return_winners"] == 1
    assert bea["ret"]["won_vs_second_serve_pct"] == 0.0
    assert bea["strokes"]["backhand"]["unforced_errors"] == 1 and bea["errors"]["net"] == 1
    assert bea["points"]["winners"] == 1 and bea["points"]["unforced_errors"] == 1
    assert ann["points"]["unforced_errors"] == 1          # the double fault
    assert bea["depth"] == {"deep": 2}
    assert bea["direction"]["cross_court"] == 1 and bea["direction"]["down_the_line"] == 1
    assert s["overview"]["avg_rally"] == 1.5 and s["overview"]["longest_rally"] == 3


def doubles_match():
    return Match(format="doubles", rules=Rules(best_of=1), players=[
        Player("d", "Dani", 0), Player("p", "Partner", 0), Player("x", "Opp X", 1), Player("y", "Opp Y", 1)])


def test_doubles_formations_poach_and_targeting():
    m = doubles_match()
    standard = {"d": (1.5, -11.9), "p": (-2.5, -3.0), "x": (-3.0, 11.5), "y": (2.5, 6.0)}
    aussie = {"d": (1.5, -11.9), "p": (2.5, -3.0), "x": (-3.0, 11.5), "y": (2.5, 6.0)}
    i_form = {"d": (0.5, -11.9), "p": (0.2, -3.0), "x": (-3.0, 11.5), "y": (2.5, 6.0)}
    # 1: standard formation; X returns cross-court, Partner crosses the centre line and volleys a winner (poach)
    p1 = Point(server="d", winner_team=0, end_type="winner", end_player="p", shots=[
        serve("d", hit=(1.5, -11.9), bounce=(-2.0, 5.5), positions=standard),
        shot("x", "forehand", hit=(-3.0, 11.5), bounce=(2.0, -8.0)),
        shot("p", "forehand", contact="volley", hit=(1.2, -2.5), bounce=(0.3, 4.0),
             positions={"d": (2.0, -10.0), "p": (1.2, -2.5), "x": (-3.0, 11.0), "y": (2.5, 5.0)}),
    ])
    # 2: Australian; X's return goes at Dani twice, Dani errs
    p2 = Point(server="d", winner_team=1, end_type="unforced_error", end_player="d", shots=[
        serve("d", hit=(1.5, -11.9), bounce=(-2.0, 5.5), positions=aussie),
        shot("x", "backhand", hit=(-3.0, 11.5), bounce=(-3.0, -9.0)),
        shot("d", "backhand", hit=(-3.0, -11.0), bounce=(-3.0, 9.0)),
        shot("x", "forehand", hit=(-3.0, 11.0), bounce=(-2.0, -10.0)),
        shot("d", "backhand", "long", hit=(-2.0, -11.5), bounce=(-1.0, 12.5),
             positions={"d": (-2.0, -11.5), "p": (2.5, -3.0), "x": (-3.0, 11.0), "y": (2.5, 5.0)}),
    ])
    # 3: I-formation, ace
    p3 = Point(server="d", winner_team=0, end_type="ace", end_player="d",
               shots=[serve("d", hit=(0.5, -11.9), bounce=(-0.3, 6.0), positions=i_form)])
    m.points = [p1, p2, p3]
    assert [formation_of(m, p) for p in m.points] == ["standard", "australian", "i_formation"]
    s = compute(m)
    d = s["doubles"]["0"]
    assert d["serving_formations"]["standard"] == {"points": 1, "won_pct": 100.0}
    assert d["serving_formations"]["australian"] == {"points": 1, "won_pct": 0.0}
    assert d["poaches"] == {"p": {"attempts": 1, "won_pct": 100.0}}
    assert d["first_volley"] == {"chances": 1, "made_pct": 100.0, "won_when_made_pct": 100.0}
    assert d["targeted"]["d"]["shots"] == 2 and d["targeted"]["p"]["shots"] == 1
    assert d["targeted"]["d"]["share_pct"] == 66.7
    assert d["team_shape_at_point_end"]["one_up_one_back"]["points"] == 3   # the ace counts: shape at the serve
    assert d["point_enders"]["p"]["winners"] == 1 and d["point_enders"]["d"] == {"winners": 1, "errors": 1}
    assert s["players"]["p"]["net"] == {"points": 1, "won_pct": 100.0, "shots": 1}
    assert s["players"]["d"]["serve"]["points"] == 3 and s["players"]["p"]["serve"]["points"] == 0
    assert s["teams"]["0"]["points"]["won"] == 2
    assert s["doubles"]["1"]["return_direction"] == {"cross_court": 1, "down_the_line": 1}


def test_round_trip_json():
    m = doubles_match()
    m.points.append(Point(server="d", winner_team=0, shots=[serve("d", positions={"d": (1.0, -11.9)})]))
    again = Match.from_dict(m.to_dict())
    assert again.points[0].shots[0].player_positions["d"] == (1.0, -11.9)
    assert compute(again)["overview"]["points"] == 1
