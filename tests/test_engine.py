import csv
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))
from mapmaker_engine.render import render, read_bins


class RenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = tempfile.TemporaryDirectory()
        os.environ["MPLCONFIGDIR"] = cls.config.name

    @classmethod
    def tearDownClass(cls):
        cls.config.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="mapmaker test '")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        outer = [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]
        hole = [[4, 4], [4, 6], [6, 6], [6, 4], [4, 4]]
        pack = {"schema": 1, "features": [{"id": "01", "panel": "conus", "rings": [outer, hole],
                                         "bounds": [0, 0, 10, 10]}], "borders": {}, "state_borders": {}}
        payload = gzip.compress(json.dumps(pack).encode())
        (self.root / "geometry.json.gz").write_bytes(payload)
        (self.root / "ids.csv").write_text("mm_id\n01\n")
        manifest = {"schema": 1, "pack_id": "fixture", "revision": "1", "feature_count": 1,
                    "geography": "state", "vintage": "test",
                    "geometry_sha256": hashlib.sha256(payload).hexdigest(),
                    "ids_sha256": hashlib.sha256((self.root / "ids.csv").read_bytes()).hexdigest()}
        (self.root / "manifest.json").write_text(json.dumps(manifest))
        (self.root / "data.csv").write_text("mm_id,mm_bin\n01,1\n")
        self.request = {"schema": 1, "pack": str(self.root), "data": str(self.root / "data.csv"),
                        "output": str(self.root / "résult.png"), "nbins": 1, "labels": ["Value ≤ 1"],
                        "geography": "state", "vintage": "test", "nolegend": True,
                        "width": 4, "height": 4, "dpi": 100}

    def test_exports_and_polygon_hole(self):
        for fmt, signature in [("png", b"\x89PNG"), ("pdf", b"%PDF"), ("svg", b"<?xml")]:
            self.request["output"] = str(self.root / ("map." + fmt))
            result = render(self.request)
            self.assertEqual(result["matched"], 1)
            self.assertTrue(Path(result["output"]).read_bytes().startswith(signature))
        from PIL import Image
        with Image.open(self.root / "map.png") as img:
            self.assertEqual(img.getpixel((200, 200))[:3], (255, 255, 255))
            self.assertNotEqual(img.getpixel((110, 200))[:3], (255, 255, 255))
            self.assertEqual(json.loads(img.info["Description"])["bin_counts"], [1])

    def test_no_clobber_and_failed_replace(self):
        output = Path(self.request["output"])
        output.write_bytes(b"original")
        with self.assertRaises(FileExistsError):
            render(self.request)
        self.request.update(replace=True, palette="does-not-exist")
        with self.assertRaises(ValueError):
            render(self.request)
        self.assertEqual(output.read_bytes(), b"original")
        self.assertFalse(list(self.root.glob(".mapmaker-*")))

    def test_invalid_data(self):
        for rows in ["01,1\n01,1\n", "02,1\n", "01,0\n", "01,1.2\n", "01,.\n", "01,nan\n"]:
            with self.subTest(rows=rows):
                (self.root / "data.csv").write_text("mm_id,mm_bin\n" + rows)
                with self.assertRaises(ValueError):
                    render(self.request)

    def test_missing_is_distinct_from_absent(self):
        f = self.root / "data.csv"
        f.write_text("mm_id,mm_bin\n01,1\n02,\n")
        values = read_bins(f, {"01", "02", "03"}, 1)
        self.assertIsNone(values["02"])
        self.assertNotIn("03", values)

    def test_checksum_failure(self):
        (self.root / "ids.csv").write_text("mm_id\n02\n")
        with self.assertRaisesRegex(ValueError, "checksum"):
            render(self.request)

    def test_cli_status_and_literal_text(self):
        self.request.update(title='Literal $x$ and "quotes" / café', note="A\\B",
                            response=str(self.root / "response.json"), status=str(self.root / "status.txt"))
        path = self.root / "request.json"
        path.write_text(json.dumps(self.request))
        proc = subprocess.run([sys.executable, str(ROOT / "python/mapmaker_cli.py"), "--request", str(path)],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual((self.root / "status.txt").read_text(), "MAPMAKER_OK_V1\n")
        self.request["palette"] = "invalid"
        self.request["replace"] = True
        path.write_text(json.dumps(self.request))
        proc = subprocess.run([sys.executable, str(ROOT / "python/mapmaker_cli.py"), "--request", str(path)],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 1)
        self.assertTrue((self.root / "status.txt").read_text().startswith("MAPMAKER_ERROR_V1"))

    def test_simultaneous_no_clobber(self):
        processes = []
        for i in range(2):
            request = dict(self.request, response=str(self.root / f"result{i}.json"),
                           status=str(self.root / f"status{i}.txt"))
            path = self.root / f"request{i}.json"
            path.write_text(json.dumps(request))
            processes.append(subprocess.Popen([sys.executable, str(ROOT / "python/mapmaker_cli.py"),
                                               "--request", str(path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE))
        for p in processes:
            p.communicate(timeout=60)
        self.assertEqual(sorted(p.returncode for p in processes), [0, 1])
        self.assertTrue(Path(self.request["output"]).read_bytes().startswith(b"\x89PNG"))


class ProjectionTests(unittest.TestCase):
    def test_topology_reversal_and_projection_origin(self):
        sys.path.insert(0, str(ROOT / "tools"))
        from prepare_legacy import decode_arcs, join_ring, project
        arcs = decode_arcs({"transform": {"scale": [2, 3], "translate": [10, 20]},
                            "arcs": [[[0, 0], [1, 0], [0, 1]]]})
        self.assertEqual(arcs[0], [[10, 20], [12, 20], [12, 23]])
        self.assertEqual(join_ring([-1], arcs), [[12, 23], [12, 20], [10, 20], [12, 23]])
        self.assertEqual(project([-96, 37.5], "conus"), [0, 0])
        self.assertEqual(project([179, 60], "alaska"), project([-181, 60], "alaska"))


if __name__ == "__main__":
    unittest.main()
