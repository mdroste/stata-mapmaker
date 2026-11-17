"""Audit optional sources and merge immutable catalog entries.

Only actual links in the provider index are selected. Download bytes, checksums,
IDs and attribute fields are checked before an entry becomes installable.
Run with --provider census (or a named provider); downloads stay in .cache.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import re
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))
from mapmaker_engine import geography as geo
from mapmaker_engine.sources import records, identifier

CACHE = ROOT / ".cache/catalog-sources"
STATES = dict(zip("01 02 04 05 06 08 09 10 11 12 13 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31 32 33 34 35 36 37 38 39 40 41 42 44 45 46 47 48 49 50 51 53 54 55 56 60 66 69 72 78".split(),
    "Alabama|Alaska|Arizona|Arkansas|California|Colorado|Connecticut|Delaware|District of Columbia|Florida|Georgia|Hawaii|Idaho|Illinois|Indiana|Iowa|Kansas|Kentucky|Louisiana|Maine|Maryland|Massachusetts|Michigan|Minnesota|Mississippi|Missouri|Montana|Nebraska|Nevada|New Hampshire|New Jersey|New Mexico|New York|North Carolina|North Dakota|Ohio|Oklahoma|Oregon|Pennsylvania|Rhode Island|South Carolina|South Dakota|Tennessee|Texas|Utah|Vermont|Virginia|Washington|West Virginia|Wisconsin|Wyoming|American Samoa|Guam|Northern Mariana Islands|Puerto Rico|U.S. Virgin Islands".split("|")))
LEVELS = {"tract": (11, "Census tracts"), "puma10": (7, "2010 PUMAs"), "puma20": (7, "2020 PUMAs"),
          "bg": (12, "Block groups"), "place": (7, "Places (incorporated and census-designated)"),
          "cousub": (10, "County subdivisions"), "sldu": (5, "State legislative upper chambers"),
          "sldl": (5, "State legislative lower chambers"), "elsd": (7, "Elementary school districts"),
          "scsd": (7, "Secondary school districts"), "unsd": (7, "Unified school districts"),
          "vtd": (11, "Voting districts"), "state": (2, "States and equivalents"),
          "county": (5, "Counties and equivalents"), "cbsa": (5, "Core-based statistical areas (metro/micro)"),
          "csa": (3, "Combined statistical areas"), "metdiv": (10, "Metropolitan divisions (CBSA + division GEOID)"),
          "zcta510": (5, "2010 ZIP Code Tabulation Areas"), "zcta520": (5, "2020 ZIP Code Tabulation Areas"),
          "aiannh": (4, "American Indian, Alaska Native and Native Hawaiian areas"),
          "anrc": (7, "Alaska Native Regional Corporations")}


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mapmaker catalog audit/2"})
    with urllib.request.urlopen(req, timeout=120) as response:
        raw = response.read(geo.MAX_DOWNLOAD + 1)
    if len(raw) > geo.MAX_DOWNLOAD:
        raise ValueError("Source exceeds download limit: " + url)
    return raw


def cached(url):
    CACHE.mkdir(parents=True, exist_ok=True)
    name = url.split("?")[0].rsplit("/", 1)[-1]
    path = CACHE / (hashlib.sha256(url.encode()).hexdigest()[:12] + "-" + name)
    if not path.exists():
        raw = fetch(url)
        temporary = path.with_name(path.name + ".part")
        temporary.write_bytes(raw)
        temporary.replace(path)
    return path


def census_seeds():
    # 2013 is the first modern generalized release using 2010 tract/PUMA definitions.
    # Editions are explicit, not aliases for the newest file on the server.
    for year in [2013, 2014, 2015, 2017, 2019, 2020, 2021, 2022, 2023, 2024, 2025]:
        base = f"https://www2.census.gov/geo/tiger/GENZ{year}/" + ("shp/" if year >= 2014 else "")
        listing = fetch(base).decode()
        for name in sorted(set(re.findall(r'href="(cb_[^"]+_500k.zip)"', listing))):
            if name == "cb_2013_23_puma10_500k.zip":
                continue  # Provider returns HTML; reviewed 2014 snapshot supplies Maine's 2010 PUMAs.
            match = re.fullmatch(r"cb_(\d+)_(\w+)_(\w+)_500k.zip", name)
            if not match:
                continue
            _, state, level = match.groups()
            if state != "us" and state not in STATES:
                continue
            if state == "us" and level in {"bg", "vtd", "tract"}:
                continue  # Keep fine boundaries partitioned by state.
            cd = re.fullmatch(r"cd(\d+)", level)
            if cd:
                if state != "us":
                    continue
                # One published boundary snapshot for every modern Congress.
                if year not in [2013, 2015, 2017, 2019, 2021, 2023, 2025]:
                    continue
                width, label, geography = 4, "Congressional districts", "cd"
            elif level not in LEVELS:
                continue
            else:
                width, label = LEVELS[level]
                geography = level
                if year == 2013 and level not in {"tract", "puma10", "state", "county"}:
                    continue
                if year not in {2013, 2020, 2024, 2025} and not (year == 2014 and state == "23" and level == "puma10"):
                    continue
                if year in {2024, 2025} and level not in {"state", "county", "cbsa", "csa", "metdiv"}:
                    continue
            ident = f"us_cd{cd[1]}_{year}" if cd else f"us_{state + '_' if state != 'us' else ''}{level}_{year}_500k"
            entry = dict(pack_id=ident, revision="1", geography=geography, vintage=str(year),
                country="US", provider="U.S. Census Bureau", source_url=base+name, id_fields=[],
                id_kind="digits", id_width=width, layout="us-insets", scale="500k", default=False,
                title=f"{STATES.get(state, 'United States')}: {label} ({year})",
                coverage=STATES.get(state, "United States and territories included by source"),
                source_page=f"https://www.census.gov/geographies/mapping-files/{year}/geo/carto-boundary-file.html",
                license="U.S. Census Bureau public data", source_release=str(year), priority="P1" if geography in {"cd", "state", "county", "tract", "puma10", "puma20", "cbsa", "csa", "metdiv"} else "P2")
            if state != "us":
                entry["state_fips"] = state
            if year == 2013:
                entry["encoding"] = "cp1252"
            if year == 2014 and state == "23" and level == "puma10":
                entry.update(dimensions="xy", definition_note="Maine 2010 PUMAs from the 2014 snapshot. Source PolygonZ is rendered in XY; Z/M are explicitly discarded.")
            if level in {"vtd", "sldu", "sldl"}:
                entry["id_kind"] = "string"
            if cd:
                entry["congress"] = int(cd[1])
            if level in {"tract", "puma10", "puma20", "bg", "vtd", "zcta510", "zcta520"}:
                entry["boundary_definition"] = "2010" if year < 2020 else "2020"
            if level in {"cbsa", "csa", "metdiv"}:
                entry["definition_note"] = "Census boundary snapshot; consult the release technical documentation for OMB delineation date."
            if level.startswith("zcta"):
                entry["definition_note"] = "ZCTAs approximate ZIP delivery areas; these are not USPS ZIP polygons or a complete ZIP list."
            if level in {"aiannh", "anrc"}:
                entry["definition_note"] = "Provider area types retained in attributes; areas are not an exclusive state hierarchy."
            yield entry


def audit(entry):
    entry = dict(entry)
    geo.check_url(entry["source_url"])
    path = cached(entry["source_url"])
    raw = path.read_bytes()
    # Discover Census field conventions from DBF rather than assume an annual schema.
    if not entry["id_fields"]:
        import io, shapefile
        parts = geo.shapefile_parts(path, entry.get("source_member"))
        with shapefile.Reader(dbf=io.BytesIO(parts["dbf"])) as reader:
            fields = {f[0] for f in reader.fields[1:]}
        entry["id_fields"] = [next(f for f in ("GEOID", "GEOID20", "GEOID10") if f in fields)]
    crs, rows, hashes = records(path, entry)
    ids, fields, source_count = [], set(), 0
    for attrs, geometry in rows:
        source_count += 1
        if any(str(attrs.get(k)) != str(v) for k, v in entry.get("filter", {}).items()):
            continue
        if not geometry and entry.get("skip_null_geometry"):
            continue
        ids.append(identifier(attrs, entry))
        fields.update(attrs)
    if not ids or (len(ids) != len(set(ids)) and not entry.get("dissolve")):
        raise ValueError(f"Missing/duplicate IDs: {entry['pack_id']}")
    if entry.get("expected_source_count") and source_count != entry["expected_source_count"]:
        raise ValueError("Provider returned incomplete feature collection")
    entry.update(source_sha256=hashlib.sha256(raw).hexdigest(), download_bytes=len(raw),
                 source_feature_count=source_count, feature_count=len(set(ids)),
                 id_examples=ids[:5], attribute_fields=sorted(fields),
                 source_crs_name=crs.name)
    return entry


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", default="census")
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()
    catalog_path = ROOT / "catalog/geographies.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    existing = {(e["pack_id"], e["revision"]): e for e in catalog["packs"]}
    if args.provider == "census":
        seeds = list(census_seeds())
    else:
        from geography_providers import seeds_for
        seeds = list(seeds_for(args.provider))
    pending = [e for e in seeds if (e["pack_id"], e["revision"]) not in existing]
    print(f"Auditing {len(pending)} new {args.provider} sources", flush=True)
    failures = []
    additions = {}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(audit, entry): entry for entry in pending}
        for future in as_completed(futures):
            entry = futures[future]
            try:
                entry = future.result()
                existing[(entry["pack_id"], entry["revision"])] = entry
                additions[(entry["pack_id"], entry["revision"])] = entry
                print("OK", entry["pack_id"], entry["feature_count"], flush=True)
            except Exception as error:
                failures.append(dict(pack_id=entry["pack_id"], error=str(error)))
                print("FAIL", entry["pack_id"], str(error), flush=True)
    # Re-read before merging so a separate provider audit cannot drop additions
    # committed while these downloads were in progress. Run final writes serially.
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    existing = {(e["pack_id"], e["revision"]): e for e in catalog["packs"]}
    existing.update(additions)
    catalog.update(updated="2026-11-16", packs=sorted(existing.values(), key=lambda e: (e["pack_id"], e["revision"])))
    geo.validate_catalog(catalog)
    catalog_path.write_text(json.dumps(catalog, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    (CACHE / ("audit-"+args.provider+".json")).write_text(json.dumps(failures, indent=2))
    if failures:
        raise SystemExit(f"{len(failures)} sources need review; no failed entries were published")


if __name__ == "__main__":
    main()
