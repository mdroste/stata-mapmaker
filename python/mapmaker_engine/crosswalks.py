"""Explicit count allocation. Rates are reconstructed from two allocated totals."""
import csv
import hashlib
import io
import json
from pathlib import Path

from . import geography as geo
from .figure_config import read_json
from .figure_layers import read_table, normalize_id, finite
from .geography_tables import atomic_bytes
from .render import load_pack


def pack(root,home,token):
    name,_,revision = token.partition("@")
    path,manifest = geo.resolve(root,home,name,revision or "1")
    manifest = dict(dict(id_kind="digits",id_width=0),**manifest)
    _,geometry = load_pack(path)
    return manifest,{f["id"] for f in geometry["features"]}


def validate(value):
    if value.get("schema") != "mapmaker-crosswalk-1" or not value.get("universe") or not value.get("method"):
        raise ValueError("Invalid crosswalk; declare the weight universe and allocation method")
    seen,totals = set(),{}
    for row in value["rows"]:
        key = row["source"],row["target"]
        if key in seen:
            raise ValueError("Crosswalk has duplicate source/target pairs")
        seen.add(key)
        weight = finite(row["weight"],"Crosswalk weight",True)
        totals[key[0]] = totals.get(key[0],0)+weight
    if any(v>1+1e-10 for v in totals.values()):
        raise ValueError("Source weights sum above 1; weights are never silently normalized")
    return totals


def run(request,home):
    root = Path(request["root"])
    action = request["action"]
    if action == "import":
        if not all(request.get(k) for k in ("source","targetpack","universe","method","saving")):
            raise ValueError("Import requires source(pack@revision), targetpack(pack@revision), universe(), method(), saving()")
        source,sids = pack(root,home,request["source"])
        target,tids = pack(root,home,request["targetpack"])
        rows,checksum = read_table(request["using"],["source","target","weight"],1000000)
        normalized = []
        for row in rows:
            sid,tid = normalize_id(row["source"],source),normalize_id(row["target"],target)
            if sid not in sids or tid not in tids:
                raise ValueError("Crosswalk IDs are absent from a declared source/target revision")
            normalized.append(dict(source=sid,target=tid,weight=finite(row["weight"],"Weight",True)))
        value = dict(schema="mapmaker-crosswalk-1",source={k:source[k] for k in ("pack_id","revision","geometry_sha256","id_kind","id_width")},
                     target={k:target[k] for k in ("pack_id","revision","geometry_sha256")},universe=request["universe"],method=request["method"],
                     direction="source to target; weight is the fraction of each source total allocated to target",
                     source_table_sha256=checksum,rows=sorted(normalized,key=lambda r:(r["source"],r["target"])))
        totals = validate(value)
        value["coverage"] = dict(source_regions=len(sids),covered_sources=len(totals),target_regions=len(tids),covered_targets=len({r["target"] for r in normalized}),
                                 incomplete_sources=sum(v<1-1e-10 for v in totals.values()),uncovered_sources=len(sids-set(totals)))
        atomic_bytes(Path(request["saving"]),(json.dumps(value,indent=2)+"\n").encode(),request.get("replace",False))
        return dict(path=request["saving"],coverage=value["coverage"]),[f"Saved source-to-target crosswalk: {len(normalized)} pairs; {value['coverage']}","Weights were validated without normalization. Allocation is separate from mapping."]
    path = Path(request.get("using") or request["target"])
    if path.stat().st_size > 128*1024*1024:
        raise ValueError("Crosswalk exceeds 128 MiB")
    value = json.loads(path.read_text(encoding="utf-8"))
    totals = validate(value)
    if action == "describe":
        return dict(crosswalk=value),[value["direction"],f"Universe: {value['universe']}; method: {value['method']}",str(value.get("coverage",{})),"Fractional allocation of counts assumes this weight universe is appropriate; supplied rates are not accepted."]
    if action not in {"apply","verify"}:
        raise ValueError("Crosswalk actions: import, describe, verify, apply")
    for pin in (value["source"],value["target"]):
        actual,valid_ids = pack(root,home,pin["pack_id"]+"@"+pin["revision"])
        if pin is value["source"]:
            source_ids = valid_ids
            source_manifest = actual
        else:
            target_ids = valid_ids
        if actual["geometry_sha256"]!=pin["geometry_sha256"]:
            raise ValueError("Crosswalk geography differs from its pinned revision")
    if any(r["source"] not in source_ids or r["target"] not in target_ids for r in value["rows"]):
        raise ValueError("Crosswalk ID is absent from its pinned geography")
    if action == "verify":
        return dict(verified=True),["Crosswalk weights, IDs, and pinned geography checksums verified."]
    rows,_ = read_table(request["data"],["mm_id","numerator"],1000000)
    rate = bool(request.get("denominator"))
    inputs = {}
    for row in rows:
        sid = normalize_id(row["mm_id"],source_manifest)
        if sid not in source_ids:
            raise ValueError("Input ID is absent from the pinned source geography: " + sid)
        if sid in inputs:
            raise ValueError("Aggregate to one observation per source ID before allocating")
        inputs[sid] = (finite(row["numerator"],"Count/numerator",True),finite(row["denominator"],"Denominator",True) if rate else 0)
    output = {}
    for row in value["rows"]:
        if row["source"] not in inputs:
            continue
        result = output.setdefault(row["target"],[0.,0.,set()])
        n,d = inputs[row["source"]]
        result[0] += n*row["weight"]; result[1] += d*row["weight"]; result[2].add(row["source"])
    expected = {}
    for row in value["rows"]:
        expected.setdefault(row["target"],set()).add(row["source"])
    fields = ["mm_id","numerator","denominator","value","contributing_sources","missing_sources"]
    stream=io.StringIO(newline=""); writer=csv.DictWriter(stream,fieldnames=fields); writer.writeheader()
    for tid in sorted(expected):
        n,d,seen = output.get(tid,[0.,0.,set()])
        writer.writerow(dict(mm_id=tid,numerator=n if seen else "",denominator=d if seen and rate else "",
                             value=(n/d if d else "") if rate else (n if seen else ""),contributing_sources=len(seen),missing_sources=len(expected[tid]-seen)))
    initial = [sum(r[i] for r in inputs.values()) for i in (0,1)]
    allocated = [sum(r[i] for r in output.values()) for i in (0,1)]
    unallocated = [a-b for a,b in zip(initial,allocated)]
    for number in initial+allocated+unallocated:
        finite(number,"Allocation total (overflow)")
    report = dict(input_numerator=initial[0],allocated_numerator=allocated[0],unallocated_numerator=unallocated[0],
                  input_denominator=initial[1] if rate else None,allocated_denominator=allocated[1] if rate else None,
                  unallocated_denominator=unallocated[1] if rate else None,uncovered_selected_ids=sorted(set(inputs)-set(totals)),
                  crosswalk_sha256=hashlib.sha256(Path(request["using"]).read_bytes()).hexdigest(),universe=value["universe"],method=value["method"])
    atomic_bytes(Path(request["saving"]),stream.getvalue().encode(),request.get("replace",False))
    if request.get("audit"):
        atomic_bytes(Path(request["audit"]),(json.dumps(report,indent=2)+"\n").encode(),request.get("replace",False))
    return dict(path=request["saving"],allocation=report), [f"Allocated numerator/count: {allocated[0]:.17g} of {initial[0]:.17g}; unallocated: {unallocated[0]:.17g}"]+([f"Allocated denominator: {allocated[1]:.17g} of {initial[1]:.17g}; unallocated: {unallocated[1]:.17g}"] if rate else [])+["Inspect missing_sources before using target estimates; no weights were renormalized."]
