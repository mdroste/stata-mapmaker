"""Refresh reviewed 2D PROJ grid metadata (maintainer only; no grids downloaded)."""
import hashlib
import json
from pathlib import Path
import urllib.request
from datetime import date

ROOT = Path(__file__).resolve().parents[1]
PROVIDERS = {"us_noaa": "Public Domain", "uk_os": "BSD-2-Clause",
             "au_icsm": "CC-BY-4.0", "ca_nrc": "Open Government Licence - Canada"}


def main():
    url = "https://cdn.proj.org/files.geojson"
    raw = urllib.request.urlopen(url, timeout=60).read()
    features = json.loads(raw)["features"]
    indexed = {f["properties"]["name"]: f["properties"] for f in features}
    folder = ROOT / "catalog/grid-licenses"
    folder.mkdir(exist_ok=True)
    rows = []
    for provider, license_ in PROVIDERS.items():
        filename = provider + "_README.txt"
        license_raw = urllib.request.urlopen("https://cdn.proj.org/"+filename, timeout=60).read()
        if hashlib.sha256(license_raw).hexdigest() != indexed[filename]["sha256sum"]:
            raise ValueError("PROJ license snapshot checksum failed")
        (folder / filename).write_bytes(license_raw)
        for p in indexed.values():
            if p.get("source_id") != provider or p.get("type") != "HORIZONTAL_OFFSET":
                continue
            rows.append(dict(name=p["name"], sha256=p["sha256sum"], bytes=p["file_size"],
                             license=license_, license_file=filename, license_url="https://cdn.proj.org/"+filename,
                             license_sha256=indexed[filename]["sha256sum"], description=p.get("description", ""),
                             area=p.get("area_of_use", ""), type=p["type"],
                             source=p.get("source_crs_code", ""), target=p.get("target_crs_code", "")))
    path = ROOT / "catalog/projection-grids.json"
    if path.exists():
        keys = {(r["name"], r["sha256"]) for r in rows}
        # A named old checksum remains resolvable after a maintainer refresh.
        rows += [r for r in json.loads(path.read_text(encoding="utf-8"))["grids"]
                 if r["type"] == "HORIZONTAL_OFFSET" and (r["name"], r["sha256"]) not in keys]
    path.write_text(json.dumps(dict(schema=1, source=url, source_sha256=hashlib.sha256(raw).hexdigest(),
                                    updated=date.today().isoformat(), grids=rows), indent=2)+"\n", encoding="utf-8")
    print(f"Wrote {len(rows)} optional 2D grids. Review provider license changes before release.")


if __name__ == "__main__":
    main()
