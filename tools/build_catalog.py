"""Maintainer tool: download and fingerprint the explicit Census catalog sources.

Run deliberately when adding/reviewing sources; never runs during rendering.
Existing cached ZIPs are reused. Commit the resulting catalog, not the downloads.
"""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import json
from pathlib import Path
import urllib.request
import zipfile

import shapefile

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / ".cache/catalog-sources"


def seeds():
    for year, congress in [(2010, 111), (2013, 113), (2020, 116), (2023, 118), (2024, 119)]:
        filename = ("gz_2010_us_500_11_20m.zip" if year == 2010 else
                    f"cb_{year}_us_cd{congress}_500k.zip")
        yield dict(pack_id=f"us_cd{congress}_{year}", geography="cd", vintage=str(year),
                   title=f"U.S. congressional districts: {congress}th Congress ({year})",
                   congress=congress, id_width=4, filename=filename,
                   scale="20m" if year == 2010 else "500k")
    for geography, width in [("state", 2), ("county", 5)]:
        yield dict(pack_id=f"us_{geography}_2020_500k", geography=geography, vintage="2020",
                   title=f"U.S. {geography} boundaries (2020)", id_width=width,
                   filename=f"cb_2020_us_{geography}_500k.zip", scale="500k")
    for state, name in [("06", "California"), ("36", "New York")]:
        for geography, width, label in [("tract", 11, "census tracts"), ("puma20", 7, "2020 PUMAs")]:
            yield dict(pack_id=f"us_{state}_{geography}_2020_500k", geography=geography,
                       vintage="2020", title=f"{name} {label}", id_width=width,
                       filename=f"cb_2020_{state}_{geography}_500k.zip", scale="500k",
                       coverage=name)


def fingerprint(entry):
    entry = dict(entry)
    year = entry["vintage"]
    filename = entry.pop("filename")
    url = f"https://www2.census.gov/geo/tiger/GENZ{year}/" + ("shp/" if int(year) >= 2014 else "") + filename
    path = CACHE / filename
    if not path.exists():
        with urllib.request.urlopen(url, timeout=60) as response:
            raw = response.read()
        with zipfile.ZipFile(io.BytesIO(raw)):
            pass
        path.write_bytes(raw)
    raw = path.read_bytes()
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        dbf = next(n for n in archive.namelist() if n.lower().endswith(".dbf"))
        reader = shapefile.Reader(dbf=io.BytesIO(archive.read(dbf)))
        fields = [f[0] for f in reader.fields[1:]]
        id_fields = (["GEOID"] if "GEOID" in fields else ["GEOID20"] if "GEOID20" in fields else
                     ["STATE", "CD"] if entry["geography"] == "cd" else [])
        if not id_fields or not all(f in fields for f in id_fields):
            raise ValueError(f"Inspect ID fields for {filename}: {fields}")
    entry.update(revision="1", country="US", provider="U.S. Census Bureau",
                 coverage=entry.get("coverage", "United States and source territories"),
                 id_kind="digits", id_fields=id_fields, source_url=url,
                 source_sha256=hashlib.sha256(raw).hexdigest(), download_bytes=len(raw),
                 source_feature_count=len(reader), license="U.S. Census Bureau public data",
                 source_page=f"https://www.census.gov/geographies/mapping-files/{year}/geo/carto-boundary-file.html",
                 layout="us-insets", default=False)
    print(entry["pack_id"], len(raw), fields, flush=True)
    return entry


if __name__ == "__main__":
    CACHE.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        entries = list(pool.map(fingerprint, seeds()))
    defaults = [dict(pack_id=f"{geo}-legacy", geography=geo, vintage="legacy", revision="1",
                     title=title, country="US", provider="Original Mapmaker",
                     coverage="Legacy coverage; see pack manifest", scale="legacy", default=geo != "tract",
                     id_kind="digits", id_width=width,
                     provenance="Original source and boundary date unverified; fixed projection.")
                for geo, title, width in [("county", "U.S. counties (legacy)", 5),
                                           ("state", "U.S. states (legacy)", 2),
                                           ("cz", "U.S. commuting zones (legacy)", 0),
                                           ("tract", "U.S. census tracts (legacy)", 11)]]
    destination = ROOT / "catalog/geographies.json"
    destination.parent.mkdir(exist_ok=True)
    current = json.loads(destination.read_text(encoding="utf-8")) if destination.exists() else dict(packs=[])
    combined = {(e["pack_id"], e["revision"]): e for e in current["packs"]}
    for entry in defaults + entries:
        key = (entry["pack_id"], entry["revision"])
        if key in combined and combined[key].get("source_sha256") != entry.get("source_sha256"):
            raise ValueError("Source changed; publish a new revision instead of overwriting")
        combined.setdefault(key, entry)
    destination.write_text(json.dumps(dict(schema=1, updated="2026-11-16", packs=list(combined.values())), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
