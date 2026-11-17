import json
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from pyproj import CRS, Transformer
from shapely.geometry import Polygon, Point, box
from shapely.geometry.polygon import orient
from shapely import union_all
from mapmaker_engine.projections import project_pack, resolve, PRESETS
from mapmaker_engine.projection_geometry import groups
from mapmaker_engine.projection_workflows import preflight, recommend, inset_settings
from mapmaker_engine import projection_cache as cache
from mapmaker_engine import projection_resources as grids


def rings(polygon):
    polygon = orient(polygon, sign=-1)
    return [list(polygon.exterior.coords), *[list(r.coords) for r in polygon.interiors]]


def shape(pack):
    return union_all([Polygon(g[0], g[1:]) for f in pack["features"] for g in groups(f["rings"])])


class ProjectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.manifest = dict(schema=2, country="US", geography="custom", source_crs="EPSG:4326", layout="single")
        self.request = dict(root=str(ROOT), datadir=str(self.home))

    def project(self, polygon, name, source="EPSG:4326", **options):
        pack = dict(schema=2, features=[dict(id="a", panel="conus", rings=rings(polygon))])
        return project_pack(dict(self.manifest, source_crs=source), pack, dict(self.request, projection=name, **options), {})

    def test_named_presets_and_datums(self):
        for name in PRESETS:
            crs, _, _ = resolve(name, [-102, 35, -100, 37])
            self.assertTrue(crs.is_projected, name)
        self.assertEqual(resolve("australia-albers", [110,-45,155,-10])[0].to_epsg(), 9473)
        self.assertEqual(resolve("australia-albers-gda94", [110,-45,155,-10])[0].to_epsg(), 3577)
        self.assertEqual(resolve("canada-lambert", [-140,40,-50,80])[0].to_epsg(), 3347)

    def test_utm_hemisphere_zone_and_exceptions(self):
        self.assertEqual(resolve("auto-utm", [149,-35,151,-33])[0].to_epsg(), 32756)
        self.assertEqual(resolve("auto-utm", [5,59,7,61])[0].to_epsg(), 32632)
        self.assertEqual(resolve("auto-utm", [12,75,14,77])[0].to_epsg(), 32633)
        self.assertTrue(resolve("auto-utm", [-120,20,-90,50])[2])
        with self.assertRaisesRegex(ValueError, "polar"):
            resolve("auto-utm", [0,80,5,89])

    def test_extent_warning_and_resolved_center(self):
        self.assertTrue(resolve("conus-albers", [150,30,-120,70])[2])
        _, spec, _ = resolve("regional-laea", [170,-10,-170,20])
        self.assertEqual(spec["longitude"], -180)
        self.assertEqual(spec["latitude"], 5)

    def test_pacific_seam_holes_conserve_equal_area(self):
        polygon = Polygon([(-40,-20),(-40,20),(-20,20),(-20,-20),(-40,-20)],
                          [[(-35,-10),(-25,-10),(-25,10),(-35,10),(-35,-10)]])
        normal, _ = self.project(polygon, "equalearth")
        pacific, _ = self.project(polygon, "equalearth-pacific")
        a, b = shape(normal), shape(pacific)
        self.assertTrue(b.is_valid)
        self.assertAlmostEqual(a.area/b.area, 1, places=5)
        self.assertEqual(len(list(groups(pacific["features"][0]["rings"]))), 2)

    def test_projected_source_crosses_dateline(self):
        polygon = box(170, -10, 190, 10)
        forward = Transformer.from_crs(4326, 3857, always_xy=True, force_over=True)
        projected = Polygon([forward.transform(x,y) for x,y in polygon.exterior.coords])
        actual, _ = self.project(projected, "equalearth", source="EPSG:3857")
        expected, _ = self.project(polygon, "equalearth")
        self.assertTrue(shape(actual).is_valid)
        self.assertAlmostEqual(shape(actual).area/shape(expected).area, 1, delta=1e-4)
        self.assertEqual(len(list(groups(actual["features"][0]["rings"]))), 2)

    def test_horizon_clip_preserves_intersecting_hole(self):
        outer = box(70,-20,110,20)
        hole = box(80,-10,100,10)
        full, _ = self.project(outer, "orthographic", center="0 0")
        void, _ = self.project(hole, "orthographic", center="0 0")
        cut, metadata = self.project(Polygon(outer.exterior.coords, [hole.exterior.coords]), "orthographic", center="0 0")
        self.assertTrue(shape(cut).is_valid)
        self.assertAlmostEqual(shape(cut).area/(shape(full).area-shape(void).area), 1, places=5)
        self.assertEqual(metadata["partly_visible_ids"], ["a"])
        self.assertLessEqual(shape(cut).bounds[2], 6378137.01)

    def test_hidden_hemisphere_is_not_drawn(self):
        with self.assertRaisesRegex(ValueError, "No geometry is visible"):
            self.project(box(120,-20,150,20), "orthographic", center="0 0")

    def test_center_enclosing_hemisphere_has_no_pinhole(self):
        projected, _ = self.project(box(-170,-80,170,80), "orthographic", center="0 0")
        self.assertTrue(shape(projected).covers(Point(0,0)))

    def test_antipodal_cap_is_clipped_without_filling_world(self):
        projected, meta = self.project(box(170,-10,190,10), "regional-laea", center="0 0")
        self.assertTrue(shape(projected).is_valid)
        self.assertFalse(shape(projected).covers(Point(0,0)))
        self.assertLess(shape(projected).area, 6e12)
        self.assertIn("a", meta["partly_visible_ids"])

    def test_projected_pole_enclosing_polygon_and_hole(self):
        # A perfectly valid planar polygon encloses the north pole. Its inverse
        # projection winds around longitude; neither explicit seam nor pole
        # vertices occur in this source file.
        outer = Point(0,0).buffer(500000, quad_segs=90)
        hole = Point(0,0).buffer(100000, quad_segs=90)
        full, _ = self.project(outer, "arctic-equalarea", "EPSG:3413")
        donut, _ = self.project(outer.difference(hole), "arctic-equalarea", "EPSG:3413")
        self.assertTrue(shape(donut).is_valid)
        self.assertTrue(shape(full).covers(Point(0,0)))
        self.assertFalse(shape(donut).covers(Point(0,0)))
        self.assertGreater(shape(donut).area/shape(full).area, .94)
        self.assertLess(shape(donut).area/shape(full).area, .97)

    def test_south_pole_explicit_seam(self):
        polygon = Polygon([(-180,-90),(-180,-75),(0,-75),(180,-75),(180,-90),(-180,-90)])
        result, _ = self.project(polygon, "antarctic-equalarea")
        self.assertTrue(shape(result).covers(Point(0,0)))
        self.assertGreater(shape(result).area, 8e12)

    def test_interrupted_lobes_preserve_hole_and_area(self):
        outer = box(-50,10,-30,40)
        hole = box(-45,15,-35,30)
        polygon = Polygon(outer.exterior.coords, [hole.exterior.coords])
        cut, _ = self.project(polygon, "interrupted-goode")
        self.assertEqual(len(list(groups(cut["features"][0]["rings"]))), 2)
        a, _ = self.project(outer, "interrupted-goode")
        b, _ = self.project(hole, "interrupted-goode")
        self.assertTrue(shape(cut).is_valid)
        self.assertAlmostEqual(shape(cut).area/(shape(a).area-shape(b).area), 1, places=5)
        # No segment should bridge the gap between lobes.
        self.assertLess(max(math.dist(a,b) for r in cut['features'][0]['rings'] for a,b in zip(r,r[1:])), 100000)

    def test_azimuthal_distances_from_origin(self):
        crs, spec, _ = resolve("azimuthal-equidistant", [-10,-10,10,10], "12 30")
        transform = Transformer.from_crs(crs.geodetic_crs, crs, always_xy=True)
        x,y = transform.transform(30,45)
        _,_,distance = crs.get_geod().inv(12,30,30,45)
        self.assertAlmostEqual(math.hypot(x,y), distance, places=6)

    def test_numeric_region_and_exclusions(self):
        projected, meta = self.project(box(-30,-30,30,30), "equalearth", region="-10 -10 10 10")
        expected, _ = self.project(box(-10,-10,10,10), "equalearth")
        self.assertAlmostEqual(shape(projected).area/shape(expected).area, 1, places=6)
        self.assertIn("a", meta["partly_visible_ids"])
        pack = dict(schema=2, features=[dict(id="a", panel="conus", rings=rings(box(-100,35,-99,36))),
                                     dict(id="b", panel="alaska", rings=rings(box(-150,60,-149,61)))])
        result, meta = project_pack(self.manifest, pack, dict(self.request, layout="conus"), {})
        self.assertEqual(meta["excluded_ids"], ["b"])
        self.assertEqual(len(result["features"]), 1)

    def test_subprecision_component_is_not_reported_as_domain_clipping(self):
        pack = dict(schema=2, features=[dict(id="a", panel="conus", rings=rings(box(-10,0,10,20))+rings(box(0,0,1e-10,1e-10)))])
        _, metadata = project_pack(self.manifest, pack, dict(self.request, projection="equalearth"), {})
        self.assertFalse(metadata.get("partly_visible_ids"))

    def test_inset_positions_and_captions(self):
        rectangles, captions = inset_settings('alaska .03 .05 .3 .2 Alaska (scaled); hawaii .4 .05 .2 .15 Hawaii', {"alaska","hawaii"})
        self.assertEqual(captions["alaska"], "Alaska (scaled)")
        self.assertEqual(rectangles["hawaii"][0], .4)
        with self.assertRaises(ValueError):
            inset_settings("alaska .9 .1 .2 .2", {"alaska"})

    def test_legacy_conus_preserves_fixed_geometry(self):
        a = dict(id="01", panel="conus", rings=rings(box(0,0,1,1)))
        b = dict(id="02", panel="alaska", rings=rings(box(2,2,3,3)))
        result, metadata = project_pack(dict(schema=1), dict(features=[a,b]), dict(self.request, layout="conus"), {})
        self.assertEqual(result["features"], [a])
        self.assertEqual(metadata["projection"], "legacy")
        self.assertEqual(metadata["excluded_ids"], ["02"])
        self.assertTrue(metadata["warnings"])

    def test_preflight_names_size_license_and_pinned_command(self):
        result = preflight(dict(self.request, action="preflight", crs="EPSG:27700", projection="equalearth", region="-6 50 2 58"), self.home)
        self.assertTrue(result["available"])
        row = next(r for r in result["missing_grids"] if r["name"] == "uk_os_OSTN15_NTv2_OSGBtoETRS.tif")
        self.assertEqual(row["bytes"], 3035814)
        self.assertEqual(row["license"], "BSD-2-Clause")
        self.assertIn(row["sha256"], row["install_command"])
        self.assertIn("pipeline", result["transformation"])

    def test_preflight_rejects_unknown_datum_without_guessing(self):
        result = preflight(dict(self.request, action="preflight", crs="+proj=laea +R=6371000 +type=crs", projection="equalearth"), self.home)
        self.assertFalse(result["available"])

    def test_grids_validate_names_hashes_and_selection(self):
        for name in ("../proj.db", "https://example.com/a.tif", "a.tif@bad"):
            with self.assertRaises(ValueError):
                grids.grid_entry(ROOT, name)
        entry = grids.grid_entry(ROOT, "uk_os_OSTN15_NTv2_OSGBtoETRS.tif")
        path = grids.grid_path(self.home, entry)
        path.parent.mkdir(parents=True)
        path.write_bytes(b"bad")
        with self.assertRaisesRegex(ValueError, "checksum"):
            grids.verify(self.home, entry)
        with grids.resources(ROOT, self.home) as metadata:
            self.assertEqual(metadata["grids"], [])
        with self.assertRaisesRegex(ValueError, "checksum"):
            with grids.resources(ROOT, self.home, entry["name"]):
                pass

    def test_cache_keys_limits_and_no_values(self):
        polygon = box(-100,35,-99,36)
        first, meta = self.project(polygon, "equalearth")
        second, same = self.project(polygon, "equalearth")
        self.assertEqual(same["projection_cache"], "hit")
        self.assertEqual(json.loads(json.dumps(first)), second)
        _, changed = self.project(polygon, "equalearth-pacific")
        self.assertEqual(changed["projection_cache"], "miss")
        self.assertEqual(cache.manage(self.home)["files"], 2)
        cache.manage(self.home, "limit", 0)
        self.assertEqual(cache.manage(self.home)["bytes"], 0)
        _, disabled = self.project(polygon, "equalearth")
        self.assertEqual(disabled["projection_cache"], "bypass")

    def test_offline_projection_and_overlays(self):
        with patch("urllib.request.OpenerDirector.open", side_effect=AssertionError("network")):
            result, meta = self.project(box(-120,30,-70,60), "orthographic", center="-96 40", graticule=True, distortion=True)
        self.assertTrue(result["graticules"]["map"])
        self.assertTrue(result["indicatrices"]["map"])
        self.assertIn("proj_database_sha256", meta)


if __name__ == "__main__":
    unittest.main()
