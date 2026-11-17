import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))
from mapmaker_engine import geography as geo
from mapmaker_engine.library import run, safe_text
from mapmaker_engine.projections import project_pack
from mapmaker_engine.render import load_pack, render


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / "library"
        import shapefile
        from pyproj import CRS
        base = self.root / "fixture"
        with shapefile.Writer(str(base)) as writer:
            writer.field("GEOID", "C", size=5)
            # Clockwise exterior, counterclockwise interior (shapefile convention).
            writer.poly([[[-122, 37], [-122, 39], [-120, 39], [-120, 37], [-122, 37]],
                         [[-121.6, 37.5], [-120.5, 37.5], [-120.5, 38.5], [-121.6, 38.5], [-121.6, 37.5]]])
            writer.record("06001")
        base.with_suffix(".prj").write_text(CRS("EPSG:4269").to_wkt())
        self.archive = self.root / "source.zip"
        with zipfile.ZipFile(self.archive, "w") as archive:
            for path in self.root.glob("fixture.*"):
                archive.write(path, path.name)
        self.entry = dict(pack_id="us_fixture_2020", revision="1", geography="county", vintage="2020",
                          country="US", layout="us-insets", id_kind="digits", id_fields=["GEOID"], id_width=5,
                          source_feature_count=1, source_url="https://www2.census.gov/fixture.zip",
                          source_sha256=hashlib.sha256(self.archive.read_bytes()).hexdigest())
        (self.root / "catalog").mkdir()
        (self.root / "catalog/geographies.json").write_text(json.dumps(dict(schema=1, updated="test", packs=[self.entry])))

    def install(self):
        return geo.install(self.root, self.home, self.entry, self.archive)

    def test_install_resolve_offline_and_remove(self):
        with patch("urllib.request.OpenerDirector.open", side_effect=AssertionError("network")):
            path = self.install()
            self.assertEqual(self.install(), path)
            resolved, manifest = geo.resolve(self.root, self.home, self.entry["pack_id"])
            self.assertEqual(resolved, path)
            self.assertEqual(manifest["feature_count"], 1)
            result = run(dict(schema=1, root=str(self.root), datadir=str(self.home), category="geography",
                              action="browse", installed=True, level="county"))
            self.assertEqual(len(result["entries"]), 1)
            self.assertTrue(result["entries"][0]["installed"])
            geo.remove(self.home, self.entry["pack_id"], "1")
            self.assertFalse(path.exists())

    def test_hash_failure_leaves_no_install(self):
        self.entry["source_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "checksum"):
            self.install()
        self.assertIsNone(geo.locate(self.root, self.home, self.entry["pack_id"])[0])
        self.assertFalse(list(self.home.glob("packs/*/.install-*")))

    def test_download_rejected_before_commit(self):
        with patch("mapmaker_engine.geography.download", side_effect=OSError("connection interrupted")):
            with self.assertRaisesRegex(OSError, "interrupted"):
                geo.install(self.root, self.home, self.entry)
        self.assertIsNone(geo.locate(self.root, self.home, self.entry["pack_id"])[0])

    def test_revision_pinning_and_identity(self):
        self.install()
        with self.assertRaisesRegex(ValueError, "missing"):
            geo.resolve(self.root, self.home, self.entry["pack_id"], "2")
        with self.assertRaisesRegex(ValueError, "vintage"):
            geo.resolve(self.root, self.home, self.entry["pack_id"], "1", "2010")
        second = dict(self.entry, revision="2")
        geo.install(self.root, self.home, second, self.archive)
        geo.remove(self.home, self.entry["pack_id"], "1")
        self.assertIsNotNone(geo.resolve(self.root, self.home, self.entry["pack_id"], "2"))

    def test_invalid_paths_and_source_hosts(self):
        for value in ("../outside", "a/b", "C:\\outside", "..", "x\n"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                geo.remove(self.home, value, "1")
        for url in ("http://www2.census.gov/a", "https://example.com/a", "https://www2.census.gov@evil.test/a"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                geo.check_url(url)
        with zipfile.ZipFile(self.root / "unsafe.zip", "w") as archive:
            archive.writestr("../fixture.shp", "bad")
        with self.assertRaisesRegex(ValueError, "Unsafe"):
            geo.shapefile_parts(self.root / "unsafe.zip")
        self.assertNotIn("{", safe_text('{stata clear:click} $secret `macro'))

    def test_ids_checked_against_geometry(self):
        path = self.install()
        (path / "ids.csv").write_text("mm_id\n06002\n")
        manifest = json.loads((path / "manifest.json").read_text())
        manifest["ids_sha256"] = hashlib.sha256((path / "ids.csv").read_bytes()).hexdigest()
        (path / "manifest.json").write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, "features"):
            load_pack(path)

    def test_projection_and_render_preserve_hole(self):
        path = self.install()
        manifest, pack = load_pack(path)
        projected, metadata = project_pack(manifest, pack, dict(projection="EPSG:5070", zoom=True), {"06001": 1})
        self.assertEqual(projected["features"][0]["panel"], "map")
        self.assertEqual(len(projected["features"][0]["rings"]), 2)
        self.assertIn("5070", metadata["target_crs"]["map"])
        (self.root / "data.csv").write_text("mm_id,mm_bin\n06001,1\n")
        request = dict(schema=1, pack=str(path), data=str(self.root / "data.csv"), geography="county", vintage="2020",
                       nbins=1, labels=["Test"], nolegend=True, width=4, height=4, dpi=100, projection="EPSG:5070")
        for fmt in ("png", "svg", "pdf"):
            output = self.root / ("map." + fmt)
            result = render(dict(request, output=str(output)))
            self.assertTrue(output.exists())
            self.assertEqual(result["projection"], "EPSG:5070")
        from PIL import Image
        with Image.open(self.root / "map.png") as image:
            self.assertEqual(image.getpixel((200, 200))[:3], (255, 255, 255))

    def test_legacy_projection_rejected(self):
        with self.assertRaisesRegex(ValueError, "fixed projection"):
            project_pack(dict(schema=1), {}, dict(projection="EPSG:5070"), {})

    def test_missing_crs_rejected(self):
        (self.root / "fixture.prj").unlink()
        with self.assertRaisesRegex(ValueError, "Missing source CRS"):
            geo.compile_shapefile(self.root / "fixture.shp", self.root / "out", self.entry)

    def test_custom_import_and_string_ids(self):
        result = run(dict(schema=1, root=str(self.root), datadir=str(self.home), category="geography", action="import",
                          using=str(self.archive), name="custom", idfield="GEOID"))
        path, manifest = geo.resolve(self.root, self.home, "custom")
        self.assertEqual(manifest["id_kind"], "string")
        self.assertEqual(manifest["layout"], "single")

    def test_custom_null_numeric_id_rejected(self):
        import shapefile
        base = self.root / "missing"
        with shapefile.Writer(str(base)) as writer:
            writer.field("ID", "N")
            writer.poly([[[0, 0], [0, 1], [1, 1], [1, 0], [0, 0]]])
            writer.record(None)
        with self.assertRaisesRegex(ValueError, "Missing geographic ID"):
            geo.compile_shapefile(base.with_suffix(".shp"), self.root / "out",
                                  dict(self.entry, id_kind="string", id_fields=["ID"]), "EPSG:4326")

    def test_bundled_catalog_checksums_and_defaults(self):
        catalog = geo.read_catalog(ROOT)
        self.assertEqual({e["geography"] for e in catalog["packs"] if e.get("default")}, {"county", "state", "cz"})
        self.assertTrue({111, 113, 116, 118, 119}.issubset({e.get("congress") for e in catalog["packs"]}))

    def test_catalog_refresh_preserves_revisions_and_failure_keeps_cache(self):
        new = dict(self.entry, revision="2", source_sha256="f" * 64)
        source = self.root / "update.json"
        source.write_text(json.dumps(dict(schema=1, updated="test2", packs=[new])))
        geo.refresh_catalog(self.root, self.home, source)
        self.assertEqual(len(geo.read_catalog(self.root, self.home)["packs"]), 2)
        cached = (self.home / "catalog.json").read_bytes()
        new["revision"] = "1"
        source.write_text(json.dumps(dict(schema=1, updated="test3", packs=[new])))
        with self.assertRaisesRegex(ValueError, "immutable"):
            geo.refresh_catalog(self.root, self.home, source)
        self.assertEqual((self.home / "catalog.json").read_bytes(), cached)

        with patch("urllib.request.urlopen", side_effect=OSError("offline")):
            with self.assertRaisesRegex(ValueError, "still usable"):
                geo.refresh_catalog(self.root, self.home)
        self.assertEqual((self.home / "catalog.json").read_bytes(), cached)

    def test_catalog_rejects_changed_id_rules(self):
        with self.assertRaisesRegex(ValueError, "immutable"):
            geo.check_revision(self.entry, dict(self.entry, id_width=6))


if __name__ == "__main__":
    unittest.main()
