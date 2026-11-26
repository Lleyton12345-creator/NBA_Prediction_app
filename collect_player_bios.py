"""Collect NBA player biographies by NBA ID, without guessing missing fields.
Uses NBA Stats PlayerIndex season snapshots. Run: python collect_player_bios.py
"""
import gzip, io, json, os, time, urllib.request
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parent
DATA=ROOT/"data"
UA={"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
"Referer":"https://www.nba.com/","Origin":"https://www.nba.com",
"Accept":"application/json, text/plain, */*"}
FIELDS={"position":["POSITION"],"height":["HEIGHT"],"weight":["WEIGHT"],
"draft_year":["DRAFT_YEAR"],"draft_round":["DRAFT_ROUND"],"draft_pick":["DRAFT_NUMBER"],
"roster_status":["ROSTER_STATUS"],"nba_id":["PERSON_ID","PLAYER_ID"]}
def clean(v):
    if v is None or str(v).strip().lower() in ("","null","none","nan","-","undrafted","0"): return None
    return str(v).strip()
def get(row,keys):
    for k in keys:
        v=clean(row.get(k))
        if v is not None:return v
    return None
def nba_rows(payload):
    for result in payload.get("resultSets",payload.get("resultSet",[])):
        if isinstance(result,dict) and result.get("headers"):
            for row in result.get("rowSet",[]):
                yield dict(zip(result["headers"],row))
def fetch(season):
    url=("https://stats.nba.com/stats/playerindex?LeagueID=00&Season="+season+
         "&SeasonType=Regular%20Season&TeamID=0&PlayerID=0&College=&Country=&DraftYear=&DraftPick=&Height=&Weight=&Active=&Historical=1")
    req=urllib.request.Request(url,headers=UA)
    with urllib.request.urlopen(req,timeout=35) as resp:return json.load(resp)
def main():
    master=pd.read_csv(DATA/"players.csv.gz",compression="gzip",low_memory=False,dtype=str)
    if "player_id" not in master.columns:raise RuntimeError("Master players missing player_id")
    ids=set(master.player_id.dropna().astype(str))
    cache_dir=DATA/"bio_source_cache";cache_dir.mkdir(exist_ok=True)
    merged={};sources={};failures=[]
    for year in range(2003,2027):
        season=f"{year}-{str(year+1)[-2:]}";cache=cache_dir/(season+".json")
        try:
            if cache.exists():payload=json.loads(cache.read_text())
            else:
                payload=fetch(season)
                cache.write_text(json.dumps(payload))
                time.sleep(1.5)
            count=0
            for row in nba_rows(payload):
                pid=get(row,["PERSON_ID","PLAYER_ID"])
                if not pid or pid not in ids:continue
                item=merged.setdefault(pid,{})
                for field,aliases in FIELDS.items():
                    v=get(row,aliases)
                    if v is not None:item[field]=v
                if season=="2026-27" and row.get("ROSTER_STATUS") is not None:
                    item["roster_status"]=str(row["ROSTER_STATUS"])
                sources[pid]=season
                count+=1
            print(season,count,flush=True)
        except Exception as e:
            failures.append({"season":season,"error":str(e)})
            print("FAILED",season,str(e),flush=True)
    # No inferred player positions, photos, or draft picks. NBA CDN ID is validated separately by browser.
    out={"source":"NBA Stats PlayerIndex historical season snapshots",
         "source_url":"https://stats.nba.com/stats/playerindex",
         "players":merged,"failed_seasons":failures}
    (DATA/"player_bios.json").write_text(json.dumps(out,separators=(",",":")))
    required=["position","height","weight","draft_year","draft_round","draft_pick"]
    coverage={k:sum(bool(row.get(k)) for row in merged.values()) for k in required}
    report={"master_player_count":len(ids),"matched_player_count":len(merged),
            "coverage":coverage,"missing_bio_player_ids":sorted(ids-set(merged)),
            "failed_seasons":failures,
            "note":"Missing values are not fabricated; active status requires a current roster check. Headshots load by NBA ID with a fallback."}
    (DATA/"bio_coverage_report.json").write_text(json.dumps(report,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k!="missing_bio_player_ids"},indent=2))
    if not merged:raise RuntimeError("No biographies collected. NBA Stats may be blocking requests.")
if __name__=="__main__":main()
