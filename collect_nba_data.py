"""Download NBA seasons 2003-04 through 2026-27 as compressed CSV files.

Data is sourced from llimllib/nba_data's public DuckDB catalog.
One folder per season, with raw source fields preserved. Player IDs are stable.
"""
import json
from pathlib import Path
import duckdb

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "data"
OUT.mkdir(exist_ok=True)
con = duckdb.connect()
con.execute("INSTALL httpfs; LOAD httpfs;")
con.execute("ATTACH 'https://basketball-data.billmill.org/nba/nba.duckdb' AS nba (READ_ONLY)")
tables = {
    "player_season_stats": "player_season_stats",
    "player_season_stats_per_game": "player_season_stats_per_game",
    "player_game_logs": "player_game_logs",
    "team_game_logs": "team_game_logs",
    "team_seasons": "team_seasons",
}
optional = ["player_seasons", "openrapm", "epm", "player_box"]
available = {row[0] for row in con.execute("SHOW ALL TABLES").fetchall() if row[1] == "nba"}
# SHOW ALL TABLES returns database, schema, name; use information_schema instead.
available = {r[0] for r in con.execute(
    "SELECT table_name FROM information_schema.tables WHERE table_catalog = 'nba'"
).fetchall()}
for table in optional:
    if table in available:
        tables[table] = table
missing = set(tables.values()) - available
if missing:
    raise RuntimeError(f"Required source tables unavailable: {sorted(missing)}")

manifest = {"source": "https://basketball-data.billmill.org/nba/nba.duckdb",
            "seasons": {}, "player_identity": "NBA player_id"}
for year in range(2004, 2028):
    season = f"{year-1}-{str(year)[-2:]}"
    folder = OUT / season
    folder.mkdir(exist_ok=True)
    manifest["seasons"][season] = {}
    for output_name, table in tables.items():
        cols = {row[0] for row in con.execute(f"DESCRIBE SELECT * FROM nba.{table}").fetchall()}
        if "season" not in cols:
            continue
        path = (folder / f"{output_name}.csv.gz").as_posix().replace("'", "''")
        try:
            count = con.execute(
                f"SELECT count(*) FROM nba.{table} WHERE season = ?", [year]
            ).fetchone()[0]
            if count == 0:
                continue
            con.execute(
                f"COPY (SELECT * FROM nba.{table} WHERE season = {year}) "
                f"TO '{path}' (HEADER, DELIMITER ',', COMPRESSION gzip)"
            )
            manifest["seasons"][season][output_name] = count
            print(f"{season} {output_name}: {count} rows", flush=True)
        except Exception as exc:
            if table in optional:
                print(f"Skipping optional {table} {season}: {exc}", flush=True)
            else:
                raise
players_path = (OUT / "players.csv.gz").as_posix().replace("'", "''")
con.execute(f"COPY (SELECT * FROM nba.players) TO '{players_path}' (HEADER, COMPRESSION gzip)")
(OUT / "manifest.json").write_text(json.dumps(manifest, indent=2))
print("Complete: data/manifest.json")
