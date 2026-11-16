"""Tennis scoring: replay the point winners and report the score and pressure situation before every point."""
from __future__ import annotations

from dataclasses import dataclass, field

from .schema import Match, Rules

POINT_NAMES = ["0", "15", "30", "40"]


@dataclass
class Situation:
    set_no: int
    game_no: int                 # game number within the set, starting at 1
    serving_team: int
    points: tuple[int, int]      # points in the current game, by team
    games: tuple[int, int]
    sets: tuple[int, int]
    tiebreak: bool
    score_text: str
    break_point: bool = False
    game_point: bool = False
    deuce: bool = False
    set_point_team: int | None = None
    match_point_team: int | None = None
    game_won_by: int | None = None      # filled after the point if it ended the game
    set_won_by: int | None = None
    match_won_by: int | None = None


@dataclass
class ScoreState:
    rules: Rules
    sets: list[int] = field(default_factory=lambda: [0, 0])
    games: list[int] = field(default_factory=lambda: [0, 0])
    points: list[int] = field(default_factory=lambda: [0, 0])
    set_scores: list[tuple[int, int]] = field(default_factory=list)
    winner: int | None = None

    @property
    def sets_to_win(self) -> int:
        return self.rules.best_of // 2 + 1

    def _deciding_set(self) -> bool:
        return self.sets[0] == self.sets[1] == self.sets_to_win - 1

    def tiebreak_target(self) -> int | None:
        r = self.rules
        if r.final_set_tiebreak_points and self._deciding_set() and self.games == [0, 0]:
            return r.final_set_tiebreak_points
        if self.games[0] == self.games[1] == r.games_per_set:
            return r.tiebreak_points
        return None

    def _wins_game_with_next_point(self, team: int) -> bool:
        mine, theirs = self.points[team], self.points[1 - team]
        target = self.tiebreak_target()
        if target:
            return mine + 1 >= target and mine + 1 - theirs >= 2
        if self.rules.no_ad:
            return mine >= 3
        return mine >= 3 and mine - theirs >= 1

    def _wins_set_with_game(self, team: int) -> bool:
        if self.tiebreak_target():
            return True
        g = self.rules.games_per_set
        mine, theirs = self.games[team] + 1, self.games[1 - team]
        return mine >= g and mine - theirs >= 2

    def describe(self, serving_team: int, set_no: int, game_no: int) -> Situation:
        target = self.tiebreak_target()
        a, b = self.points[serving_team], self.points[1 - serving_team]
        if target:
            text = f"{a}-{b}"
        elif a >= 3 and b >= 3:
            text = "Deuce" if a == b else ("Ad-In" if a > b else "Ad-Out")
        else:
            text = f"{POINT_NAMES[min(a, 3)]}-{POINT_NAMES[min(b, 3)]}"
        sit = Situation(set_no=set_no, game_no=game_no, serving_team=serving_team, points=tuple(self.points),
                        games=tuple(self.games), sets=tuple(self.sets), tiebreak=bool(target), score_text=text)
        sit.deuce = not target and a >= 3 and a == b
        if not target:
            sit.game_point = self._wins_game_with_next_point(serving_team)
            sit.break_point = self._wins_game_with_next_point(1 - serving_team)
        for team in (0, 1):
            if self._wins_game_with_next_point(team) and self._wins_set_with_game(team):
                sit.set_point_team = team
                if self.sets[team] + 1 >= self.sets_to_win:
                    sit.match_point_team = team
        return sit

    def award(self, team: int, sit: Situation) -> None:
        if self._wins_game_with_next_point(team):
            sit.game_won_by = team
            set_won = self._wins_set_with_game(team)
            self.games[team] += 1
            self.points = [0, 0]
            if set_won:
                sit.set_won_by = team
                self.set_scores.append(tuple(self.games))
                self.sets[team] += 1
                self.games = [0, 0]
                if self.sets[team] >= self.sets_to_win:
                    self.winner = team
                    sit.match_won_by = team
        else:
            self.points[team] += 1


def replay(match: Match) -> tuple[list[Situation], ScoreState]:
    """Situation before each point (with what the point decided), and the final score state."""
    state = ScoreState(match.rules)
    out: list[Situation] = []
    set_no, game_no = 1, 1
    for point in match.points:
        serving_team = match.team_of(point.server)
        sit = state.describe(serving_team, set_no, game_no)
        state.award(point.winner_team, sit)
        out.append(sit)
        if sit.set_won_by is not None:
            set_no, game_no = set_no + 1, 1
        elif sit.game_won_by is not None:
            game_no += 1
    return out, state


def score_line(state: ScoreState) -> str:
    done = " ".join(f"{a}-{b}" for a, b in state.set_scores)
    live = f"{state.games[0]}-{state.games[1]}" if state.winner is None and (state.games != [0, 0] or not state.set_scores) else ""
    return (done + " " + live).strip()
