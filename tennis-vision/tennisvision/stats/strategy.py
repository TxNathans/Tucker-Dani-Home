"""Coaching recommendations: where to stand and what to play, each tied to the numbers behind it."""
from __future__ import annotations

from .schema import Match

MIN_SAMPLES = 6


def _rec(area: str, priority: int, title: str, evidence: str, advice: str) -> dict:
    return dict(area=area, priority=priority, title=title, evidence=evidence, advice=advice)


def _player_recs(name: str, pos: dict, stats: dict, singles: bool) -> list[dict]:
    recs = []
    rec = pos["recovery"]
    if singles and rec["samples"] >= MIN_SAMPLES:
        if rec["avg_error_m"] is not None and rec["avg_error_m"] > 1.2:
            lean = rec["lean_m"] or 0.0
            if lean > 0.5:
                where = "You drift toward the side the opponent is hitting from, which leaves the crosscourt open."
                fix = "After each shot recover about a metre past the centre mark on the crosscourt side of the ball, and be there before the opponent makes contact."
            elif lean < -0.5:
                where = "You over-cover crosscourt and leave the line open."
                fix = "Recover closer to the centre mark; one step crosscourt of it is enough."
            else:
                where = "You are often still moving, or parked at the spot you hit from, when the opponent hits."
                fix = "Split step at the recovery spot (about a metre crosscourt of the centre mark) as the opponent starts the forward swing."
            recs.append(_rec("positioning", 1, f"{name}: recover to the right spot",
                             f"When the opponent hits, {name} is on average {rec['avg_error_m']} m from the ideal recovery position ({rec['samples']} shots). {where}", fix))
        if rec["avg_depth_m"] is not None and rec["avg_depth_m"] < -2.5:
            recs.append(_rec("positioning", 2, f"{name}: move up to the baseline",
                             f"{name} waits {abs(rec['avg_depth_m'])} m behind the baseline on average.",
                             "Standing that deep gives the opponent more angle and more time. Hold a position within a metre of the baseline and step back only for heavy, deep balls."))
    zones = pos["zones"]
    nml = zones.get("no_mans_land")
    if nml and nml["share_pct"] and nml["share_pct"] >= 25 and nml["points"] >= 4:
        base = zones.get("baseline", {})
        compare = f" against {base['points_won_pct']}% when set on the baseline" if base.get("points_won_pct") is not None else ""
        recs.append(_rec("positioning", 1, f"{name}: stop getting caught in no-man's land",
                         f"{name} was between the baseline and the service line on {nml['share_pct']}% of opponent shots, and won {nml['points_won_pct']}% of those points{compare}.",
                         "After a short ball, either keep moving forward to a volley position or get back behind the baseline. Do not stop in between: balls land at your feet there."))
    net = zones.get("net")
    if net and net["points"] >= 5 and net["points_won_pct"] is not None:
        if net["points_won_pct"] >= 60 and (net["share_pct"] or 0) < 25:
            recs.append(_rec("strategy", 2, f"{name}: come forward more",
                             f"{name} won {net['points_won_pct']}% of the {net['points']} points where they got to the net, but was there on only {net['share_pct']}% of opponent shots.",
                             "Look for the short ball and follow it in. The net is winning points."))
        elif net["points_won_pct"] < 40:
            close = pos["net_distance_m"]
            detail = f" Average distance from the net was {close} m." if close else ""
            recs.append(_rec("positioning", 2, f"{name}: fix the net position",
                             f"{name} won only {net['points_won_pct']}% of {net['points']} points at the net.{detail}",
                             "Approach behind deeper, lower balls, and set up about halfway between the net and the service line, shaded toward the side the ball is on."))
    ret = pos["return_position"]
    r = stats["ret"]
    if ret["samples"] >= 4 and ret["second_serve_m"] is not None and ret["first_serve_m"] is not None:
        if ret["second_serve_m"] <= ret["first_serve_m"] + 0.3 and (r["won_vs_second_serve_pct"] or 100) < 50:
            recs.append(_rec("positioning", 2, f"{name}: step in on second serves",
                             f"{name} returns second serves from the same depth as first serves ({ret['second_serve_m']} m vs {ret['first_serve_m']} m from the baseline) and wins {r['won_vs_second_serve_pct']}% of those points.",
                             "Move a metre or more inside your first-serve position for the second serve to take time away."))
    return recs


def _matchup_recs(name: str, me: dict, opp_name: str, opp: dict) -> list[dict]:
    recs = []
    sv = me["serve"]
    for side in ("deuce", "ad"):
        cells = {z: c for z, c in sv["placement"][side].items() if c["count"] >= 3 and c["won_pct"] is not None}
        if len(cells) >= 2:
            best = max(cells.items(), key=lambda kv: kv[1]["won_pct"])
            worst = min(cells.items(), key=lambda kv: kv[1]["won_pct"])
            if best[1]["won_pct"] - worst[1]["won_pct"] >= 25:
                recs.append(_rec("strategy", 2, f"{name}: serve {best[0]} on the {side} side",
                                 f"On the {side} side, serves {best[0]} won {best[1]['won_pct']}% ({best[1]['count']} serves) against {worst[1]['won_pct']}% {worst[0]} ({worst[1]['count']}).",
                                 f"Make {best[0]} the default on the {side} side and use {worst[0]} as the change-up."))
    wings = {k: v for k, v in opp["strokes"].items() if k in ("forehand", "backhand") and v["shots"] >= 5}
    if len(wings) == 2:
        rate = {k: (v["forced_errors"] + v["unforced_errors"]) / v["shots"] for k, v in wings.items()}
        weak = max(rate, key=rate.get)
        strong = min(rate, key=rate.get)
        total = sum(v["shots"] for v in wings.values())
        share = round(100 * wings[weak]["shots"] / total)
        if rate[weak] >= 1.5 * max(rate[strong], 0.01) and rate[weak] >= 0.12 and share < 60:
            recs.append(_rec("strategy", 1, f"{name}: play to {opp_name}'s {weak}",
                             f"{opp_name} missed {round(100 * rate[weak])}% of {weak}s against {round(100 * rate[strong])}% of {strong}s, yet only {share}% of balls went to the {weak}.",
                             f"Build points through the {weak} wing and save the {strong} side for when the court is open."))
    depth = me["depth"]
    hit = sum(depth.values())
    if hit >= 10 and depth.get("short", 0) / hit >= 0.4:
        recs.append(_rec("strategy", 2, f"{name}: hit deeper",
                         f"{round(100 * depth.get('short', 0) / hit)}% of {name}'s rally balls landed short of the service line.",
                         "Aim a metre higher over the net and a couple of metres inside the baseline. Depth keeps the opponent back and takes away their angles."))
    errs = me["errors"]
    missed = sum(errs.values())
    if missed >= 6 and errs["net"] / missed >= 0.5:
        recs.append(_rec("strategy", 2, f"{name}: clear the net by more",
                         f"{errs['net']} of {missed} misses went into the net.", "Net errors are the cheapest to fix: raise the target height, especially when stretched or on the run."))
    r = me["rally"]
    short, long_ = r["0-4"], r["9+"]
    if short["points"] >= 5 and long_["points"] >= 5 and short["won_pct"] is not None and long_["won_pct"] is not None:
        if short["won_pct"] - long_["won_pct"] >= 15:
            recs.append(_rec("strategy", 2, f"{name}: finish points early",
                             f"{name} won {short['won_pct']}% of points of 4 shots or fewer and {long_['won_pct']}% of rallies of 9 or more.",
                             "Play first-strike tennis: big first serve target, attack the first short ball."))
        elif long_["won_pct"] - short["won_pct"] >= 15:
            recs.append(_rec("strategy", 2, f"{name}: extend the rallies",
                             f"{name} won {long_['won_pct']}% of rallies of 9 or more shots and {short['won_pct']}% of points of 4 or fewer.",
                             "Get the return and the next ball in play with margin. The longer the point, the better the odds."))
    return recs


def _doubles_recs(names: str, tp: dict, d: dict, opp_names: str) -> list[dict]:
    recs = []
    if not tp:
        return recs
    gap = tp["partner_gap"]
    if gap["samples"] >= MIN_SAMPLES:
        if (gap["middle_open_pct"] or 0) >= 35:
            recs.append(_rec("positioning", 1, f"{names}: close the middle",
                             f"When level with each other, the partners were more than 5.5 m apart on {gap['middle_open_pct']}% of opponent shots (average gap {gap['avg_m']} m).",
                             "Stand about 3.5 to 4.5 m apart and give up the alleys before the middle: the middle ball is lower over the net and causes confusion. Agree who takes it (usually the forehand in the middle)."))
        elif (gap["stacked_pct"] or 0) >= 35:
            recs.append(_rec("positioning", 2, f"{names}: spread out",
                             f"The partners were less than 2.5 m apart on {gap['stacked_pct']}% of opponent shots.",
                             "Each player owns half the court. Too close together leaves both alleys open."))
    if tp["shift_samples"] >= MIN_SAMPLES and tp["shift_with_ball_m"] is not None and tp["shift_with_ball_m"] < 0.3:
        recs.append(_rec("positioning", 2, f"{names}: move together with the ball",
                         f"When the opponents hit from out wide, the team's centre shifted only {tp['shift_with_ball_m']} m toward that side.",
                         "Slide as a pair toward the side the ball is on, as if tied by a rope: the near player covers the line, the far player covers the middle."))
    shapes = {k: v for k, v in tp["shapes"].items() if v["points"] >= 4 and v["points_won_pct"] is not None}
    if len(shapes) >= 2:
        best = max(shapes.items(), key=lambda kv: kv[1]["points_won_pct"])
        most = max(shapes.items(), key=lambda kv: kv[1]["share_pct"] or 0)
        if best[0] != most[0] and best[1]["points_won_pct"] - most[1]["points_won_pct"] >= 15:
            label = lambda s: s.replace("_", " ")
            recs.append(_rec("strategy", 1, f"{names}: play more points {label(best[0])}",
                             f"{names} won {best[1]['points_won_pct']}% of points when {label(best[0])} but spent most of the time {label(most[0])} ({most[1]['points_won_pct']}% won).",
                             f"Make {label(best[0])} the default shape and work to get there within the first two shots."))
    sp = tp["server_partner"]
    if sp["samples"] >= 4 and sp["from_centre_m"] is not None:
        if sp["from_centre_m"] > 3.2:
            recs.append(_rec("positioning", 2, f"{names}: net player, come off the alley",
                             f"On serve the net partner stands {sp['from_centre_m']} m from the centre line, close to the alley.",
                             "Start in the middle of the service box, about 2 m from the centre line. From there a crosscourt return is within one step, which is what makes poaching possible."))
        if sp["from_net_m"] is not None and sp["from_net_m"] < 1.5:
            recs.append(_rec("positioning", 3, f"{names}: net player, back off the net a little",
                             f"On serve the net partner stands {sp['from_net_m']} m from the net.",
                             "About halfway back in the service box covers the lob and still lets you close forward on the volley."))
    rp = tp["receiver_partner"]
    if rp["samples"] >= 4 and rp["from_net_m"] is not None and not (4.5 <= rp["from_net_m"] <= 8.0):
        recs.append(_rec("positioning", 3, f"{names}: returner's partner, start on the service line",
                         f"The returner's partner starts {rp['from_net_m']} m from the net.",
                         "Start on the service line: close enough to move in after a good return, far enough back to defend a poach."))
    poach = sum(v["attempts"] for v in d["poaches"].values())
    serve_pts = sum(v["points"] for v in d["serving_formations"].values())
    if serve_pts >= 8 and poach == 0:
        recs.append(_rec("strategy", 2, f"{names}: poach",
                         f"No poaches in {serve_pts} service points.",
                         "Have the net player cross on at least one first serve per game, called with a hand signal. Even a failed poach makes the returner think about the net player."))
    if len(d["targeted"]) == 2:
        (a, av), (b, bv) = sorted(d["targeted"].items(), key=lambda kv: -kv[1]["shots"])
        if (av["share_pct"] or 0) >= 62 and av["shots"] >= 8:
            recs.append(_rec("strategy", 2, f"{names}: the opponents are picking on one player",
                             f"{av['share_pct']}% of {opp_names}'s shots went to one partner.",
                             "The partner being avoided should look to poach and take balls in the middle; the targeted player can lob or go down the line to change the pattern."))
    forms = {k: v for k, v in d["serving_formations"].items() if v["points"] >= 4 and v["won_pct"] is not None}
    if len(forms) >= 2:
        best = max(forms.items(), key=lambda kv: kv[1]["won_pct"])
        worst = min(forms.items(), key=lambda kv: kv[1]["won_pct"])
        if best[1]["won_pct"] - worst[1]["won_pct"] >= 20:
            recs.append(_rec("strategy", 2, f"{names}: serve from the {best[0].replace('_', ' ')} formation more",
                             f"{best[0].replace('_', ' ').capitalize()} won {best[1]['won_pct']}% of {best[1]['points']} service points; {worst[0].replace('_', ' ')} won {worst[1]['won_pct']}% of {worst[1]['points']}.",
                             "Lean on the formation that is working, and keep the other as a surprise."))
    fv = d["first_volley"]
    if fv["chances"] >= 5 and fv["made_pct"] is not None and fv["made_pct"] < 70:
        recs.append(_rec("strategy", 2, f"{names}: make the first volley",
                         f"The serving team made {fv['made_pct']}% of first volleys.",
                         "Aim the first volley deep through the middle with margin. Placement before power: the point is won on the second volley."))
    return recs


def recommendations(match: Match, stats: dict, pos: dict) -> list[dict]:
    recs: list[dict] = []
    singles = match.format == "singles"
    for p in match.players:
        recs += _player_recs(p.name, pos["players"][p.id], stats["players"][p.id], singles)
    for t in (0, 1):
        names = " / ".join(p.name for p in match.team_players(t))
        opp_names = " / ".join(p.name for p in match.team_players(1 - t))
        recs += _matchup_recs(names, stats["teams"][str(t)], opp_names, stats["teams"][str(1 - t)])
        if not singles:
            recs += _doubles_recs(names, pos.get("teams", {}).get(str(t), {}), stats["doubles"][str(t)], opp_names)
    recs.sort(key=lambda r: r["priority"])
    return recs
