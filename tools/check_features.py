"""Offline integration/capacity check with real Census counties and state outlines."""
import argparse
import csv
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"python"))
from mapmaker_engine import geography as geo
from mapmaker_engine.render import load_pack


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle",type=Path)
    parser.add_argument("--formats",nargs="+",choices=("png","pdf","svg"),default=["png","pdf","svg"])
    args=parser.parse_args()
    root=args.bundle.resolve() if args.bundle else ROOT
    work=ROOT/".cache/features-integration"
    home=work/"library"; work.mkdir(parents=True,exist_ok=True)
    source=ROOT/".cache/expanded-integration/library/packs/us_county_2020_500k/1"
    county=home/"packs/us_county_2020_500k/1"
    if not county.exists(): shutil.copytree(source,county)
    entry=next(e for e in geo.read_catalog(ROOT,home)["packs"] if e["pack_id"]=="us_state_2020_500k")
    geo.install(ROOT,home,entry,ROOT/".cache/catalog-sources/cb_2020_us_state_500k.zip")
    manifest,geometry=load_pack(county)
    data=work/"data.csv"
    with data.open("w",encoding="utf-8",newline="") as stream:
        writer=csv.writer(stream); writer.writerow(["mm_id","mm_panel","mm_bin","mm_size","mm_label","mm_uncertain"])
        for panel in ("2010","2020"):
            for i,feature in enumerate(geometry["features"]):
                writer.writerow([feature["id"],panel,i%5+1,(i%80+1)*10,feature["id"] if i%150==0 else "",int(i%9==0)])
    flows=work/"flows.csv"; flows.write_text("origin,destination,volume\n06037,36061,6\n06037,36061,6\n17031,06037,10\n02020,06037,3\n",encoding="utf-8")
    points=work/"points.csv"; points.write_text("x,y,size,label\n-118.24,34.05,100,Los Angeles\n-87.63,41.88,80,Chicago\n",encoding="utf-8")
    mode="frozen" if args.bundle else "source"
    out=ROOT/"tests/output/features-integration"/mode; out.mkdir(parents=True,exist_ok=True)
    scale=dict(mode="custom",cutoffs=[1,2,3,4],labels=["A","B","C","D","E"],interval="upper-inclusive")
    request=dict(schema=2,operation="figure",root=str(root),datadir=str(home),pack=str(county),geography=manifest["geography"],vintage=manifest["vintage"],
                 data=str(data),panels=[dict(key=k,scale=scale) for k in ("2010","2020")],projection="conus-albers",layout="conus",outline="states",
                 points=str(points),flows=str(flows),flowtop=0,uncertainty=True,scalebar=True,northarrow=True,replace=True,dpi=100,labellimit=10,
                 symbolmax=50,width=13,height=6,title="Synthetic county observations with explicit layers")
    exe=root/"runtime/mapmaker-render/mapmaker-render.exe"
    command=[str(exe)] if args.bundle else [sys.executable,str(ROOT/"python/mapmaker_cli.py")]
    measurements=[]
    for extension in args.formats:
        paths={k:str(work/(mode+"-"+k+".json")) for k in ("response","status")}
        task=dict(request,**paths,output=str(out/("layers."+extension)),manifest=str(out/("layers-"+extension+".json")))
        path=work/"request.json"; path.write_text(json.dumps(task),encoding="utf-8")
        start=time.perf_counter(); subprocess.run(command+["--request",str(path)],check=True); elapsed=time.perf_counter()-start
        result=json.loads(Path(paths["response"]).read_text(encoding="utf-8"))
        assert len(result["outlines"])==1
        assert all(p["matched"]==manifest["feature_count"] for p in result["panels"])
        assert all(p["flows"]["omitted_volume"]==3 for p in result["panels"])
        assert all(len(p["points"]["map"]["shown"])==2 for p in result["panels"])
        assert all(p["decorations"]["map"]["scale_meters"]>0 for p in result["panels"])
        assert result["panels"][0]["colors"]==result["panels"][1]["colors"]
        measurements.append(dict(format=extension,seconds=round(elapsed,3),bytes=Path(task["output"]).stat().st_size,rows=2*manifest["feature_count"]))
    report=dict(mode=mode,checks="county panels, vintage-matched outlines, proportional symbols, points, aggregate flows, omitted volume, labels, uncertainty, local north/scale",measurements=measurements)
    (work/(mode+"-validation.json")).write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report))


if __name__=="__main__": main()
