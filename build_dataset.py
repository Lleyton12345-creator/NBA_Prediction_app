"""Build NBA player-season, game, and team datasets from the public nba_data catalog."""
from pathlib import Path
import json
import sqlite3
import duckdb
import pandas as pd

OUT = Path(__file__).resolve().parent / "output"
OUT.mkdir(exist_ok=True)
SOURCE = "https://basketball-data.billmill.org/nba/nba.duckdb"
con = duckdb.connect()
con.execute(f"ATTACH '{SOURCE}' AS nba (READ_ONLY)")

seasons = con.execute("""
    SELECT * FROM nba.player_season_stats
    WHERE season BETWEEN 2011 AND 2027 AND season_type = 'regular_season'
""").df()
if seasons.empty:
    raise RuntimeError("No season records returned")
required = {"player_id", "season", "gp"}
if not required.issubset(seasons.columns):
    raise ValueError(f"Missing required columns: {required - set(seasons.columns)}")
seasons["player_id"] = seasons.player_id.astype(str)
qualifiers = set(seasons.loc[
    ((seasons.season <= 2026) & (seasons.gp >= 30)) |
    ((seasons.season == 2027) & (seasons.gp >= 1)), "player_id"
])
seasons = seasons[seasons.player_id.isin(qualifiers)].copy()
if seasons.duplicated(["player_id", "season"]).any():
    raise ValueError("Duplicate player-season rows: review team splits before aggregating")

players = con.execute("SELECT * FROM nba.players").df()
players["player_id"] = players.player_id.astype(str)
players = players[players.player_id.isin(qualifiers)].drop_duplicates("player_id")
assert players.player_id.is_unique

team_games = con.execute("""
    SELECT * FROM nba.team_game_logs
    WHERE season BETWEEN 2011 AND 2027 AND season_type = 'regular_season'
""").df()
if not {"team_id", "season", "win", "game_id"}.issubset(team_games.columns):
    raise ValueError("Unexpected team game schema: " + str(team_games.columns.tolist()))
team_games = team_games.drop_duplicates(["season", "team_id", "game_id"])
team_games["win"] = team_games.win.astype("boolean")
team_records = team_games.groupby(["season", "team_id"], as_index=False).agg(
    games=("win", "count"), wins=("win", "sum")
)
team_records["losses"] = team_records.games - team_records.wins
team_records["win_pct"] = team_records.wins / team_records.games

games = con.execute("""
    SELECT * FROM nba.player_game_logs
    WHERE season BETWEEN 2011 AND 2027 AND season_type = 'regular_season'
""").df()
games["player_id"] = games.player_id.astype(str)
games = games[games.player_id.isin(qualifiers)].copy()
if games.duplicated(["season", "game_id", "player_id"]).any():
    raise ValueError("Duplicate player-game records")

tables = {
    "players": players,
    "player_seasons": seasons,
    "player_games": games,
    "team_records": team_records,
}
for name, df in tables.items():
    df.to_csv(OUT / f"{name}.csv", index=False)
    df.to_parquet(OUT / f"{name}.parquet", index=False)
with sqlite3.connect(OUT / "nba_prediction.sqlite") as db:
    for name, df in tables.items():
        df.to_sql(name, db, if_exists="replace", index=False, chunksize=1000)
    db.execute("CREATE UNIQUE INDEX idx_players ON players(player_id)")
    db.execute("CREATE UNIQUE INDEX idx_seasons ON player_seasons(player_id, season)")
    db.execute("CREATE INDEX idx_games_player ON player_games(player_id, season)")
    db.execute("CREATE INDEX idx_teams ON team_records(team_id, season)")
report = {
    "source": SOURCE,
    "season_range": "2010-11 to 2026-27",
    "current_season_incomplete": True,
    "counts": {name: len(df) for name, df in tables.items()},
    "missing_by_column": {
        name: {key: int(value) for key, value in df.isna().sum().items() if value > 0}
        for name, df in tables.items()
    },
    "qualification": "30+ games in any completed season OR 1+ game in 2026-27; retain all seasons",
    "caveats": [
        "Current season incomplete",
        "Advanced metrics only where provided by source",
        "On/off, RAPM, BPM and Win Shares require separate verified sources",
        "Review source licensing before distribution",
    ],
}
(OUT / "audit.json").write_text(json.dumps(report, indent=2))
print(json.dumps({k: v for k, v in report.items() if k != "missing_by_column"}, indent=2))
