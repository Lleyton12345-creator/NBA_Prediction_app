"""Build player biographies from the NBA season files already imported in this repository.
No external NBA Stats requests, so no per-season network timeouts.
"""
import json
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parent
DATA=ROOT/"data"
SEASONS=[f"{y}-{str(y+1)[-2:]}" for y in range(2003,2027)]
ALIASES={
 "position":["position","pos","player_position"],
 "height":["height","player_height","height_display"],
 "weight":["weight","player_weight","weight_lbs"],
 "draft_year":["draft_year","year_drafted"],
 "draft_round":["draft_round"],
 "draft_pick":["draft_number","draft_pick","draft_overall","draft_pick_number"],
 "nba_id":["nba_id","nba_player_id","player_id","person_id"],
}
def clean(v):
 if pd.isna(v):return None
 s=str(v).strip()
 return s if s and s.lower() not in ("nan","none","null","-") else None
def main():
 master=pd.read_csv(DATA/"players.csv.gz",dtype=str,low_memory=False)
 if "player_id" not in master.columns:raise ValueError("Missing player_id in master players file")
 profiles={str(i):{} for i in master.player_id.dropna()}
 source_rows=0
 for table,df in [("players",master)]+[(f"{season}/{table}",pd.read_csv(DATA/season/(table+".csv.gz"),dtype=str,low_memory=False)) for season in SEASONS for table in ("player_seasons","player_season_stats") if (DATA/season/(table+".csv.gz")).exists()]:
  if "player_id" not in df.columns:continue
  for row in df.to_dict("records"):
   pid=clean(row.get("player_id"))
   if pid not in profiles:continue
   source_rows+=1
   for field,keys in ALIASES.items():
    if field in profiles[pid]:continue
    for key in keys:
     value=clean(row.get(key))
     if value is not None:
      profiles[pid][field]=value
      break
  print("Read",table,len(df),flush=True)
 enriched={pid:v for pid,v in profiles.items() if len(v)>1}
 output={"source":"Existing imported NBA player and season records","players":enriched}
 (DATA/"player_bios.json").write_text(json.dumps(output,separators=(",",":")))
 report={"total_players":len(profiles),"players_with_bio":len(enriched),
 "coverage":{f:sum(f in v for v in profiles.values()) for f in ALIASES},
 "missing_player_ids":[pid for pid,v in profiles.items() if len(v)<=1],
 "limitations":["Does not independently verify biographical accuracy","Headshots are not verified by this script","Active status requires a current roster source","Unknown values are not fabricated"]}
 (DATA/"bio_coverage_report.json").write_text(json.dumps(report,indent=2))
 print(json.dumps({k:v for k,v in report.items() if k!="missing_player_ids"},indent=2))
if __name__=="__main__":main()
