"""Offline real-source projection checks; accepts --bundle for the frozen runtime.

Requires the geography download cache and the optional UK grid in the integration
library. These are maintainer fixtures, never files shipped in the default bundle.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path)
    args = parser.parse_args()
    from mapmaker_engine import geography as geo
    from mapmaker_engine.projection_resources import grid_entry, grid_path, verify
    home = ROOT / ".cache/projection-integration/library"
    home.mkdir(parents=True, exist_ok=True)
    catalog = {e["pack_id"]: e for e in geo.read_catalog(ROOT)["packs"]}
    for name in ("world_ne_country_110m", "au_ste_2021", "ca_province_2021", "eu_nuts1_2021_10m"):
        entry = catalog[name]
        url = entry["source_url"]
        filename = url.split("?")[0].rsplit("/",1)[-1]
        source = ROOT / ".cache/catalog-sources" / (hashlib.sha256(url.encode()).hexdigest()[:12]+"-"+filename)
        if not source.exists():
            source = ROOT / ".cache/catalog-sources" / filename
        geo.install(ROOT, home, entry, source)
        print("Fixture:", name, flush=True)
    root = args.bundle.resolve() if args.bundle else ROOT
    command = [sys.executable, str(ROOT / "python/mapmaker_cli.py")]
    if args.bundle:
        binary = root / "runtime/mapmaker-render/mapmaker-render"
        command = [str(binary.with_suffix(".exe") if os.name == "nt" else binary)]
    output = ROOT / "tests/output/projections" / ("frozen" if args.bundle else "source")
    output.mkdir(parents=True, exist_ok=True)
    records = []

    def invoke(options, env=None):
        request = dict(dict(schema=1, root=str(root), datadir=str(home), operation="library", category="projection",
                            response=str(output/"response.json"), status=str(output/"status.txt")), **options)
        (output/"request.json").write_text(json.dumps(request), encoding="utf-8")
        started = time.monotonic()
        subprocess.run([*command, "--request", str(output/"request.json")], check=True, env=env)
        result = json.loads((output/"response.json").read_text(encoding="utf-8"))
        records.append(dict(action=request["action"], projection=request.get("projection"),
                            geography=request.get("geography", request.get("target")), seconds=round(time.monotonic()-started,3)))
        return result

    invoke(dict(action="cache", target="purge"))
    fixtures = {
        "equalearth": ("world_ne_country_110m", ""), "equalearth-atlantic": ("world_ne_country_110m", ""),
        "equalearth-pacific": ("world_ne_country_110m", ""), "robinson": ("world_ne_country_110m", ""),
        "winkeltripel": ("world_ne_country_110m", ""), "interrupted-goode": ("world_ne_country_110m", ""),
        "orthographic": ("world_ne_country_110m", ""), "regional-laea": ("world_ne_country_110m", ""),
        "azimuthal-equidistant": ("world_ne_country_110m", ""),
        "arctic-stereo": ("world_ne_country_110m", "-180 55 180 90"),
        "arctic-equalarea": ("world_ne_country_110m", "-180 55 180 90"),
        "antarctic-stereo": ("world_ne_country_110m", "-180 -90 180 -55"),
        "antarctic-equalarea": ("world_ne_country_110m", "-180 -90 180 -55"),
        "webmercator": ("world_ne_country_110m", ""),
        "conus-albers": ("world_ne_country_110m", "-125 24 -66 50"),
        "alaska-albers": ("world_ne_country_110m", "170 50 -129 72"),
        "auto-utm": ("world_ne_country_110m", "149 -36 151 -33"),
        "australia-albers": ("au_ste_2021", ""), "australia-albers-gda94": ("au_ste_2021", ""),
        "canada-lambert": ("ca_province_2021", ""), "canada-equalarea": ("ca_province_2021", ""),
        "europe-laea": ("eu_nuts1_2021_10m", "-25 30 45 72"),
    }
    for name, (geography, region) in fixtures.items():
        result = invoke(dict(category="geography", action="preview", target=geography, projection=name, region=region,
                             center="-96 40" if name in {"orthographic", "regional-laea", "azimuthal-equidistant"} else "",
                             saving=str(output/(name+".png")), replace=True, graticule=True))
        assert result["visible_features"] > 0
        assert result["transformations"]["map"]["pipeline"]
        if name in {"canada-lambert", "canada-equalarea", "australia-albers", "australia-albers-gda94"}:
            assert not result.get("partly_visible_ids") and not result.get("hidden_ids")
        print("Rendered:", name, result["visible_features"], flush=True)
    for fmt in ("pdf", "svg", "png"):
        result = invoke(dict(action="compare", geography="world_ne_country_110m", choices="equalearth equalearth-pacific interrupted-goode orthographic arctic-equalarea antarctic-stereo",
                             center="-96 40", graticule=True, distortion=True, saving=str(output/("comparison."+fmt)), replace=True))
        assert len(result["comparisons"]) == 6
    rows = invoke(dict(action="recommend", geography="ca_province_2021", purpose="thematic"))["recommendations"]
    assert rows[0]["preset"] == "canada-equalarea" and rows[0]["available"]
    grid = grid_entry(ROOT, "uk_os_OSTN15_NTv2_OSGBtoETRS.tif")
    verify(home, grid)
    options = dict(action="preflight", crs="EPSG:27700", projection="equalearth", region="-6 50 2 58")
    baseline = invoke(options)
    selected = invoke(dict(options, grids=grid["name"]+"@"+grid["sha256"]))
    assert baseline["transformation"]["pipeline"] != selected["transformation"]["pipeline"]
    assert selected["grids"][0]["sha256"] == grid["sha256"]
    assert selected["transformation"]["accuracy_m"] == 1
    fixture = output / "british-grid.geojson"
    fixture.write_text(json.dumps(dict(type="FeatureCollection", features=[dict(type="Feature", properties=dict(code="london"),
        geometry=dict(type="Polygon", coordinates=[[[529000,179000],[529000,182000],[532000,182000],[532000,179000],[529000,179000]]]))])), encoding="utf-8")
    if (home/"packs/projection_grid_fixture/1/manifest.json").exists():
        invoke(dict(category="geography", action="remove", target="projection_grid_fixture"))
    invoke(dict(category="geography", action="import", name="projection_grid_fixture", using=str(fixture), idfield="code", crs="EPSG:27700"))
    mapped = invoke(dict(category="geography", action="preview", target="projection_grid_fixture", projection="equalearth",
                         grids=grid["name"]+"@"+grid["sha256"], saving=str(output/"selected-grid.svg"), replace=True))
    assert grid["name"] in mapped["transformations"]["map"]["pipeline"]
    polluted_env = dict(os.environ, PROJ_USER_WRITABLE_DIRECTORY=str(grid_path(home, grid).parent), PROJ_NETWORK="ON")
    isolated = invoke(options, env=polluted_env)
    assert isolated["transformation"]["pipeline"] == baseline["transformation"]["pipeline"]
    usage = invoke(dict(action="cache"))
    assert usage["bytes"] <= usage["limit_bytes"] == 64*1024*1024
    (output/"validation.json").write_text(json.dumps(dict(ok=True, runtime=command[0], checks=records, cache=usage), indent=2)+"\n", encoding="utf-8")
    print(f"PROJECTION_CHECK_PASSED: {len(fixtures)} presets; real projected sources; 3 comparison formats; recommendations; pinned grids; cache isolation", flush=True)


if __name__ == "__main__":
    main()
