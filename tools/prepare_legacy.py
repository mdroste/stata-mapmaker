"""Compile the checked-in TopoJSON into explicitly provisional, projected packs.

Only Python's standard library is needed. This does not infer an official Census
vintage from filenames. No topology simplification is applied. Coordinates use
the documented spherical Albers projection, not an EPSG ellipsoidal CRS.
"""
import argparse
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECTIONS = {
    "conus": (-96, 37.5, 29.5, 45.5),
    "alaska": (-154, 58.5, 55, 65),
    "hawaii": (-157, 20, 8, 18),
    "puerto_rico": (-66, 18, 8, 18),
}


def project(point, panel):
    lon0, lat0, lat1, lat2 = map(math.radians, PROJECTIONS[panel])
    lon, lat = map(math.radians, point[:2])
    n = (math.sin(lat1) + math.sin(lat2)) / 2
    c = math.cos(lat1) ** 2 + 2 * n * math.sin(lat1)
    rho = math.sqrt(c - 2 * n * math.sin(lat)) / n
    rho0 = math.sqrt(c - 2 * n * math.sin(lat0)) / n
    theta = n * ((lon - lon0 + math.pi) % (2 * math.pi) - math.pi)
    return [round(6371008.8 * rho * math.sin(theta), 2),
            round(6371008.8 * (rho0 - rho * math.cos(theta)), 2)]


def decode_arcs(topology):
    transform = topology.get("transform")
    result = []
    for arc in topology["arcs"]:
        x = y = 0
        points = []
        for a, b, *_ in arc:
            if transform:
                x += a
                y += b
                points.append([x * transform["scale"][0] + transform["translate"][0],
                               y * transform["scale"][1] + transform["translate"][1]])
            else:
                points.append([a, b])
        result.append(points)
    return result


def join_ring(indices, arcs):
    points = []
    for index in indices:
        arc = arcs[index] if index >= 0 else list(reversed(arcs[~index]))
        points.extend(arc if not points else arc[1:])
    if points and points[0] != points[-1]:
        points.append(points[0])
    return points


def orient(ring, outer):
    area = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(ring, ring[1:]))
    return ring if (area > 0) == outer else list(reversed(ring))


def build(geography, target):
    tract = geography == "tract"
    source = ROOT / "src/geos" / ("tract2010_lores.json" if tract else
                                  "counties_hr.json" if geography == "county" else "usa_county_cz_zip.json")
    raw = source.read_bytes()
    topology = json.loads(raw)
    arcs = decode_arcs(topology)
    key = {"county": "counties_hr", "state": "states", "cz": "commute", "tract": "tract2010_lores"}[geography]
    width = {"county": 5, "state": 2, "tract": 11, "cz": 0}[geography]
    features, arc_panels, state_owners = [], {}, {}
    excluded = []
    degenerate = []
    for geo in topology["objects"][key]["geometries"]:
        ident = str(geo.get("id", geo.get("properties", {}).get("id")))
        ident = ident.zfill(width)
        if geo.get("type") not in ("Polygon", "MultiPolygon"):
            degenerate.append(ident)
            continue
        polygons = [geo["arcs"]] if geo["type"] == "Polygon" else geo["arcs"]
        state = ident[:2] if geography != "cz" else ""
        if state and int(state) > 56 and state != "72":
            excluded.append(ident)
            continue
        panel = {"02": "alaska", "15": "hawaii", "72": "puerto_rico"}.get(state, "conus")
        if geography == "cz":
            point = join_ring(polygons[0][0], arcs)[0]
            panel = "alaska" if point[1] > 50 else "hawaii" if point[0] < -140 else "conus"
        rings = []
        for polygon in polygons:
            for i, indices in enumerate(polygon):
                ring = [project(p, panel) for p in join_ring(indices, arcs)]
                if len(ring) < 4:
                    continue
                rings.append(orient(ring, i == 0))
                for index in indices:
                    index = index if index >= 0 else ~index
                    arc_panels[(index, panel)] = True
                    state_owners.setdefault((index, panel), set()).add(state)
        if not rings:
            degenerate.append(ident)
            continue
        pts = [p for ring in rings for p in ring]
        bounds = [min(p[0] for p in pts), min(p[1] for p in pts),
                  max(p[0] for p in pts), max(p[1] for p in pts)]
        features.append({"id": ident, "panel": panel, "rings": rings, "bounds": bounds})
    features.sort(key=lambda f: f["id"])
    if len({f["id"] for f in features}) != len(features):
        raise ValueError("Duplicate geography IDs")
    borders = {p: [] for p in PROJECTIONS}
    states = {p: [] for p in PROJECTIONS}
    for index, panel in sorted(arc_panels):
        line = [project(p, panel) for p in arcs[index]]
        borders[panel].append(line)
        if geography == "state" or len(state_owners[(index, panel)]) > 1:
            states[panel].append(line)
    pack = {"schema": 1, "features": features, "borders": borders, "state_borders": states}
    payload = gzip.compress(json.dumps(pack, separators=(",", ":")).encode(), mtime=0)
    target.mkdir(parents=True, exist_ok=True)
    (target / "geometry.json.gz").write_bytes(payload)
    with (target / "ids.csv").open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["mm_id"])
        writer.writerows([f["id"]] for f in features)
    ids_hash = hashlib.sha256((target / "ids.csv").read_bytes()).hexdigest()
    manifest = {
        "schema": 1, "pack_id": f"{geography}-legacy", "revision": "1",
        "geography": geography, "vintage": "legacy", "id_width": width,
        "feature_count": len(features), "geometry_sha256": hashlib.sha256(payload).hexdigest(),
        "ids_sha256": ids_hash, "source_path": str(source.relative_to(ROOT)),
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "provenance": "Legacy Mapmaker asset; original source and boundary vintage not verified.",
        "projection": {"method": "spherical Albers equal-area", "radius_m": 6371008.8,
                       "parameters_lon0_lat0_lat1_lat2": PROJECTIONS},
        "precision_m": 0.01, "simplification": "none beyond source asset",
        "excluded_ids": excluded, "degenerate_ids": degenerate,
    }
    (target / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"{target.name}: {len(features):,} features, {len(payload)/1048576:.2f} MiB")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("geography", nargs="*", default=["county", "state", "cz"],
                        choices=["county", "state", "cz", "tract"])
    args = parser.parse_args()
    for geography in args.geography:
        build(geography, ROOT / "assets" / f"{geography}-legacy")
