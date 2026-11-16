"""Turn detected hits and bounces into rallies, shots and points."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..stats.schema import (DOUBLES_HALF_WIDTH, HALF_LENGTH, SERVICE_LINE, SINGLES_HALF_WIDTH, Match, Player, Point, Shot)

LINE_TOLERANCE_M = 0.12      # a ball touching the line is in; this also absorbs calibration error
RALLY_GAP_S = 3.5
FORCED_RUN_M = 3.0
FORCED_SPEED_KMH = 95.0


@dataclass
class Hit:
    t: float
    player: str                                   # player id
    pos: tuple[float, float] | None = None        # hitter's feet on court (metres)
    positions: dict[str, tuple[float, float]] = field(default_factory=dict)
    above_head: bool = False                      # ball above the hitter's head at contact
    stroke: str = "unknown"                       # forehand | backhand | serve/overhead | unknown
    unsure_player: bool = False
    frame: int = 0


@dataclass
class Bounce:
    t: float
    pos: tuple[float, float] | None = None        # court metres


@dataclass
class Rally:
    hits: list[Hit]
    bounces: list[Bounce]

    @property
    def t_start(self) -> float:
        return self.hits[0].t

    @property
    def t_end(self) -> float:
        last = max([self.hits[-1].t] + [b.t for b in self.bounces])
        return last


def split_rallies(hits: list[Hit], bounces: list[Bounce], gap_s: float = RALLY_GAP_S) -> list[Rally]:
    rallies: list[Rally] = []
    hits = sorted(hits, key=lambda h: h.t)
    group: list[Hit] = []
    for h in hits:
        if group and h.t - group[-1].t > gap_s:
            rallies.append(Rally(group, []))
            group = []
        group.append(h)
    if group:
        rallies.append(Rally(group, []))
    for i, r in enumerate(rallies):
        end = rallies[i + 1].t_start - 0.3 if i + 1 < len(rallies) else float("inf")
        r.bounces = [b for b in bounces if r.t_start < b.t < min(end, r.hits[-1].t + gap_s)]
    return rallies


def landing_result(pos, hitter_y: float, fmt: str, serve_from_x: float | None = None) -> str:
    """in / net / long / wide for a bounce, judged from the hitter's end. serve_from_x set means it is a serve."""
    if pos is None:
        return "unknown"
    x, y = pos
    if hitter_y > 0:                      # look at it from the hitter's end
        x, y = -x, -y
        if serve_from_x is not None:
            serve_from_x = -serve_from_x
    tol = LINE_TOLERANCE_M
    if y < 0:
        return "net"                      # came down on the hitter's own side
    if serve_from_x is not None:
        if y > SERVICE_LINE + tol:
            return "long"
        lo, hi = (-SINGLES_HALF_WIDTH, 0.0) if serve_from_x > 0 else (0.0, SINGLES_HALF_WIDTH)
        return "in" if lo - tol <= x <= hi + tol else "wide"
    half_width = DOUBLES_HALF_WIDTH if fmt == "doubles" else SINGLES_HALF_WIDTH
    if y > HALF_LENGTH + tol:
        return "long"
    return "in" if abs(x) <= half_width + tol else "wide"


def _contact(index: int, hit: Hit, bounced_before: bool) -> tuple[str, str]:
    """(stroke, contact) for a rally shot."""
    behind_baseline = hit.pos is not None and abs(hit.pos[1]) > HALF_LENGTH - 0.6
    if index == 0 and hit.above_head and (behind_baseline or hit.pos is None):
        return "serve", "serve"
    stroke = hit.stroke if hit.stroke in ("forehand", "backhand") else "unknown"
    if hit.above_head and index > 0:
        return (stroke if stroke != "unknown" else "forehand"), "overhead"
    if index > 0 and not bounced_before:
        return stroke, "volley"
    return stroke, "groundstroke"


def build_shots(rally: Rally, fmt: str) -> list[Shot]:
    shots: list[Shot] = []
    hits = rally.hits
    for i, h in enumerate(hits):
        t_next = hits[i + 1].t if i + 1 < len(hits) else float("inf")
        t_prev = hits[i - 1].t if i else -float("inf")
        after = [b for b in rally.bounces if h.t < b.t < t_next]
        bounced_before = any(t_prev < b.t < h.t for b in rally.bounces)
        stroke, contact = _contact(i, h, bounced_before)
        landing = after[0] if after else None
        shot = Shot(player=h.player, t=h.t, stroke=stroke, contact=contact, hit_pos=h.pos,
                    bounce_pos=landing.pos if landing else None, player_positions=dict(h.positions))
        if stroke == "serve":
            shot.serve_number = 1
        if i + 1 < len(hits):
            shot.result = "in"                         # the rally went on, so it was played as good
        elif landing and h.pos is not None:
            shot.result = landing_result(landing.pos, h.pos[1], fmt, h.pos[0] if stroke == "serve" else None)
        else:
            shot.result = "unknown"
        if landing and landing.pos is not None and h.pos is not None and landing.t - h.t > 0.15:
            dist = float(np.hypot(landing.pos[0] - h.pos[0], landing.pos[1] - h.pos[1]))
            shot.speed_kmh = round(dist / (landing.t - h.t) * 3.6, 1)
        shot.is_return = i == 1 and shots[0].stroke == "serve"
        shots.append(shot)
    return shots


def _forced(shots: list[Shot]) -> bool:
    """Was the last shot hit under pressure? Fast incoming ball, or a long run to reach it."""
    if len(shots) < 2:
        return False
    last, incoming = shots[-1], shots[-2]
    if last.contact in ("volley", "overhead") and incoming.speed_kmh and incoming.speed_kmh >= FORCED_SPEED_KMH * 0.8:
        return True
    if incoming.speed_kmh and incoming.speed_kmh >= FORCED_SPEED_KMH:
        return True
    earlier = next((s for s in reversed(shots[:-1]) if s.player_positions.get(last.player)), None)
    if earlier and last.hit_pos is not None:
        was = earlier.player_positions[last.player]
        return float(np.hypot(last.hit_pos[0] - was[0], last.hit_pos[1] - was[1])) >= FORCED_RUN_M
    return False


def judge(shots: list[Shot], team_of: dict[str, int]) -> tuple[int | None, str, str | None]:
    """(winner_team, end_type, end_player) from the last shot. winner_team None means it could not be told."""
    if not shots:
        return None, "unknown", None
    last = shots[-1]
    team = team_of[last.player]
    if last.result == "in":
        if last.stroke == "serve":
            return team, "ace", last.player
        return team, "winner", last.player
    if last.result in ("net", "long", "wide"):
        if last.stroke == "serve":
            return None, "fault", last.player
        return 1 - team, "forced_error" if _forced(shots) else "unforced_error", last.player
    return None, "unknown", last.player


def build_points(rallies: list[Rally], players: list[Player], fmt: str) -> tuple[list[Point], list[dict]]:
    """Scored points (they start with a serve and have a clear ending) and the rallies that need a person to finish."""
    team_of = {p.id: p.team for p in players}
    points: list[Point] = []
    review: list[dict] = []
    pending_fault: Shot | None = None
    for rally in rallies:
        shots = build_shots(rally, fmt)
        winner, end_type, end_player = judge(shots, team_of)
        starts_with_serve = bool(shots) and shots[0].stroke == "serve"
        if starts_with_serve and end_type == "fault" and len(shots) == 1:
            if pending_fault is not None and pending_fault.player == shots[0].player:
                shots[0].serve_number = 2
                server = shots[0].player
                points.append(Point(server=server, winner_team=1 - team_of[server], end_type="double_fault", end_player=server,
                                    shots=[pending_fault, shots[0]], t_start=pending_fault.t, t_end=rally.t_end))
                pending_fault = None
            else:
                pending_fault = shots[0]
            continue
        if starts_with_serve and pending_fault is not None and pending_fault.player == shots[0].player \
                and shots[0].t - pending_fault.t < 30:
            shots[0].serve_number = 2
            shots = [pending_fault] + shots
        pending_fault = None
        entry = dict(t_start=round(shots[0].t, 2) if shots else 0.0, t_end=round(rally.t_end, 2), shots=shots,
                     end_type=end_type, end_player=end_player, winner_team=winner)
        if starts_with_serve and winner is not None:
            live = [s for s in shots if not (s.stroke == "serve" and s.result != "in")]
            receiver = live[1].player if len(live) > 1 else None
            points.append(Point(server=shots[0].player, winner_team=winner, end_type=end_type, end_player=end_player,
                                shots=shots, t_start=shots[0].t, t_end=rally.t_end, receiver=receiver))
        else:
            entry["reason"] = "no serve seen at the start" if not starts_with_serve else "could not tell how the point ended"
            review.append(entry)
    return points, review


def shot_summary(all_shots: list[Shot], players: list[Player]) -> dict:
    """Shot counts and placement per player from every rally, scored or not."""
    out = {}
    for p in players:
        mine = [s for s in all_shots if s.player == p.id]
        by_stroke: dict[str, int] = {}
        by_contact: dict[str, int] = {}
        for s in mine:
            by_stroke[s.stroke] = by_stroke.get(s.stroke, 0) + 1
            by_contact[s.contact] = by_contact.get(s.contact, 0) + 1
        speeds = [s.speed_kmh for s in mine if s.speed_kmh]
        out[p.id] = dict(
            name=p.name, shots=len(mine), by_stroke=by_stroke, by_contact=by_contact,
            avg_speed_kmh=round(float(np.mean(speeds)), 1) if speeds else None,
            max_speed_kmh=max(speeds) if speeds else None,
            landings=[dict(x=round(s.bounce_pos[0], 2), y=round(s.bounce_pos[1], 2), result=s.result, stroke=s.stroke)
                      for s in mine if s.bounce_pos is not None],
            hit_positions=[dict(x=round(s.hit_pos[0], 2), y=round(s.hit_pos[1], 2), stroke=s.stroke, contact=s.contact)
                           for s in mine if s.hit_pos is not None],
        )
    return out
