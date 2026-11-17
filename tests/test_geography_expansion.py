import csv
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))
from mapmaker_engine import geography as geo
from mapmaker_engine.sources import compile_source, split_dateline
from mapmaker_engine.render import load_pack
from mapmaker_engine.geography_tables import inspect
from mapmaker_engine.library import run


class ExpansionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.entry = dict(pack_id="fixture", revision="1", geography="custom", vintage="test",
                          id_fields=["ID"], id_kind="string", id_width=0, format="geojson", layout="single")

    def source(self, features):
        path = self.root / "source.geojson"
        path.write_text(json.dumps(dict(type="FeatureCollection", features=features)), encoding="utf-8")
        return path

    def feature(self, ident="region-a", **properties):
        return dict(type="Feature", properties=dict(ID=ident, **properties), geometry=dict(type="Polygon",
            coordinates=[[[0, 0], [0, 4], [4, 4], [4, 0], [0, 0]], [[1, 1], [3, 1], [3, 3], [1, 3], [1, 1]]]))

    def test_geojson_attributes_long_ids_and_holes(self):
        ident = "region-" + "x"*80
        source = self.source([self.feature(ident, NAME="Québec", parent="01")])
        destination = self.root / "pack"
        compile_source(source, destination, self.entry)
        manifest, pack = load_pack(destination)
        self.assertEqual(pack["features"][0]["id"], ident)
        self.assertEqual(len(pack["features"][0]["rings"]), 2)
        with (destination / "attributes.csv").open(encoding="utf-8", newline="") as stream:
            row = next(csv.DictReader(stream))
        self.assertEqual(row["NAME"], "Québec")
        (destination / "attributes.csv").write_text("bad")
        with self.assertRaisesRegex(ValueError, "attributes"):
            load_pack(destination)

    def test_dateline_split_retains_area_and_hole(self):
        from shapely.geometry import Polygon
        geometry = Polygon([(170, -10), (170, 10), (-170, 10), (-170, -10), (170, -10)],
                           [[(175, -5), (-175, -5), (-175, 5), (175, 5), (175, -5)]])
        result = split_dateline(geometry)
        self.assertTrue(result.is_valid)
        self.assertAlmostEqual(result.area, 300)
        self.assertEqual(len(result.geoms), 2)
        self.assertTrue(all(p.bounds[2]-p.bounds[0] <= 10 for p in result.geoms))

    def test_polar_seam_preserved(self):
        from shapely.geometry import Polygon
        result = split_dateline(Polygon([(-180,-90),(-180,-70),(0,-80),(180,-70),(180,-90),(-180,-90)]))
        self.assertAlmostEqual(result.area, 5400)

    def test_geojson_crs_and_transfer_limit(self):
        source = self.source([self.feature()])
        data = json.loads(source.read_text())
        data["crs"] = dict(type="name", properties=dict(name="EPSG:3857"))
        source.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, "explicit"):
            compile_source(source, self.root/"pack", self.entry)
        data.pop("crs")
        data["exceededTransferLimit"] = True
        source.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, "incomplete"):
            compile_source(source, self.root/"pack", self.entry)

    def test_nonspatial_codes_explicit_and_filters(self):
        missing = dict(type="Feature", properties=dict(ID="outside", level="1"), geometry=None)
        source = self.source([self.feature(level="1"), self.feature("other", level="2"), missing])
        manifest = compile_source(source, self.root/"pack", dict(self.entry, filter={"level":"1"}, skip_null_geometry=True,
                                                              source_feature_count=3, feature_count=1))
        self.assertEqual(manifest["nonspatial_ids"], ["outside"])
        self.assertEqual(manifest["feature_count"], 1)

    def test_inspection_no_clobber_and_diagnostics(self):
        path = self.root/"pack"
        manifest = compile_source(self.source([self.feature("01001")]), path, dict(self.entry, id_kind="digits", id_width=5))
        output = self.root/"ids.csv"
        inspect(dict(saving=str(output)), path, manifest, "ids")
        with self.assertRaises(FileExistsError):
            inspect(dict(saving=str(output)), path, manifest, "ids")
        source = self.root/"input.csv"
        source.write_text("mm_id\n1001\n01001\n01001\nBAD\n")
        result, _ = inspect(dict(data=str(source), saving=str(self.root/"diagnostics.csv")), path, manifest, "diagnose")
        self.assertEqual((result["matched"], result["unmatched"], result["duplicates"]), (2,2,1))
        with Path(result["path"]).open(newline="") as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(rows[0]["suggested_id"], "01001")
        self.assertEqual(source.read_text(), "mm_id\n1001\n01001\n01001\nBAD\n")

    def test_revision_protects_partition_membership_and_provider_path(self):
        for key, value in [("filter", {"STATEFP":"06"}), ("membership_sha256", "a"*64), ("source_member", "other.shp")]:
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "immutable"):
                geo.check_revision(self.entry, dict(self.entry, **{key:value}))
        geo.check_url("https://raw.githubusercontent.com/wmgeolab/geoBoundaries/123abc/releaseData/a.geojson")
        with self.assertRaises(ValueError):
            geo.check_url("https://raw.githubusercontent.com/unreviewed/repo/main/a.geojson")
        with self.assertRaises(ValueError):
            geo.check_url("https://raw.githubusercontent.com/wmgeolab/geoBoundaries/%2e%2e/other/a.geojson")

    def test_catalog_pagination_and_new_families(self):
        result = run(dict(schema=1, root=str(ROOT), datadir=str(self.root), category="geography", action="browse", limit="7", offset="2"))
        self.assertEqual(result["shown"], 7)
        self.assertGreater(result["count"], 100)
        selected = run(dict(schema=1, root=str(ROOT), datadir=str(self.root), category="geography", action="browse", state="06", level="tract", all=True))
        self.assertTrue(selected["entries"])
        self.assertTrue(all(e["pack_id"].startswith("us_06_") and e["geography"] == "tract" for e in selected["entries"]))

    def test_county_dissolve_conserves_area_and_rejects_wrong_vintage(self):
        from mapmaker_engine.derived import dissolve
        from shapely.geometry import Polygon
        home = self.root / "library"
        county_entry = dict(self.entry, pack_id="counties", geography="county", id_kind="digits", id_width=5)
        first = self.feature("09110")
        first["geometry"]["coordinates"] = [[[0,0],[0,1],[1,1],[1,0],[0,0]]]
        second = self.feature("09120")
        second["geometry"]["coordinates"] = [[[1,0],[1,1],[2,1],[2,0],[1,0]]]
        compile_source(self.source([first,second]), home/"packs/counties/1", county_entry)
        (self.root/"catalog/membership").mkdir(parents=True)
        (self.root/"catalog/geographies.json").write_text(json.dumps(dict(schema=1,updated="test",packs=[county_entry])))
        table = self.root/"catalog/membership/zones.csv"
        table.write_text("county_id,mm_id,zone_name\n09110,1,Zone\n09120,1,Zone\n")
        entry = dict(self.entry,pack_id="zones",geography="cz",membership_sha256=hashlib.sha256(table.read_bytes()).hexdigest(),
                     recipe=dict(kind="county_dissolve",base_pack="counties",base_revision="1"))
        output = self.root/"derived"
        dissolve(self.root,home,output,entry)
        manifest, pack = load_pack(output)
        self.assertEqual(manifest["feature_count"],1)
        self.assertAlmostEqual(Polygon(pack["features"][0]["rings"][0]).area,2)
        self.assertEqual(len(pack["features"][0]["rings"]),1)
        table.write_text("county_id,mm_id,zone_name\n09001,1,Old county\n")
        entry["membership_sha256"] = hashlib.sha256(table.read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError,"missing from boundary vintage"):
            dissolve(self.root,home,self.root/"wrong",entry)

    def test_unknown_spherical_datum_preserves_source_projection(self):
        from pyproj import CRS
        from mapmaker_engine.projections import project_pack
        manifest = dict(schema=2,source_crs=CRS("+proj=laea +lon_0=-100 +lat_0=45 +R=6370997 +units=m +type=crs").to_wkt(),
                        geography="cz",layout="single",recommended_projection="source")
        ring = [[0,0],[0,100],[100,100],[100,0],[0,0]]
        pack = dict(features=[dict(id="1",panel="map",rings=[ring])])
        projected, meta = project_pack(manifest,pack,{}, {"1":1})
        self.assertEqual(projected["features"][0]["rings"][0],ring)
        with self.assertRaisesRegex(ValueError,"Cannot transform"):
            project_pack(manifest,pack,dict(projection="equalearth"),{"1":1})

    def test_nonhierarchical_us_ids_do_not_select_state_panels(self):
        from unittest.mock import patch
        from pyproj import Transformer
        california = self.feature("02001")
        california["geometry"]["coordinates"] = [[[-122,35],[-122,36],[-121,36],[-121,35],[-122,35]]]
        alaska = self.feature("06001")
        alaska["geometry"]["coordinates"] = [[[-150,60],[-150,61],[-149,61],[-149,60],[-150,60]]]
        with patch("pyproj.Transformer.from_crs", wraps=Transformer.from_crs) as transformer:
            compile_source(self.source([california,alaska]),self.root/"pack",
                           dict(self.entry,country="US",layout="us-insets"))
            self.assertEqual(transformer.call_count,1)
        _, pack = load_pack(self.root/"pack")
        self.assertEqual({f["id"]:f["panel"] for f in pack["features"]},{"02001":"conus","06001":"alaska"})


if __name__ == "__main__":
    unittest.main()
