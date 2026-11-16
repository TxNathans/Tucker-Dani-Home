"""The match record: players, points and shots. Everything the tracker detects (or a person tags by hand) lands here.

Court coordinates are metres with the origin at the centre of the net.
x runs across the court (doubles sidelines at +/-5.485, singles at +/-4.115), y runs along it (baselines at +/-11.885).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional

HALF_LENGTH = 11.885
SINGLES_HALF_WIDTH = 4.115
DOUBLES_HALF_WIDTH = 5.485
SERVICE_LINE = 6.40

STROKES = ("serve", "forehand", "backhand")
CONTACTS = ("serve", "groundstroke", "volley", "half_volley", "overhead", "lob", "drop_shot")
RESULTS = ("in", "net", "long", "wide", "unknown")
END_TYPES = ("ace", "double_fault", "winner", "forced_error", "unforced_error", "unknown")


@dataclass
class Player:
    id: str
    name: str
    team: int                 # 0 or 1
    hand: str = "right"


@dataclass
class Shot:
    player: str
    t: float = 0.0
    stroke: str = "forehand"          # serve | forehand | backhand
    contact: str = "groundstroke"     # groundstroke | volley | half_volley | overhead | serve ...
    serve_number: Optional[int] = None
    hit_pos: Optional[tuple[float, float]] = None       # hitter's feet on court
    bounce_pos: Optional[tuple[float, float]] = None    # where the ball landed
    result: str = "in"                # in | net | long | wide | unknown
    speed_kmh: Optional[float] = None
    is_return: bool = False
    poach: bool = False               # doubles: net player crossed to intercept
    player_positions: dict[str, tuple[float, float]] = field(default_factory=dict)  # everyone's feet at the hit


@dataclass
class Point:
    server: str
    winner_team: int
    end_type: str = "unknown"
    end_player: Optional[str] = None
    shots: list[Shot] = field(default_factory=list)
    t_start: float = 0.0
    t_end: float = 0.0
    receiver: Optional[str] = None
    formation: Optional[str] = None          # doubles serving formation: standard | i_formation | australian
    distance_m: dict[str, float] = field(default_factory=dict)   # metres run by each player in the point
    source: str = "auto"                     # auto | manual | corrected


@dataclass
class Rules:
    best_of: int = 3
    games_per_set: int = 6
    no_ad: bool = False
    tiebreak_points: int = 7
    final_set_tiebreak_points: Optional[int] = None   # e.g. 10 for a match tiebreak instead of a final set


@dataclass
class Match:
    format: str                               # singles | doubles
    players: list[Player]
    points: list[Point] = field(default_factory=list)
    rules: Rules = field(default_factory=Rules)
    title: str = ""
    duration_s: Optional[float] = None

    def player(self, pid: str) -> Player:
        return next(p for p in self.players if p.id == pid)

    def team_of(self, pid: str) -> int:
        return self.player(pid).team

    def team_players(self, team: int) -> list[Player]:
        return [p for p in self.players if p.team == team]

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Match":
        tup = lambda v: tuple(v) if v is not None else None
        points = []
        for p in d.get("points", []):
            shots = []
            for s in p.get("shots", []):
                s = dict(s)
                s["hit_pos"], s["bounce_pos"] = tup(s.get("hit_pos")), tup(s.get("bounce_pos"))
                s["player_positions"] = {k: tuple(v) for k, v in s.get("player_positions", {}).items()}
                shots.append(Shot(**s))
            points.append(Point(**{**p, "shots": shots}))
        return cls(format=d["format"], players=[Player(**p) for p in d["players"]], points=points,
                   rules=Rules(**d.get("rules", {})), title=d.get("title", ""), duration_s=d.get("duration_s"))
