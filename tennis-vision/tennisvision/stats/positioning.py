"""Court positioning: where players stand at the moment the opponent hits, measured against sound positions.

Every shot in the match record carries a snapshot of all players' feet. The moment an opponent makes contact is
when positioning matters, so those snapshots are what gets scored here.
"""
from __future__ import annotations

from collections import defaultdict

import numpy as np

from .engine import NET_ZONE_M, pct, serves_of
from .schema import DOUBLES_HALF_WIDTH, HALF_LENGTH, SERVICE_LINE, SINGLES_HALF_WIDTH, Match, Shot

DEEP_BEHIND_M = 2.5          # further behind the baseline than this gives away angle and time
INSIDE_BASELINE_M = 1.5      # further inside than this (but not at net) is no-man's land
IDEAL_PARTNER_GAP = (3.0, 5.0)
SERVICE_BOX_MIDDLE_X = SINGLES_HALF_WIDTH / 2


def view_from(pos, me):
    """Rotate so the player 'me' is at negative y looking toward positive y."""
    if pos is None or me is None:
        return None
    return (-pos[0], -pos[1]) if me[1] > 0 else (pos[0], pos[1])


def ideal_recovery_x(opponent, half_width: float = SINGLES_HALF_WIDTH) -> float:
    """Where on the baseline to stand so the opponent's widest shots either way are equally far.

    The opponent's range runs from down the line to the sharp crosscourt angle (ball crossing the sideline at
    service-line depth), which is why the answer sits crosscourt of the centre mark.
    """
    ox, oy = opponent
    crossings = []
    for tx in (-half_width, half_width):
        for ty in (-SERVICE_LINE, -HALF_LENGTH):
            if oy - ty <= 0:
                continue
            crossings.append(ox + (tx - ox) * (oy + HALF_LENGTH) / (oy - ty))
    left, right = min(crossings), max(crossings)
    d_left = np.hypot(ox - left, oy + HALF_LENGTH)
    d_right = np.hypot(ox - right, oy + HALF_LENGTH)
    return float((d_right * left + d_left * right) / (d_left + d_right))


def zone_of(pos_view) -> str:
    """Zone for a player seen from their own end (negative y)."""
    from_net = -pos_view[1]
    if from_net < NET_ZONE_M:
        return "net"
    if from_net < HALF_LENGTH - INSIDE_BASELINE_M:
        return "no_mans_land"
    if from_net <= HALF_LENGTH + DEEP_BEHIND_M:
        return "baseline"
    return "deep_behind"


def _mean(values, digits=2):
    return round(float(np.mean(values)), digits) if len(values) else None


def player_positioning(match: Match, pid: str) -> dict:
    team = match.team_of(pid)
    half_width = DOUBLES_HALF_WIDTH if match.format == "doubles" else SINGLES_HALF_WIDTH
    zones = defaultdict(lambda: dict(n=0, points=set(), won=set()))
    recovery_err, recovery_signed, depth_at_contact = [], [], []
    return_depth = {1: [], 2: []}
    contact_depth, net_distance = [], []
    for k, point in enumerate(match.points):
        won = point.winner_team == team
        for shot in point.shots:
            me = shot.player_positions.get(pid)
            if shot.player == pid and shot.hit_pos is not None and shot.stroke != "serve":
                mine = view_from(shot.hit_pos, shot.hit_pos)
                contact_depth.append(mine[1] + HALF_LENGTH)        # positive = inside the baseline
            if me is None or match.team_of(shot.player) == team:
                continue
            mine = view_from(me, me)
            opp = view_from(shot.hit_pos, me)
            if shot.stroke == "serve":
                if shot.serve_number in (1, 2) and (point.receiver == pid or (point.receiver is None and match.format == "singles")):
                    return_depth[shot.serve_number].append(mine[1] + HALF_LENGTH)
                continue
            zone = zone_of(mine)
            z = zones[zone]
            z["n"] += 1
            z["points"].add(k)
            if won:
                z["won"].add(k)
            if zone == "net":
                net_distance.append(-mine[1])
            if match.format == "singles" and zone in ("baseline", "deep_behind") and opp is not None and opp[1] > 0:
                ideal = ideal_recovery_x(opp, half_width)
                recovery_err.append(abs(mine[0] - ideal))
                side = np.sign(opp[0]) if abs(opp[0]) > 0.5 else 0.0
                recovery_signed.append((mine[0] - ideal) * side)   # positive = leaning toward the opponent's side (down the line)
                depth_at_contact.append(mine[1] + HALF_LENGTH)
    total = sum(z["n"] for z in zones.values())
    return dict(
        snapshots=total,
        zones={name: dict(share_pct=pct(z["n"], total), points=len(z["points"]), points_won_pct=pct(len(z["won"]), len(z["points"])))
               for name, z in zones.items()},
        recovery=dict(
            samples=len(recovery_err), avg_error_m=_mean(recovery_err),
            lean_m=_mean(recovery_signed),
            avg_depth_m=_mean(depth_at_contact),
        ),
        return_position=dict(first_serve_m=_mean(return_depth[1]), second_serve_m=_mean(return_depth[2]),
                             samples=len(return_depth[1]) + len(return_depth[2])),
        contact_depth_m=_mean(contact_depth), contact_samples=len(contact_depth),
        net_distance_m=_mean(net_distance),
    )


def team_positioning(match: Match, team: int) -> dict:
    """Doubles: how the two partners arrange themselves when an opponent is hitting."""
    ids = [p.id for p in match.team_players(team)]
    if len(ids) != 2:
        return {}
    a, b = ids
    gaps_level, wide_open, stacked = [], 0, 0
    shapes = defaultdict(lambda: dict(n=0, points=set(), won=set()))
    shift = []
    server_partner_x, server_partner_net = [], []
    receiver_partner_depth = []
    for k, point in enumerate(match.points):
        won = point.winner_team == team
        serves = serves_of(point)
        if serves and serves[0].player_positions:
            snap = serves[0].player_positions
            if point.server in ids:
                partner = b if point.server == a else a
                if partner in snap:
                    pp = view_from(snap[partner], snap[partner])
                    if -pp[1] < SERVICE_LINE + 1.0:
                        server_partner_x.append(abs(pp[0]))
                        server_partner_net.append(-pp[1])
            elif point.receiver in ids:
                partner = b if point.receiver == a else a
                if partner in snap:
                    receiver_partner_depth.append(-view_from(snap[partner], snap[partner])[1])
        for shot in point.shots:
            if match.team_of(shot.player) == team or shot.stroke == "serve":
                continue
            pa, pb = shot.player_positions.get(a), shot.player_positions.get(b)
            if pa is None or pb is None:
                continue
            va, vb = view_from(pa, pa), view_from(pb, pa)
            up = int(-va[1] < NET_ZONE_M) + int(-vb[1] < NET_ZONE_M)
            shape = {2: "both_at_net", 1: "one_up_one_back", 0: "both_back"}[up]
            s = shapes[shape]
            s["n"] += 1
            s["points"].add(k)
            if won:
                s["won"].add(k)
            if up != 1:
                gap = abs(va[0] - vb[0])
                gaps_level.append(gap)
                wide_open += gap > IDEAL_PARTNER_GAP[1] + 0.5
                stacked += gap < IDEAL_PARTNER_GAP[0] - 0.5
            opp = view_from(shot.hit_pos, pa)
            if opp is not None and abs(opp[0]) > 2.0:
                shift.append((va[0] + vb[0]) / 2 * np.sign(opp[0]))
    total = sum(s["n"] for s in shapes.values())
    return dict(
        snapshots=total,
        shapes={name: dict(share_pct=pct(s["n"], total), points=len(s["points"]), points_won_pct=pct(len(s["won"]), len(s["points"])))
                for name, s in shapes.items()},
        partner_gap=dict(avg_m=_mean(gaps_level), samples=len(gaps_level),
                         middle_open_pct=pct(wide_open, len(gaps_level)), stacked_pct=pct(stacked, len(gaps_level))),
        shift_with_ball_m=_mean(shift), shift_samples=len(shift),
        server_partner=dict(from_centre_m=_mean(server_partner_x), from_net_m=_mean(server_partner_net), samples=len(server_partner_x)),
        receiver_partner=dict(from_net_m=_mean(receiver_partner_depth), samples=len(receiver_partner_depth)),
    )


def positioning(match: Match) -> dict:
    out = dict(players={p.id: player_positioning(match, p.id) for p in match.players})
    if match.format == "doubles":
        out["teams"] = {str(t): team_positioning(match, t) for t in (0, 1)}
    return out
