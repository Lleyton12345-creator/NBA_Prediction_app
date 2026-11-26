"""Enrich NBA player biographies from the public Hugging Face dataset viewer.
Source: tamir25/nba_players_draft_analysis_tamir_sela (NBA PlayerIndex snapshot).
Exact PERSON_ID match only. Do not infer active status from historical roster data.
"""
import json, time, urllib.parse, urllib.request
from pathlib import Path
import pandas as pd

DATA=Path(__file__).resolve().parent/"data"
DATASET="tamir25/nba_players_draft_analysis_tamir_sela"
BASE="https://datasets-server.huggingface.co"
HEADERS={"User-Agent":"NBA-Prediction-App/1.0"}
def get(path,params):
 url=BASE+path+"?"+urllib.parse.urlencode(params)
 req=urllib.request.Request(url,headers=HEADERS)
 with urllib.request.urlopen(req,timeout=45) as response:return json.load(response)
def clean(value):
 if value is None or pd.isna(value):return None
 value=str(value).strip()
 return value if value and value.lower() not in ("none","null","nan","-","0.0") else None
def main():
 previous=json.loads((DATA/"player_bios.json").read_text())
 players=previous.get("players",{})
 master=pd.read_csv(DATA/"players.csv.gz",dtype=str,low_memory=False)
 ids=set(master.player_id.dropna().astype(str))
 splits=get("/splits",{"dataset":DATASET})["splits"]
 target=next((s for s in splits if s["split"]=="train"),splits[0])
 config=target["config"];split=target["split"]
 matched=set();count=0;total=target.get("num_rows") or 10000
 for offset in range(0,total,100):
  page=get("/rows",{"dataset":DATASET,"config":config,"split":split,"offset":offset,"length":100})
  rows=[item["row"] for item in page.get("rows",[])]
  if not rows:break
  for row in rows:
   pid=clean(row.get("PERSON_ID"))
   if not pid or pid not in ids:continue
   matched.add(pid);p=players.setdefault(pid,{"nba_id":pid})
   for dst,src in [("position","POSITION"),("height","HEIGHT"),("weight","WEIGHT"),
                   ("draft_year","DRAFT_YEAR"),("draft_round","DRAFT_ROUND"),("draft_pick","DRAFT_NUMBER")]:
    v=clean(row.get(src))
    if not clean(p.get(dst)) and v:
     if dst.startswith("draft_") and v.endswith(".0"):v=v[:-2]
     p[dst]=v
   # Explicit undrafted markers only. Empty draft fields are NOT proof.
   if str(row.get("DRAFT_YEAR","")).strip().lower() in ("undrafted","not drafted"):
    p["draft_status"]="Undrafted"
  count+=len(rows)
  print("Read",count,"matched",len(matched),flush=True)
  time.sleep(.12)
 if not matched:raise RuntimeError("No NBA player IDs matched. Existing bios unchanged.")
 previous["players"]=players
 previous["external_source"]=DATASET
 (DATA/"player_bios.json").write_text(json.dumps(previous,separators=(",",":")))
 fields=["position","height","weight","draft_year","draft_round","draft_pick"]
 report={"total_players":len(ids),"external_matched_ids":len(matched),
  "coverage":{f:sum(bool(clean(players.get(pid,{}).get(f))) for pid in ids) for f in fields},
  "missing_by_field":{f:sorted(pid for pid in ids if not clean(players.get(pid,{}).get(f))) for f in fields},
  "source":DATASET,"limitations":["Snapshot is historical; do not use for 2026 active status",
  "Headshots are loaded from NBA CDN and not independently validated in this import",
  "Undrafted requires explicit verification; empty draft fields are unknown"]}
 (DATA/"bio_coverage_report.json").write_text(json.dumps(report,indent=2))
 print(json.dumps({k:v for k,v in report.items() if k!="missing_by_field"},indent=2),flush=True)
if __name__=="__main__":main()
