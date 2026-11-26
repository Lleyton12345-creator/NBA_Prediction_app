"""Audit imported NBA files without modifying or deleting any player records."""
from pathlib import Path
import gzip, json
import pandas as pd

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
manifest = json.loads((DATA / "manifest.json").read_text())
issues = []
seasons = {}
identity = {}
for season, expected in manifest["seasons"].items():
    folder = DATA / season
    entry = {}
    for table, count in expected.items():
        path = folder / f"{table}.csv.gz"
        if not path.exists():
            issues.append({"season": season, "table": table, "issue": "missing_file"})
            continue
        try:
            df = pd.read_csv(path, compression="gzip", low_memory=False)
        except Exception as exc:
            issues.append({"season": season, "table": table, "issue": "unreadable", "detail": str(exc)})
            continue
        entry[table] = {"rows": len(df), "columns": list(df.columns),
                        "missing_cells": int(df.isna().sum().sum()),
                        "exact_duplicate_rows": int(df.duplicated().sum())}
        if len(df) != count:
            issues.append({"season": season, "table": table, "issue": "manifest_count_mismatch", "expected": count, "actual": len(df)})
        if df.duplicated().any():
            issues.append({"season": season, "table": table, "issue": "exact_duplicate_rows", "count": int(df.duplicated().sum())})
        if "season" in df.columns:
            expected_year = int(season[:4]) + 1
            bad = int((pd.to_numeric(df.season, errors="coerce") != expected_year).sum())
            if bad:
                issues.append({"season": season, "table": table, "issue": "wrong_season", "count": bad})
        if "player_id" in df.columns:
            null_ids = int(df.player_id.isna().sum())
            if null_ids:
                issues.append({"season": season, "table": table, "issue": "missing_player_id", "count": null_ids})
            if table in ("player_season_stats", "player_season_stats_per_game", "player_seasons"):
                entry[table]["unique_player_ids"] = int(df.player_id.nunique())
                entry[table]["multiple_rows_per_player"] = int(df.duplicated("player_id").sum())
                if df.duplicated("player_id").any():
                    entry[table]["duplicate_player_ids_sample"] = df.loc[df.duplicated("player_id", keep=False), "player_id"].astype(str).unique()[:15].tolist()
        if table == "player_game_logs" and {"player_id", "game_id"}.issubset(df.columns):
            dup = int(df.duplicated(["player_id", "game_id"]).sum())
            entry[table]["duplicate_player_game_keys"] = dup
            if dup:
                issues.append({"season": season, "table": table, "issue": "duplicate_player_game_keys", "count": dup})
    seasons[season] = entry

players_path = DATA / "players.csv.gz"
player_report = {}
if players_path.exists():
    players = pd.read_csv(players_path, compression="gzip", low_memory=False)
    player_report = {"rows": len(players), "columns": list(players.columns)}
    if "player_id" in players.columns:
        player_report["unique_player_ids"] = int(players.player_id.nunique())
        player_report["duplicate_player_ids"] = int(players.duplicated("player_id").sum())
        player_report["missing_player_ids"] = int(players.player_id.isna().sum())
        if player_report["duplicate_player_ids"]:
            issues.append({"table": "players", "issue": "duplicate_master_player_ids", "count": player_report["duplicate_player_ids"]})
    else:
        issues.append({"table": "players", "issue": "missing_player_id_column"})
else:
    issues.append({"table": "players", "issue": "missing_master_player_file"})
report = {"scope": "2003-04 through 2026-27", "limitations": [
    "Internal consistency checks only; does not independently verify box scores against NBA official records.",
    "Multiple player-season rows can be legitimate team splits or stat categories; do not delete without investigating.",
    "2026-27 is incomplete.",
    "Missing advanced metrics are not proof of missing players."
], "master_players": player_report, "seasons": seasons, "issues": issues}
(DATA / "audit_report.json").write_text(json.dumps(report, indent=2))
summary = {"seasons_checked": len(seasons), "master_players": player_report,
           "issues_found": len(issues), "issues_by_type": {}}
for issue in issues:
    key = issue["issue"]
    summary["issues_by_type"][key] = summary["issues_by_type"].get(key, 0) + 1
(DATA / "audit_summary.json").write_text(json.dumps(summary, indent=2))
print(json.dumps(summary, indent=2))
