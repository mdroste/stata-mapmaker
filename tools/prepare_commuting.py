"""Normalize original membership tables; attach provenance to distinct CZ series.

XLS support is maintainer-only. Users receive small checksum-pinned CSV tables.
No boundaries or table values are inferred from the number of zones.
"""
import csv
import hashlib
import io
import json

from expand_catalog import ROOT, cached, audit
from geography_providers import psu


SOURCES = {
    "us_ers_cz_1990": ("https://ers.usda.gov/media/5687/1980-and-1990-commuting-zones-and-labor-market-areas.xls?v=98144", "County FIPS Code", "CZ90", "County name", "Name of largest place in commuting zone"),
    "us_ers_cz_2000": ("https://ers.usda.gov/media/5688/2000-commuting-zones.xls?v=37556", "FIPS", "Commuting Zone ID, 2000", "County name", None),
    "us_psu_cz_2010": ("https://sites.psu.edu/psucz/files/2018/09/counties10-zqvz0r.csv", "FIPS", "OUT10", None, None),
    "us_psu_cz_2020": ("https://sites.psu.edu/psucz/files/2024/05/county20.csv", "GEOID", "CZ20", None, None),
    "us_ers_cz_2020": ("https://ers.usda.gov/media/6968/2020-commuting-zones.csv?v=40894", "FIPStxt", "CZ2020", "CountyName", "CZName")}


def normalize(ident):
    url, county, zone, county_name, zone_name = SOURCES[ident]
    source = cached(url)
    if ".xls?" in url:
        import xlrd
        sheet = xlrd.open_workbook(source).sheet_by_index(0)
        headers = sheet.row_values(0)
        rows = [dict(zip(headers, sheet.row_values(i))) for i in range(1, sheet.nrows)]
    else:
        with source.open(encoding="cp1252" if "counties10" in url else "utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream))
    output = [dict(county_id=str(int(row[county])).zfill(5), mm_id=str(int(row[zone])),
                   county_name=str(row.get(county_name, "")), zone_name=str(row.get(zone_name, ""))) for row in rows]
    if len({r["county_id"] for r in output}) != len(output):
        raise ValueError("Duplicate source county")
    destination = ROOT / "catalog/membership" / (ident+".csv")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, ["county_id", "mm_id", "county_name", "zone_name"])
        writer.writeheader()
        writer.writerows(sorted(output, key=lambda row: row["county_id"]))
    return dict(membership_sha256=hashlib.sha256(destination.read_bytes()).hexdigest(),
                membership_source_url=url, membership_source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                membership_count=len(output), membership_zone_count=len({r["mm_id"] for r in output}),
                membership_normalization="County FIPS padded to 5 digits; CZ IDs decimal without leading zeroes; original membership unchanged")


def main():
    path = ROOT / "catalog/geographies.json"
    catalog = json.loads(path.read_text(encoding="utf-8"))
    entries = {(e["pack_id"],e["revision"]):e for e in catalog["packs"]}
    for seed in psu():
        seed.update(id_kind="digits", id_width=0)
        seed = audit(seed)
        seed.update(normalize(seed["pack_id"]))
        if seed["feature_count"] != seed["membership_zone_count"]:
            raise ValueError("Source zone count differs from membership")
        entries[(seed["pack_id"],"1")] = seed
        print(seed["pack_id"], seed["feature_count"], flush=True)
    ident = "us_ers_cz_2020"
    seed = dict(pack_id=ident, revision="1", geography="cz", vintage="2020", country="US",
        provider="USDA Economic Research Service", title="ERS 2020 commuting zones (final January 2026 release)",
        source_release="2026-01-09", source_page="https://ers.usda.gov/data-products/commuting-zones-and-labor-market-areas",
        license="USDA ERS public data; Census public boundaries", attribution="USDA ERS 2020 Commuting Zones; U.S. Census Bureau 2024 county boundaries",
        layout="us-insets", id_kind="digits", id_width=0, id_fields=["CZ2020"], scale="500k county dissolve",
        recipe=dict(kind="county_dissolve", base_pack="us_county_2024_500k", base_revision="1", repair="make_valid"),
        definition_note="Final ERS contiguous definition, distinct from Penn State 2020. Exact county membership shipped; 2024 county polygons match the final release, including Connecticut planning regions. Nonmember territories excluded explicitly.",
        default=False, priority="P1", **normalize(ident))
    if seed["membership_count"] != 3222 or seed["membership_zone_count"] != 598:
        raise ValueError("ERS source differs from reviewed final release")
    seed["feature_count"] = 598
    dependency = entries[("us_county_2024_500k","1")]
    seed["download_bytes"] = dependency["download_bytes"]
    entries[(ident,"1")] = seed
    catalog["packs"] = sorted(entries.values(), key=lambda e:(e["pack_id"],e["revision"]))
    path.write_text(json.dumps(catalog,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")


if __name__ == "__main__":
    main()
