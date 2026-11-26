"""Enrich existing NBA biographies with an independently published player directory.
Matches strictly on numeric NBA personId, never on player name.
"""
import json, urllib.request
from pathlib import Path
import pandas as pd

DATA=Path(__file__).resolve().parent/"data"
URL="https://raw.githubusercontent.com/nickth3man/basketball-data-index/main/csv/nba/Players.csv"
def norm(x):
 if pd.isna(x):return None
 v=str(x).strip()
 return None if v.lower() in ("","nan","null","none","-") else v
def main():
 previous=json.loads((DATA/"player_bios.json").read_text())
 profiles=previous.get("players",{})
 master=pd.read_csv(DATA/"players.csv.gz",dtype=str,low_memory=False)
 ids=set(master.player_id.dropna().astype(str))
 req=urllib.request.Request(URL,headers={"User-Agent":"NBA-Research-Dataset/1.0"})
 with urllib.request.urlopen(req,timeout=30) as response:
  external=pd.read_csv(response,dtype=str,low_memory=False)
 print("External columns:",list(external.columns),flush=True)
 idcol=next((c for c in ("personId","PERSON_ID","player_id","playerId") if c in external.columns),None)
 if not idcol:raise RuntimeError("External data lacks numeric NBA player ID")
 matched=set()
 for row in external.to_dict("records"):
  pid=norm(row.get(idcol))
  if pid not in ids:continue
  matched.add(pid)
  p=profiles.setdefault(pid,{"nba_id":pid})
  def fill(target,*cols):
   if norm(p.get(target)):return
   for c in cols:
    v=norm(row.get(c))
    if v:p[target]=v;return
  fill("height","height","HEIGHT")
  fill("weight","bodyWeight","weight","WEIGHT")
  fill("draft_year","draftYear","draft_year")
  fill("draft_round","draftRound","draft_round")
  fill("draft_pick","draftNumber","draft_number")
  if not norm(p.get("position")):
   roles=[name for name,col in (("G","guard"),("F","forward"),("C","center")) if str(row.get(col,"")).lower() in ("true","1","yes","y")]
   if roles:p["position"]="-".join(roles)
  # Undrafted only when explicitly marked, not merely when draft fields are absent.
  if str(row.get("draftYear","")).strip().lower() in ("undrafted","not drafted"):
   p["draft_status"]="Undrafted"
 previous["players"]=profiles
 previous["external_source"]=URL
 (DATA/"player_bios.json").write_text(json.dumps(previous,separators=(",",":")))
 fields=["position","height","weight","draft_year","draft_round","draft_pick"]
 coverage={f:sum(bool(norm(profiles.get(pid,{}).get(f))) for pid in ids) for f in fields}
 report={"total_players":len(ids),"external_matched_ids":len(matched),"coverage":coverage,
 "missing_by_field":{f:sorted(pid for pid in ids if not norm(profiles.get(pid,{}).get(f))) for f in fields},
 "external_source":URL,
 "limitations":["No claim that every missing draft entry means undrafted","Headshot URLs require browser checks","Active status requires current official roster validation"]}
 (DATA/"bio_coverage_report.json").write_text(json.dumps(report,indent=2))
 print(json.dumps({"total_players":len(ids),"external_matched_ids":len(matched),"coverage":coverage},indent=2),flush=True)
 if not matched:raise RuntimeError("No player IDs matched; do not save empty enrichment")
if __name__=="__main__":main()
