"""Lesson mode: every shot stands on its own. What was hit, from where, where it landed, and whether it was in."""
from __future__ import annotations

from ..stats.engine import depth_zone, pct
from ..stats.positioning import view_from, zone_of
from ..stats.schema import Player, Shot

HIT_ZONES = {"net": "at the net", "no_mans_land": "mid-court", "baseline": "baseline", "deep_behind": "behind the baseline"}
MISSES = ("net", "long", "wide")


def shot_kind(shot: Shot) -> str:
    """One label per shot: serve, overhead, forehand volley, backhand, ..."""
    if shot.contact in ("serve", "overhead"):
        return shot.contact
    stroke = shot.stroke if shot.stroke in ("forehand", "backhand") else ""
    if shot.contact == "volley":
        return f"{stroke} volley".strip()
    return stroke or "unclassified"


def hit_zone(shot: Shot) -> str | None:
    if shot.hit_pos is None:
        return None
    return HIT_ZONES[zone_of(view_from(shot.hit_pos, shot.hit_pos))]


def _tally(shots: list[Shot]) -> dict:
    judged = [s for s in shots if s.result in ("in",) + MISSES]
    made = sum(s.result == "in" for s in judged)
    speeds = [s.speed_kmh for s in shots if s.speed_kmh]
    return dict(
        shots=len(shots), judged=len(judged), made=made, in_pct=pct(made, len(judged)),
        net=sum(s.result == "net" for s in shots), long=sum(s.result == "long" for s in shots),
        wide=sum(s.result == "wide" for s in shots), not_seen=len(shots) - len(judged),
        avg_speed_kmh=round(sum(speeds) / len(speeds), 1) if speeds else None,
    )


def _group(shots: list[Shot], key) -> dict:
    groups: dict[str, list[Shot]] = {}
    for s in shots:
        k = key(s)
        if k is not None:
            groups.setdefault(k, []).append(s)
    return {k: _tally(v) for k, v in sorted(groups.items(), key=lambda kv: -len(kv[1]))}


def lesson_breakdown(shots: list[Shot], players: list[Player]) -> dict:
    """Per player: totals, and the same tally split by shot type, by where it was hit from, and by landing depth."""
    out = {}
    for p in players:
        mine = [s for s in shots if s.player == p.id]
        miss_counts = {m: sum(s.result == m for s in mine) for m in MISSES}
        worst = max(miss_counts, key=miss_counts.get) if any(miss_counts.values()) else None
        out[p.id] = dict(
            name=p.name, total=_tally(mine),
            by_kind=_group(mine, shot_kind),
            by_hit_zone=_group(mine, hit_zone),
            by_depth=_group(mine, depth_zone),
            most_common_miss=worst,
            shots=[dict(t=round(s.t, 2), kind=shot_kind(s), hit_zone=hit_zone(s), result=s.result, depth=depth_zone(s),
                        speed_kmh=s.speed_kmh, hit_pos=s.hit_pos, bounce_pos=s.bounce_pos) for s in mine],
        )
    return out
