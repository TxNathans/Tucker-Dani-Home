"""Turn a match record into the full stat breakdown for singles and doubles."""
from __future__ import annotations

from collections import Counter, defaultdict

from .schema import DOUBLES_HALF_WIDTH, HALF_LENGTH, SERVICE_LINE, SINGLES_HALF_WIDTH, Match, Point, Shot
from .scoring import Situation, replay, score_line

NET_ZONE_M = 4.5          # closer to the net than this counts as "at net"
DEEP_ZONE_M = 9.14        # last 2.74 m (9 ft) before the baseline
MIDDLE_HALF_WIDTH = 1.37
RALLY_BUCKETS = (("0-4", 0, 4), ("5-8", 5, 8), ("9+", 9, 10_000))


def pct(num: float, den: float) -> float | None:
    return round(100.0 * num / den, 1) if den else None


def avg(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 1) if values else None


def norm(pos, hitter_pos):
    """Rotate court coordinates so the hitter stands at negative y hitting toward positive y; +x is the hitter's right."""
    if pos is None:
        return None
    flip = hitter_pos is not None and hitter_pos[1] > 0
    return (-pos[0], -pos[1]) if flip else (pos[0], pos[1])


def serves_of(point: Point) -> list[Shot]:
    return [s for s in point.shots if s.stroke == "serve"]


def rally_shots(point: Point) -> list[Shot]:
    """Shots in the live rally: the serve that went in, and everything after it."""
    serves = serves_of(point)
    if not serves:
        return list(point.shots)
    start = point.shots.index(serves[-1])
    return point.shots[start:] if serves[-1].result == "in" else []


def rally_length(point: Point) -> int:
    """Match Charting Project convention: the serve counts, errors do not. Double fault = 0, ace = 1."""
    return sum(1 for s in rally_shots(point) if s.result == "in")


def returner_of(point: Point) -> str | None:
    shots = rally_shots(point)
    return shots[1].player if len(shots) > 1 else point.receiver


def serve_side(point: Point, sit: Situation) -> str:
    serves = serves_of(point)
    if serves and serves[0].hit_pos is not None:
        x = norm(serves[0].hit_pos, serves[0].hit_pos)[0]
        return "deuce" if x > 0 else "ad"
    return "deuce" if sum(sit.points) % 2 == 0 else "ad"


def serve_placement(serve: Shot) -> str | None:
    """wide / body / T by thirds of the service box."""
    b = norm(serve.bounce_pos, serve.hit_pos)
    if b is None or serve.result != "in":
        return None
    off_centre = abs(b[0])
    return "T" if off_centre < SINGLES_HALF_WIDTH / 3 else "body" if off_centre < 2 * SINGLES_HALF_WIDTH / 3 else "wide"


def depth_zone(shot: Shot) -> str | None:
    b = norm(shot.bounce_pos, shot.hit_pos)
    if b is None or shot.result != "in" or shot.stroke == "serve":
        return None
    return "short" if b[1] < SERVICE_LINE else "mid" if b[1] < DEEP_ZONE_M else "deep"


def direction(shot: Shot) -> str | None:
    h, b = norm(shot.hit_pos, shot.hit_pos), norm(shot.bounce_pos, shot.hit_pos)
    if h is None or b is None or shot.stroke == "serve":
        return None
    if abs(b[0]) < MIDDLE_HALF_WIDTH:
        return "middle"
    if abs(h[0]) < 0.8:
        return "from_centre"
    return "down_the_line" if (h[0] > 0) == (b[0] > 0) else "cross_court"


def at_net(pos) -> bool:
    return pos is not None and abs(pos[1]) < NET_ZONE_M


def is_net_shot(shot: Shot) -> bool:
    return shot.stroke != "serve" and (shot.contact in ("volley", "half_volley", "overhead") or at_net(shot.hit_pos))


def formation_of(match: Match, point: Point) -> str | None:
    """Doubles serving formation from where the server's partner stands at the serve."""
    if point.formation:
        return point.formation
    serves = serves_of(point)
    if match.format != "doubles" or not serves or not serves[0].player_positions:
        return None
    serve = serves[0]
    partner = next((p.id for p in match.team_players(match.team_of(point.server)) if p.id != point.server), None)
    server_pos = serve.hit_pos or serve.player_positions.get(point.server)
    partner_pos = serve.player_positions.get(partner)
    if server_pos is None or partner_pos is None:
        return None
    s, p = norm(server_pos, server_pos), norm(partner_pos, server_pos)
    if abs(p[1]) > SERVICE_LINE + 1.0:
        return "both_back"
    if abs(p[0]) < 0.9:
        return "i_formation"
    return "australian" if (p[0] > 0) == (s[0] > 0) else "standard"


def is_poach(match: Match, point: Point, shot: Shot) -> bool:
    """A net player's volley taken on the other side of the centre line from where they started the point."""
    if shot.poach:
        return True
    if match.format != "doubles" or not is_net_shot(shot) or shot.hit_pos is None:
        return False
    serves = serves_of(point)
    start = serves[0].player_positions.get(shot.player) if serves else None
    if start is None or not at_net(start) or abs(start[0]) < 0.9:
        return False
    return (start[0] > 0) != (shot.hit_pos[0] > 0) and abs(shot.hit_pos[0]) > 0.3


class MatchStats:
    def __init__(self, match: Match):
        self.match = match
        self.sits, self.final = replay(match)
        self.points = list(zip(match.points, self.sits))

    # ---- one side (a single player, or a whole team) ----------------------
    def side(self, members: set[str], team: int) -> dict:
        m = self.match
        serve = dict(points=0, first_in=0, first_won=0, second_played=0, second_won=0, aces=0, double_faults=0,
                     unreturned=0, won=0)
        placement = {side: {z: dict(count=0, won=0) for z in ("wide", "body", "T")} for side in ("deuce", "ad")}
        speeds = {1: [], 2: []}
        ret = dict(points=0, in_play=0, attempts=0, won=0, vs_first=0, vs_first_won=0, vs_second=0, vs_second_won=0, winners=0)
        pressure = dict(bp_faced=0, bp_saved=0, bp_chances=0, bp_converted=0, deuce_points=0, deuce_won=0,
                        game_points=0, game_points_won=0, set_points=0, set_points_won=0)
        games = dict(service_games=0, holds=0, return_games=0, breaks=0)
        ends = Counter()
        by_stroke = defaultdict(lambda: dict(shots=0, in_play=0, winners=0, forced_errors=0, unforced_errors=0, speeds=[]))
        error_types = Counter()
        depth, direct, contacts = Counter(), Counter(), Counter()
        net = dict(points=0, won=0, shots=0)
        buckets = {name: dict(points=0, won=0) for name, _, _ in RALLY_BUCKETS}
        plus_one = dict(points=0, forehand=0, won=0)
        won = total = 0
        streak = best_streak = 0
        distance = 0.0

        for point, sit in self.points:
            total += 1
            point_won = point.winner_team == team
            won += point_won
            streak = streak + 1 if point_won else 0
            best_streak = max(best_streak, streak)
            distance += sum(v for k, v in point.distance_m.items() if k in members)
            length = rally_length(point)
            for name, lo, hi in RALLY_BUCKETS:
                if lo <= length <= hi:
                    buckets[name]["points"] += 1
                    buckets[name]["won"] += point_won
            serves = serves_of(point)
            serving = point.server in members
            returning = returner_of(point) in members if returner_of(point) else (not serving and m.team_of(point.server) != team
                                                                                and len(members) == len(m.team_players(team)))
            # --- serving
            if serving:
                serve["points"] += 1
                serve["won"] += point_won
                first_in = bool(serves) and serves[0].result == "in"
                if first_in:
                    serve["first_in"] += 1
                    serve["first_won"] += point_won
                elif serves:
                    serve["second_played"] += 1
                    serve["second_won"] += point_won
                serve["aces"] += point.end_type == "ace"
                serve["double_faults"] += point.end_type == "double_fault"
                serve["unreturned"] += bool(serves) and serves[-1].result == "in" and length == 1
                for s in serves:
                    if s.speed_kmh and s.serve_number in (1, 2):
                        speeds[s.serve_number].append(s.speed_kmh)
                if serves and serves[-1].result == "in":
                    zone = serve_placement(serves[-1])
                    if zone:
                        cell = placement[serve_side(point, sit)][zone]
                        cell["count"] += 1
                        cell["won"] += point_won
                live = rally_shots(point)
                if len(live) >= 3 and live[2].player in members:
                    plus_one["points"] += 1
                    plus_one["forehand"] += live[2].stroke == "forehand"
                    plus_one["won"] += point_won
                if sit.break_point:
                    pressure["bp_faced"] += 1
                    pressure["bp_saved"] += point_won
            # --- returning
            if returning and serves and serves[-1].result == "in":
                ret["points"] += 1
                ret["won"] += point_won
                live = rally_shots(point)
                if len(live) > 1:
                    ret["attempts"] += 1
                    ret["in_play"] += live[1].result == "in"
                    ret["winners"] += point.end_type == "winner" and length == 2 and point.end_player in members
                first_in = serves[0].result == "in"
                key = "vs_first" if first_in else "vs_second"
                ret[key] += 1
                ret[key + "_won"] += point_won
            if m.team_of(point.server) != team and sit.break_point and (returning or len(members) > 1 or m.format == "singles"):
                pressure["bp_chances"] += 1
                pressure["bp_converted"] += point_won
            # --- pressure shared by the team
            if sit.deuce:
                pressure["deuce_points"] += 1
                pressure["deuce_won"] += point_won
            if sit.game_point and m.team_of(point.server) == team and serving:
                pressure["game_points"] += 1
                pressure["game_points_won"] += point_won
            if sit.set_point_team == team:
                pressure["set_points"] += 1
                pressure["set_points_won"] += point_won
            if sit.game_won_by is not None and not sit.tiebreak:
                if serving:
                    games["service_games"] += 1
                    games["holds"] += sit.game_won_by == team
                elif m.team_of(point.server) != team:
                    games["return_games"] += 1
                    games["breaks"] += sit.game_won_by == team
            # --- how points ended
            if point.end_player in members:
                ends[point.end_type] += 1
            # --- shots
            went_to_net = False
            for shot in point.shots:
                if shot.player not in members:
                    continue
                row = by_stroke[shot.stroke]
                row["shots"] += 1
                row["in_play"] += shot.result == "in"
                if shot.speed_kmh:
                    row["speeds"].append(shot.speed_kmh)
                if shot.result in ("net", "long", "wide"):
                    error_types[shot.result] += 1
                contacts[shot.contact] += 1
                zone, way = depth_zone(shot), direction(shot)
                if zone:
                    depth[zone] += 1
                if way:
                    direct[way] += 1
                if is_net_shot(shot):
                    went_to_net = True
                    net["shots"] += 1
            if point.end_player in members and point.shots:
                last = next((s for s in reversed(point.shots) if s.player == point.end_player), None)
                if last is not None and point.end_type in ("winner", "forced_error", "unforced_error"):
                    by_stroke[last.stroke][{"winner": "winners", "forced_error": "forced_errors",
                                            "unforced_error": "unforced_errors"}[point.end_type]] += 1
            if went_to_net:
                net["points"] += 1
                net["won"] += point_won

        winners = ends["winner"] + ends["ace"]
        unforced = ends["unforced_error"] + ends["double_fault"]
        strokes = {}
        for name, row in by_stroke.items():
            strokes[name] = dict(shots=row["shots"], in_pct=pct(row["in_play"], row["shots"]), winners=row["winners"],
                                 forced_errors=row["forced_errors"], unforced_errors=row["unforced_errors"],
                                 avg_speed_kmh=avg(row["speeds"]), max_speed_kmh=max(row["speeds"]) if row["speeds"] else None)
        return dict(
            points=dict(won=won, total=total, won_pct=pct(won, total), longest_streak=best_streak,
                        winners=winners, forced_errors=ends["forced_error"], unforced_errors=unforced,
                        winner_to_ue_ratio=round(winners / unforced, 2) if unforced else None,
                        aggressive_margin=winners - unforced),
            serve=dict(
                points=serve["points"], points_won_pct=pct(serve["won"], serve["points"]),
                first_serve_in_pct=pct(serve["first_in"], serve["points"]),
                first_serve_won_pct=pct(serve["first_won"], serve["first_in"]),
                second_serve_won_pct=pct(serve["second_won"], serve["second_played"]),
                aces=serve["aces"], double_faults=serve["double_faults"],
                unreturned_pct=pct(serve["unreturned"], serve["points"]),
                first_serve_avg_kmh=avg(speeds[1]), first_serve_max_kmh=max(speeds[1]) if speeds[1] else None,
                second_serve_avg_kmh=avg(speeds[2]),
                service_games=games["service_games"], hold_pct=pct(games["holds"], games["service_games"]),
                break_points_faced=pressure["bp_faced"], break_points_saved=pressure["bp_saved"],
                placement={side: {z: dict(count=c["count"], won_pct=pct(c["won"], c["count"])) for z, c in zones.items()}
                           for side, zones in placement.items()},
                serve_plus_one=dict(points=plus_one["points"], forehand_pct=pct(plus_one["forehand"], plus_one["points"]),
                                    won_pct=pct(plus_one["won"], plus_one["points"])),
            ),
            ret=dict(
                points=ret["points"], points_won_pct=pct(ret["won"], ret["points"]),
                returns_in_pct=pct(ret["in_play"], ret["attempts"]),
                won_vs_first_serve_pct=pct(ret["vs_first_won"], ret["vs_first"]),
                won_vs_second_serve_pct=pct(ret["vs_second_won"], ret["vs_second"]),
                return_winners=ret["winners"], return_games=games["return_games"], breaks=games["breaks"],
                break_points_chances=pressure["bp_chances"], break_points_converted=pressure["bp_converted"],
            ),
            pressure=dict(
                deuce_points_won_pct=pct(pressure["deuce_won"], pressure["deuce_points"]), deuce_points=pressure["deuce_points"],
                game_points_won_pct=pct(pressure["game_points_won"], pressure["game_points"]),
                set_points=pressure["set_points"], set_points_won=pressure["set_points_won"],
            ),
            strokes=strokes,
            errors=dict(net=error_types["net"], long=error_types["long"], wide=error_types["wide"]),
            depth=dict(depth), direction=dict(direct), contacts=dict(contacts),
            net=dict(points=net["points"], won_pct=pct(net["won"], net["points"]), shots=net["shots"]),
            rally={name: dict(points=b["points"], won_pct=pct(b["won"], b["points"])) for name, b in buckets.items()},
            movement=dict(distance_m=round(distance, 1), per_point_m=round(distance / total, 1) if total else None),
        )

    # ---- doubles-only analysis --------------------------------------------
    def doubles(self) -> dict:
        m = self.match
        out = {}
        for team in (0, 1):
            ids = {p.id for p in m.team_players(team)}
            formations = defaultdict(lambda: dict(points=0, won=0))
            poaches = defaultdict(lambda: dict(attempts=0, won=0))
            first_volley = dict(chances=0, made=0, won_when_made=0)
            targeted = defaultdict(lambda: dict(shots=0, points_won=0))
            end_position = defaultdict(lambda: dict(points=0, won=0))
            finishers = defaultdict(lambda: dict(winners=0, errors=0))
            return_dir = Counter()
            middle = dict(shots=0, won=0)
            lobs = dict(shots=0, won=0)
            for point, sit in self.points:
                won = point.winner_team == team
                live = rally_shots(point)
                if m.team_of(point.server) == team:
                    f = formation_of(m, point)
                    if f:
                        formations[f]["points"] += 1
                        formations[f]["won"] += won
                    # first volley: the serving team's first shot after the return
                    if len(live) >= 3 and live[1].result == "in":
                        third = live[2]
                        if is_net_shot(third):
                            first_volley["chances"] += 1
                            first_volley["made"] += third.result == "in"
                            first_volley["won_when_made"] += third.result == "in" and won
                elif len(live) >= 2 and live[1].player in ids:
                    way = "lob" if live[1].contact == "lob" else direction(live[1])
                    if way:
                        return_dir[way] += 1
                for i, shot in enumerate(point.shots):
                    if shot.player in ids:
                        if is_poach(m, point, shot):
                            poaches[shot.player]["attempts"] += 1
                            poaches[shot.player]["won"] += won
                        if shot.stroke != "serve" and direction(shot) == "middle":
                            middle["shots"] += 1
                            middle["won"] += won
                        if shot.contact == "lob":
                            lobs["shots"] += 1
                            lobs["won"] += won
                    elif shot.stroke != "serve" and shot.result == "in" and i + 1 < len(point.shots):
                        target = point.shots[i + 1].player
                        if target in ids:
                            targeted[target]["shots"] += 1
                if point.end_player in ids:
                    key = "winners" if point.end_type in ("winner", "ace") else "errors"
                    finishers[point.end_player][key] += 1
                # team shape when the point ended
                last = next((s for s in reversed(point.shots) if s.player_positions), None)
                if last:
                    up = sum(at_net(last.player_positions.get(pid)) for pid in ids if pid in last.player_positions)
                    shape = {2: "both_at_net", 1: "one_up_one_back", 0: "both_back"}[up]
                    end_position[shape]["points"] += 1
                    end_position[shape]["won"] += won
                # who the other team went after: credit the point result to the last target
                opp_shots = [(i, s) for i, s in enumerate(point.shots) if s.player not in ids and s.stroke != "serve"
                             and i + 1 < len(point.shots) and point.shots[i + 1].player in ids]
                for pid in {point.shots[i + 1].player for i, _ in opp_shots}:
                    targeted[pid]["points_won"] += won
            total_targets = sum(v["shots"] for v in targeted.values())
            out[str(team)] = dict(
                serving_formations={k: dict(points=v["points"], won_pct=pct(v["won"], v["points"])) for k, v in formations.items()},
                poaches={k: dict(attempts=v["attempts"], won_pct=pct(v["won"], v["attempts"])) for k, v in poaches.items()},
                first_volley=dict(chances=first_volley["chances"], made_pct=pct(first_volley["made"], first_volley["chances"]),
                                  won_when_made_pct=pct(first_volley["won_when_made"], first_volley["made"])),
                targeted={k: dict(shots=v["shots"], share_pct=pct(v["shots"], total_targets)) for k, v in targeted.items()},
                team_shape_at_point_end={k: dict(points=v["points"], won_pct=pct(v["won"], v["points"])) for k, v in end_position.items()},
                point_enders={k: dict(v) for k, v in finishers.items()},
                return_direction=dict(return_dir),
                middle_balls=dict(shots=middle["shots"], points_won_pct=pct(middle["won"], middle["shots"])),
                lobs=dict(shots=lobs["shots"], points_won_pct=pct(lobs["won"], lobs["shots"])),
            )
        return out

    # ---- everything --------------------------------------------------------
    def overview(self) -> dict:
        m = self.match
        lengths = [rally_length(p) for p in m.points]
        durations = [p.t_end - p.t_start for p in m.points if p.t_end > p.t_start]
        playing = sum(durations)
        gaps = [b.t_start - a.t_end for a, b in zip(m.points, m.points[1:]) if b.t_start > a.t_end > 0]
        total_time = m.duration_s or (m.points[-1].t_end - m.points[0].t_start if m.points else 0)
        return dict(
            format=m.format, title=m.title, score=score_line(self.final), winner_team=self.final.winner,
            sets=[list(s) for s in self.final.set_scores], points=len(m.points),
            avg_rally=avg(lengths), longest_rally=max(lengths) if lengths else 0,
            rally_histogram=dict(sorted(Counter(lengths).items())),
            duration_s=round(total_time, 1) if total_time else None, playing_time_s=round(playing, 1),
            avg_point_s=avg(durations), avg_between_points_s=avg(gaps),
            work_rest_ratio=round(playing / (total_time - playing), 2) if total_time and total_time > playing > 0 else None,
        )

    def timeline(self) -> list[dict]:
        rows, momentum = [], 0
        for i, (point, sit) in enumerate(self.points):
            momentum += 1 if point.winner_team == 0 else -1
            rows.append(dict(
                n=i + 1, set=sit.set_no, game=sit.game_no, games=list(sit.games), score=sit.score_text, server=point.server,
                winner_team=point.winner_team, end_type=point.end_type, end_player=point.end_player,
                rally=rally_length(point), break_point=sit.break_point, t=round(point.t_start, 1), momentum=momentum,
            ))
        return rows

    def compute(self) -> dict:
        m = self.match
        result = dict(
            overview=self.overview(),
            teams={str(t): dict(players=[p.name for p in m.team_players(t)],
                                **self.side({p.id for p in m.team_players(t)}, t)) for t in (0, 1)},
            players={p.id: dict(name=p.name, team=p.team, **self.side({p.id}, p.team)) for p in m.players},
            timeline=self.timeline(),
        )
        if m.format == "doubles":
            result["doubles"] = self.doubles()
        result["insights"] = insights(result, m)
        return result


def insights(stats: dict, match: Match) -> list[str]:
    """Plain-language rundown of the numbers that decided the match."""
    out = []
    names = {str(t): " / ".join(p.name for p in match.team_players(t)) for t in (0, 1)}
    for t in ("0", "1"):
        s, who = stats["teams"][t], names[t]
        sv, rt = s["serve"], s["ret"]
        if sv["first_serve_won_pct"] is not None and sv["second_serve_won_pct"] is not None:
            gap = sv["first_serve_won_pct"] - sv["second_serve_won_pct"]
            if gap >= 20:
                out.append(f"{who} won {sv['first_serve_won_pct']}% behind the first serve but only {sv['second_serve_won_pct']}% "
                           f"behind the second. First-serve percentage ({sv['first_serve_in_pct']}%) is the lever.")
        if sv["double_faults"] and sv["points"] and sv["double_faults"] / sv["points"] > 0.08:
            out.append(f"{who} gave away {sv['double_faults']} points on double faults ({pct(sv['double_faults'], sv['points'])}% of service points).")
        p = s["points"]
        if p["unforced_errors"] and p["winners"] is not None and p["unforced_errors"] >= 2 * max(p["winners"], 1):
            out.append(f"{who} made {p['unforced_errors']} unforced errors against {p['winners']} winners. Cutting errors matters more than adding winners.")
        worst = max(s["strokes"].items(), key=lambda kv: kv[1]["unforced_errors"], default=None)
        if worst and worst[1]["unforced_errors"] >= 3 and p["unforced_errors"] and worst[1]["unforced_errors"] / p["unforced_errors"] >= 0.5:
            out.append(f"{worst[1]['unforced_errors']} of {who}'s {p['unforced_errors']} unforced errors came off the {worst[0]}.")
        errs = s["errors"]
        if sum(errs.values()) >= 5:
            kind, count = max(errs.items(), key=lambda kv: kv[1])
            if count / sum(errs.values()) >= 0.5:
                tip = {"net": "aim higher over the net", "long": "add spin or take pace off", "wide": "play bigger targets"}[kind]
                out.append(f"{who}'s misses went mostly {kind} ({count} of {sum(errs.values())}): {tip}.")
        r = s["rally"]
        short, long_ = r["0-4"], r["9+"]
        if short["points"] >= 5 and long_["points"] >= 5 and short["won_pct"] is not None and long_["won_pct"] is not None:
            if short["won_pct"] - long_["won_pct"] >= 15:
                out.append(f"{who} won {short['won_pct']}% of short points (0-4 shots) but {long_['won_pct']}% of long rallies (9+). Keep points short.")
            elif long_["won_pct"] - short["won_pct"] >= 15:
                out.append(f"{who} won {long_['won_pct']}% of long rallies but {short['won_pct']}% of short points. Serve and return are costing points.")
        n = s["net"]
        if n["points"] >= 5 and n["won_pct"] is not None:
            verdict = "Coming forward is working." if n["won_pct"] >= 60 else "Net points are a net loss right now." if n["won_pct"] < 45 else ""
            out.append(f"{who} won {n['won_pct']}% of {n['points']} points played at the net. {verdict}".strip())
        if rt["break_points_chances"] >= 3:
            out.append(f"{who} converted {rt['break_points_converted']} of {rt['break_points_chances']} break points.")
    if "doubles" in stats:
        for t in ("0", "1"):
            d, who = stats["doubles"][t], names[t]
            if len(d["targeted"]) == 2:
                (a, av), (b, bv) = sorted(d["targeted"].items(), key=lambda kv: -kv[1]["shots"])
                if av["share_pct"] and av["share_pct"] >= 60:
                    out.append(f"Opponents sent {av['share_pct']}% of their shots to {match.player(a).name}, not {match.player(b).name}.")
            forms = {k: v for k, v in d["serving_formations"].items() if v["points"] >= 4}
            if len(forms) >= 2:
                best = max(forms.items(), key=lambda kv: kv[1]["won_pct"] or 0)
                out.append(f"{who}'s best serving formation was {best[0].replace('_', ' ')} ({best[1]['won_pct']}% of {best[1]['points']} points).")
            total_poach = sum(v["attempts"] for v in d["poaches"].values())
            if total_poach >= 3:
                wonp = sum(round((v["won_pct"] or 0) * v["attempts"] / 100) for v in d["poaches"].values())
                out.append(f"{who} poached {total_poach} times and won {wonp} of those points.")
            fv = d["first_volley"]
            if fv["chances"] >= 4 and fv["made_pct"] is not None:
                out.append(f"{who} made {fv['made_pct']}% of first volleys and won {fv['won_when_made_pct']}% of points when they did.")
    return out


def compute(match: Match) -> dict:
    return MatchStats(match).compute()
