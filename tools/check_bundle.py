"""Smoke-test a built runtime without invoking source Python inside that runtime.

Run after build_bundle.py and build_catalog.py. Output stays in tests/output.
"""
import argparse
import json
from pathlib import Path
import subprocess
import shutil
import tempfile

ROOT = Path(__file__).resolve().parents[1]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    args = parser.parse_args()
    bundle = args.bundle.resolve()
    binary = bundle / "runtime/mapmaker-render/mapmaker-render"
    if binary.with_suffix(".exe").exists():
        binary = binary.with_suffix(".exe")
    output = ROOT / "tests/output/bundle"
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="library-", dir=output) as directory:
        home = Path(directory)

        def invoke(request):
            request = dict(schema=1, root=str(bundle), datadir=str(home), **request,
                           response=str(home / "response.json"), status=str(home / "status.txt"))
            path = home / "request.json"
            path.write_text(json.dumps(request), encoding="utf-8")
            subprocess.run([str(binary), "--request", str(path)], check=True)
            return json.loads((home / "response.json").read_text(encoding="utf-8"))

        result = invoke(dict(operation="library", category="geography", action="browse", installed=True))
        assert {e["geography"] for e in result["entries"]} >= {"county", "state", "cz"}
        result = invoke(dict(operation="library", category="projection", action="search", target="Albers"))
        assert any(e["code"] == "EPSG:5070" for e in result["entries"])
        invoke(dict(operation="library", category="geography", action="import", name="bundle_test",
                    using=str(ROOT / ".cache/catalog-sources/cb_2020_us_state_500k.zip"), idfield="GEOID"))
        (home / "data.csv").write_text("mm_id,mm_bin\n06,1\n")
        resolved = invoke(dict(operation="library", category="geography", action="resolve", target="bundle_test"))
        for fmt in ("png", "pdf", "svg"):
            result = invoke(dict(pack=resolved["path"], geography="custom", vintage="custom", data=str(home / "data.csv"),
                                 output=str(output / ("california." + fmt)), replace=True,
                                 nbins=1, labels=["California"], zoom=True, projection="EPSG:5070"))
            assert result["matched"] == 1 and result["projection"] == "EPSG:5070"
        # Exercise Shapely/GEOS and GeoJSON inside the frozen runtime.
        source = home / "dateline.geojson"
        source.write_text(json.dumps(dict(type="FeatureCollection", features=[dict(type="Feature",
            properties=dict(code="region-"+"x"*80, name="Québec"), geometry=dict(type="Polygon",
            coordinates=[[[170,-10],[170,10],[-170,10],[-170,-10],[170,-10]]]))])), encoding="utf-8")
        invoke(dict(operation="library", category="geography", action="import", name="dateline", using=str(source), idfield="code"))
        invoke(dict(operation="library", category="geography", action="preview", target="dateline",
                    saving=str(output/"dateline.pdf"), replace=True))
        table = invoke(dict(operation="library", category="geography", action="attributes", target="dateline"))
        assert "Québec" in Path(table["path"]).read_text(encoding="utf-8")
        # Only boundary data are copied; the child process executes no source Python.
        county = ROOT/".cache/expanded-integration/library/packs/us_county_2024_500k/1"
        if county.exists():
            shutil.copytree(county, home/"packs/us_county_2024_500k/1")
            invoke(dict(operation="library", category="geography", action="install", target="us_ers_cz_2020"))
            verified = invoke(dict(operation="library", category="geography", action="verify", target="us_ers_cz_2020"))
            assert verified["manifest"]["feature_count"] == 598
            assert verified["manifest"]["derived_from"]["pack_id"] == "us_county_2024_500k"
    print("BUNDLE_CHECK_PASSED: defaults, CRS search, shapefile/GeoJSON import, seam splitting, tables, CZ dissolve, PNG/PDF/SVG")
