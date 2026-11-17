import csv
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"python"))
from mapmaker_engine.sources import compile_source
from mapmaker_engine.render import load_pack
from mapmaker_engine.figures import render, records, colors
from mapmaker_engine.figure_config import validate_scale, style
from mapmaker_engine.figure_layouts import anchor, geometry, dorling, tiled
from mapmaker_engine.figure_layers import flow_layer, selected_flows
from mapmaker_engine import crosswalks, offline


class FeatureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.pack = self.home/"packs/fixture/1"
        source = self.home/"source.geojson"
        features = [dict(type="Feature",properties=dict(ID=k),geometry=dict(type="Polygon",coordinates=[
            [[x,0],[x,2],[x+2,2],[x+2,0],[x,0]]])) for k,x in [("a",0),("b",3),("c",6)]]
        source.write_text(json.dumps(dict(type="FeatureCollection",features=features)),encoding="utf-8")
        compile_source(source,self.pack,dict(pack_id="fixture",revision="1",geography="custom",vintage="test",id_fields=["ID"],id_kind="string",id_width=0,format="geojson",layout="single"))
        self.scale = dict(mode="custom",cutoffs=[1],labels=["Low","High"],interval="upper-inclusive")
        self.data = self.home/"data.csv"
        self.data.write_text("mm_id,mm_panel,mm_bin\na,2010,1\nb,2010,2\na,2020,2\nb,2020,.\n",encoding="utf-8")
        self.request = dict(schema=2,root=str(ROOT),datadir=str(self.home),pack=str(self.pack),data=str(self.data),
                            geography="custom",vintage="test",panels=[dict(key=k,scale=self.scale) for k in ("2010","2020","2030")],
                            scale="shared",output=str(self.home/"map.png"),projection="equalearth",replace=True,dpi=80)

    def test_shared_panels_preserve_absent_missing_and_colors(self):
        result = render(self.request)
        self.assertEqual([p["matched"] for p in result["panels"]],[2,2,0])
        self.assertEqual([p["missing"] for p in result["panels"]],[0,1,0])
        self.assertEqual([p["absent"] for p in result["panels"]],[0,0,2])
        self.assertEqual(result["panels"][0]["colors"],result["panels"][1]["colors"])
        self.assertTrue(all(p["excluded"]==1 for p in result["panels"]))

    def test_typed_rows_reject_duplicates_invalid_bins_and_continuous_missing(self):
        panels={p["key"]:p for p in self.request["panels"]}
        for text in ("a,2010,1\na,2010,2", "a,2010,3", "unknown,2010,1"):
            self.data.write_text("mm_id,mm_panel,mm_bin\n"+text+"\n",encoding="utf-8")
            with self.assertRaises(ValueError): records(self.request,{"a","b"},panels)
        self.data.write_text("mm_id,mm_panel,mm_bin,mm_value\na,2010,1,.\n",encoding="utf-8")
        panels["2010"]["scale"]=dict(mode="continuous",limits=[0,1],labels=["Value"])
        with self.assertRaisesRegex(ValueError,"missingness"): records(self.request,{"a"},panels)

    def test_scales_and_styles_reject_semantic_overrides(self):
        with self.assertRaises(ValueError): validate_scale(dict(mode="continuous",limits=[1,1],labels=["Value"]))
        with self.assertRaises(ValueError): validate_scale(dict(mode="categorical",category_keys=["a","a"],labels=["a","b"]))
        path=self.home/"bad-style.json"
        path.write_text(json.dumps(dict(schema="mapmaker-style-1",settings=dict(projection="mercator"))),encoding="utf-8")
        with self.assertRaisesRegex(ValueError,"appearance"): style(dict(style=str(path)))

    def test_grayscale_theme_has_no_chromatic_classes(self):
        settings=style(dict(style="grayscale"))
        for mode in ("diverging","categorical","bivariate"):
            scale=dict(mode=mode,labels=["1","2","3","4"],cutoffs=[1],cutoffs2=[1])
            for color in colors(scale,settings):
                self.assertAlmostEqual(color[0],color[1]); self.assertAlmostEqual(color[1],color[2])

    def test_label_anchor_respects_hole_and_legacy_winding(self):
        f=dict(rings=[[[0,0],[0,5],[5,5],[5,0],[0,0]],[[1,1],[4,1],[4,4],[1,4],[1,1]]])
        from shapely.geometry import Point
        self.assertTrue(geometry(f).contains(Point(anchor(f))))
        legacy=dict(rings=[list(reversed(r)) for r in f["rings"]])
        self.assertEqual(anchor(f),anchor(legacy))

    def test_cartogram_area_and_nonoverlap_and_determinism(self):
        _,pack=load_pack(self.pack)
        first,meta=dorling(pack,dict(a=1,b=4,c=9),{})
        second,_=dorling(pack,dict(a=1,b=4,c=9),{})
        self.assertEqual(first,second)
        shapes=[geometry(f) for f in first["features"]]
        self.assertAlmostEqual(shapes[1].area/shapes[0].area,4,places=8)
        self.assertAlmostEqual(shapes[2].area/shapes[0].area,9,places=8)
        self.assertTrue(all(shapes[i].intersection(shapes[j]).area<1e-8 for i in range(3) for j in range(i)))
        self.assertEqual(meta["algorithm"],"dorling-relaxation-1")

    def test_custom_tile_revision_and_duplicate_cell_validation(self):
        _,pack=load_pack(self.pack)
        path=self.home/"tile.json"
        value=dict(schema="mapmaker-tile-1",revision="one",cells=dict(a=[0,0],b=[1,0],c=[0,1]))
        path.write_text(json.dumps(value),encoding="utf-8")
        output,meta=tiled(pack,dict(tiles=str(path)))
        self.assertEqual(len(output["features"]),3)
        self.assertEqual(meta["revision"],"one")
        value["cells"]["b"]=[0,0]; path.write_text(json.dumps(value),encoding="utf-8")
        with self.assertRaises(ValueError): tiled(pack,dict(tiles=str(path)))

    def test_flow_aggregation_precedes_threshold_and_topn(self):
        path=self.home/"flows.csv"
        path.write_text("origin,destination,volume\na,b,6\na,b,6\na,c,10\na,a,9\n",encoding="utf-8")
        manifest,_=load_pack(self.pack)
        rows,meta=flow_layer(dict(flows=str(path)),manifest,{"a","b","c"})
        selected,counts=selected_flows(rows,"2010",dict(flowtop=1,flowmin=11))
        self.assertEqual(selected[0]["volume"],12)
        self.assertEqual(counts["filtered_volume"],19)
        self.assertEqual(meta["source_rows"],4)

    def test_geographic_layers_and_decorations(self):
        points=self.home/"points.csv"; flows=self.home/"flows.csv"
        points.write_text("x,y,size,label\n1,1,10,Center\n150,1,3,Hidden\n",encoding="utf-8")
        flows.write_text("origin,destination,volume\na,b,10\na,c,2\n",encoding="utf-8")
        result=render(dict(self.request,points=str(points),flows=str(flows),flowtop=1,scalebar=True,northarrow=True))
        first=result["panels"][0]
        self.assertEqual(first["flows"]["drawn_volume"],10)
        self.assertEqual(first["flows"]["omitted_volume"],2)
        self.assertEqual(first["points"]["map"]["outside_view"],["2"])
        self.assertGreater(first["decorations"]["map"]["scale_meters"],0)

    def test_outline_vintage_must_be_acknowledged(self):
        path=self.home/"packs/other/1"
        import shutil
        shutil.copytree(self.pack,path)
        manifest=json.loads((path/"manifest.json").read_text(encoding="utf-8")); manifest.update(pack_id="other",vintage="other")
        (path/"manifest.json").write_text(json.dumps(manifest),encoding="utf-8")
        with self.assertRaisesRegex(ValueError,"vintage"):
            render(dict(self.request,outline="other"))
        self.assertTrue(render(dict(self.request,outline="other",allowvintagemismatch=True))["outlines"][0]["vintage_mismatch_acknowledged"])

    def test_reproduction_contains_no_observation_labels_or_coordinates(self):
        from mapmaker_engine.reproduction import run
        path=self.home/"manifest.json"
        self.data.write_text("mm_id,mm_panel,mm_bin,mm_label\na,2010,1,PRIVATE-TEXT\n",encoding="utf-8")
        render(dict(self.request,manifest=str(path)))
        raw=path.read_text(encoding="utf-8")
        self.assertNotIn("PRIVATE-TEXT",raw)
        self.assertNotIn(str(self.data),raw)
        request=dict(root=str(ROOT),using=str(path),action="verify")
        self.assertTrue(run(request,self.home)[0]["engine_match"])
        value=json.loads(raw); value["engine_sha256"]="wrong"; path.write_text(json.dumps(value),encoding="utf-8")
        with self.assertRaisesRegex(ValueError,"engine"): run(request,self.home)

    def test_offline_archive_restore_without_network_and_corrupt_rejection(self):
        output=self.home/"archive.zip"
        offline.run(dict(action="export",target="fixture",saving=str(output)),ROOT,self.home)
        elsewhere=self.home/"restored"
        with patch("urllib.request.OpenerDirector.open",side_effect=AssertionError("network")):
            result,_=offline.run(dict(action="restore",using=str(output)),ROOT,elsewhere)
            self.assertEqual(load_pack(result["path"])[0]["geometry_sha256"],load_pack(self.pack)[0]["geometry_sha256"])
        with zipfile.ZipFile(output,"a") as archive: archive.writestr("../escape",b"bad")
        with self.assertRaisesRegex(ValueError,"Invalid"): offline.run(dict(action="restore",using=str(output)),ROOT,elsewhere)

    def test_crosswalk_conservation_rates_coverage_and_no_normalization(self):
        weights=self.home/"weights.csv"; saved=self.home/"crosswalk.json"; data=self.home/"counts.csv"; output=self.home/"allocated.csv"
        weights.write_text("source,target,weight\na,b,.25\na,c,.5\nb,c,1\n",encoding="utf-8")
        crosswalks.run(dict(action="import",root=str(ROOT),using=str(weights),saving=str(saved),source="fixture@1",targetpack="fixture@1",universe="population",method="fixture fractions"),self.home)
        data.write_text("mm_id,numerator,denominator\na,100,200\nb,40,40\nc,10,20\n",encoding="utf-8")
        result,_=crosswalks.run(dict(action="apply",root=str(ROOT),using=str(saved),data=str(data),saving=str(output),denominator="denominator"),self.home)
        self.assertEqual(result["allocation"]["unallocated_numerator"],35)
        self.assertEqual(result["allocation"]["unallocated_denominator"],70)
        rows=list(csv.DictReader(io.StringIO(output.read_text(encoding="utf-8"))))
        self.assertAlmostEqual(float(rows[1]["value"]),90/140)
        value=json.loads(saved.read_text(encoding="utf-8")); value["rows"][0]["weight"]=.75
        with self.assertRaisesRegex(ValueError,"above 1"): crosswalks.validate(value)


if __name__ == "__main__": unittest.main()
