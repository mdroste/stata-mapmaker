"""Compile every audited optional source offline, with representative map exports.

Temporary compiled packs are removed after verification. Download caches remain.
Reports record measured installed bytes and failures without editing the catalog.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))
from mapmaker_engine import geography as geo
from mapmaker_engine.render import load_pack
from mapmaker_engine.geography_tables import inspect


def check(entry, preview=False):
    started = time.monotonic()
    url = entry["source_url"]
    filename = hashlib.sha256(url.encode()).hexdigest()[:12] + "-" + url.split("?")[0].rsplit("/",1)[-1]
    source = ROOT / ".cache/catalog-sources" / filename
    if not source.exists():
        source = ROOT / ".cache/catalog-sources" / url.split("?")[0].rsplit("/",1)[-1]
    if not source.is_file():
        return dict(pack_id=entry["pack_id"], ok=False, error="Source cache missing")
    try:
        with tempfile.TemporaryDirectory(prefix="mapmaker-check-") as home:
            path = geo.install(ROOT, home, entry, source)
            manifest, pack = load_pack(path)
            size = sum(p.stat().st_size for p in path.iterdir() if p.is_file())
            if preview:
                output = ROOT / "tests/output/expansion" / (entry["pack_id"]+".png")
                output.parent.mkdir(parents=True, exist_ok=True)
                inspect(dict(saving=str(output), replace=True), path, manifest, "preview")
            return dict(pack_id=entry["pack_id"], ok=True, features=manifest["feature_count"],
                        installed_bytes=size, seconds=round(time.monotonic()-started,2),
                        repaired_ids=len(manifest.get("repaired_ids", [])),
                        nonspatial_ids=len(manifest.get("nonspatial_ids", [])), preview=preview)
    except Exception as error:
        return dict(pack_id=entry["pack_id"], ok=False, error=str(error))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--only", default="")
    parser.add_argument("--report", default=".cache/expansion-validation.json")
    parser.add_argument("--pending", action="store_true", help="Retain passing results and check additions/previous failures")
    args = parser.parse_args()
    catalog = geo.read_catalog(ROOT)
    report = ROOT / args.report
    previous = [r for r in json.loads(report.read_text(encoding="utf-8")) if r["ok"]] if args.pending and report.exists() else []
    done = {r["pack_id"] for r in previous}
    entries = [e for e in catalog["packs"] if e.get("source_url") and e["pack_id"] not in done and (not args.only or args.only in e["pack_id"])]
    previews = set()
    seen = set()
    for entry in entries:
        key = (entry["provider"], entry["geography"])
        if key not in seen:
            previews.add(entry["pack_id"])
            seen.add(key)
        if entry["pack_id"] in {"us_06_tract_2020_500k", "us_psu_cz_2020", "world_ne_country_10m", "world_ne_country_50m", "au_sa2_2026", "us_11001_block_2020", "us_ucla_cd103"}:
            previews.add(entry["pack_id"])
    results = previous
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(check, e, e["pack_id"] in previews): e for e in entries}
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            print("OK" if result["ok"] else "FAIL", result["pack_id"], result.get("error", result.get("features")), flush=True)
            (ROOT / args.report).write_text(json.dumps(results, indent=2)+"\n", encoding="utf-8")
    failures = [r for r in results if not r["ok"]]
    print(f"{len(results)-len(failures)}/{len(results)} packs passed", flush=True)
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
