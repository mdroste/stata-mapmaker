"""Audited membership tables and explicit county dissolves for commuting zones."""
import csv
import hashlib
import json
from pathlib import Path


def membership(root, entry):
    from .geography import token
    name = token(entry["pack_id"]) + ".csv"
    path = Path(root) / "catalog/membership" / name
    if not path.is_file():
        raise ValueError("Membership resource missing from the installation; reinstall the complete Mapmaker bundle")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != entry["membership_sha256"]:
        raise ValueError("Membership checksum mismatch")
    with path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    ids = [r["county_id"] for r in rows]
    if len(set(ids)) != len(ids) or any(not r["mm_id"] or len(r["county_id"]) != 5 for r in rows):
        raise ValueError("Invalid or duplicate county membership")
    return raw, rows


def attach(root, stage, entry):
    if not entry.get("membership_sha256"):
        return
    raw, rows = membership(root, entry)
    (Path(stage) / "membership.csv").write_bytes(raw)
    from .render import load_pack
    manifest, pack = load_pack(stage)
    if {r["mm_id"] for r in rows} != {f["id"] for f in pack["features"]}:
        raise ValueError("Membership zone IDs do not match polygon IDs")
    manifest.update(membership_sha256=entry["membership_sha256"], membership_count=len(rows))
    (Path(stage) / "manifest.json").write_text(json.dumps(manifest, indent=2)+"\n", encoding="utf-8")


def dissolve(root, home, stage, entry):
    from shapely import make_valid, union_all
    from shapely.geometry import shape
    from shapely.geometry.polygon import orient
    from pyproj import CRS
    import shapefile
    from . import geography as geo
    from .render import load_pack
    from .sources import polygons, write_pack
    recipe = entry["recipe"]
    if recipe.get("kind") != "county_dissolve":
        raise ValueError("Unsupported geography build recipe")
    selected = [e for e in geo.read_catalog(root, home)["packs"]
                if e["pack_id"] == recipe["base_pack"] and e["revision"] == recipe["base_revision"]]
    if len(selected) != 1:
        raise ValueError("Dissolve requires an exact catalog dependency")
    base_path = geo.install(root, home, selected[0])
    base, pack = load_pack(base_path)
    if base["schema"] != 2 or base["geography"] != "county":
        raise ValueError("Dissolve requires source-coordinate county polygons")
    raw, rows = membership(root, entry)
    by_county = {f["id"]: f for f in pack["features"]}
    missing = {r["county_id"] for r in rows} - set(by_county)
    if missing:
        raise ValueError(f"Membership counties missing from boundary vintage: {sorted(missing)[:20]}")
    groups, panels, names, repaired = {}, {}, {}, []
    for row in rows:
        county, ident = row["county_id"], row["mm_id"]
        feature = by_county[county]
        points, parts = [], []
        for ring in feature["rings"]:
            parts.append(len(points))
            points.extend(ring)
        geometry = shape(shapefile.Shape(shapeType=shapefile.POLYGON, points=points, parts=parts).__geo_interface__)
        if not geometry.is_valid:
            if recipe.get("repair") != "make_valid":
                raise ValueError(f"Invalid county {county}; an explicit repair recipe is required")
            geometry = make_valid(geometry)
            repaired.append(county)
        groups.setdefault(ident, []).append(geometry)
        if ident in panels and panels[ident] != feature["panel"]:
            raise ValueError("Zone crosses regional inset panels; use a single-panel build recipe")
        panels[ident] = feature["panel"]
        names[ident] = row.get("zone_name", "")
    features, attrs = [], []
    for ident, members in groups.items():
        rings = []
        for polygon in polygons(union_all(members)):
            polygon = orient(polygon, sign=-1)
            rings += [list(polygon.exterior.coords)] + [list(r.coords) for r in polygon.interiors]
        features.append(dict(id=ident, panel=panels[ident], rings=rings))
        attrs.append(dict(mm_id=ident, name=names[ident], county_count=len(members)))
    manifest = write_pack(stage, entry, CRS(base["source_crs"]), features, attrs,
                         {"county_geometry": base["geometry_sha256"], "membership": entry["membership_sha256"]},
                         repaired_county_ids=repaired, excluded_county_ids=sorted(set(by_county)-{r["county_id"] for r in rows}),
                         derived_from=dict(pack_id=base["pack_id"], revision=base["revision"], geometry_sha256=base["geometry_sha256"]))
    (Path(stage) / "membership.csv").write_bytes(raw)
    return manifest
