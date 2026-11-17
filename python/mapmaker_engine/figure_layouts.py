"""Deterministic nongeographic layouts; no new binary dependencies."""
import hashlib
import json
import math
from pathlib import Path

from shapely.geometry import Polygon, LinearRing
from shapely import union_all, make_valid
from .projection_geometry import groups


def geometry(feature):
    # Fixed legacy packs use the opposite winding from source-coordinate packs.
    rings = feature["rings"]
    if rings and LinearRing(rings[0]).is_ccw:
        rings = [list(reversed(r)) for r in rings]
    return union_all([make_valid(Polygon(g[0], g[1:])) for g in groups(rings)])


def anchor(feature):
    geom = geometry(feature)
    from .projection_geometry import parts as polygon_parts
    parts = list(polygon_parts(geom))
    if not parts:
        raise ValueError("No polygon interior is available for a label/symbol anchor")
    point = max(parts, key=lambda p: p.area).representative_point()
    return point.x, point.y


def base_centers(pack):
    """Place inset groups on one canvas before a nongeographic layout is built."""
    panels = sorted({f["panel"] for f in pack["features"]}, key=lambda p: (p != "conus", p))
    positions = {}
    for j, panel in enumerate(panels):
        features = [f for f in pack["features"] if f["panel"] == panel]
        points = {f["id"]: anchor(f) for f in features}
        xs, ys = zip(*points.values())
        span = max(max(xs)-min(xs), max(ys)-min(ys), 1)
        for ident, (x,y) in points.items():
            positions[ident] = [(x-min(xs))/span + (j % 3)*1.2, (y-min(ys))/span - (j//3)*1.2]
    return positions


def tiled(pack, request):
    positions = base_centers(pack)
    source = request.get("tiles")
    metadata = dict(kind="tile", algorithm="geographic-sort-grid-1", nongeographic=True)
    if source:
        raw = Path(source).read_bytes()
        value = json.loads(raw)
        if value.get("schema") != "mapmaker-tile-1" or not value.get("revision"):
            raise ValueError("Tile layout requires schema mapmaker-tile-1 and a revision")
        cells = value["cells"]
        if set(cells) != set(positions):
            raise ValueError("Tile layout IDs must exactly match the selected boundary universe")
        if any(len(p) != 2 or any(not isinstance(v, int) or isinstance(v, bool) for v in p) for p in cells.values()):
            raise ValueError("Tile coordinates must be integer column/row pairs")
        if len(set(map(tuple, cells.values()))) != len(cells):
            raise ValueError("Tile positions overlap")
        metadata.update(algorithm="explicit-grid-1", revision=value["revision"], sha256=hashlib.sha256(raw).hexdigest())
    else:
        columns = max(1, math.ceil(math.sqrt(len(positions)*1.5)))
        order = sorted(positions, key=lambda k: (-positions[k][1], positions[k][0], k))
        cells = {}
        for row in range(math.ceil(len(order)/columns)):
            band = sorted(order[row*columns:(row+1)*columns], key=lambda k: (positions[k][0], k))
            for col, ident in enumerate(band):
                cells[ident] = [col, -row]
    features = []
    for ident, (x,y) in sorted(cells.items()):
        ring = [[x-.45,y-.45],[x-.45,y+.45],[x+.45,y+.45],[x+.45,y-.45],[x-.45,y-.45]]
        features.append(dict(id=ident, panel="map", rings=[ring], bounds=[x-.45,y-.45,x+.45,y+.45]))
    metadata["cells"] = cells
    return dict(schema=2, features=features, borders={"map": [f["rings"][0] for f in features]}, state_borders={}), metadata


def dorling(pack, weights, request):
    import numpy as np
    from shapely import STRtree, box
    positions = base_centers(pack)
    ids = sorted(positions)
    if len(ids) > 5000:
        raise ValueError("Dorling cartograms support at most 5,000 regions; select or aggregate the geography")
    if set(weights) != set(ids) or any(not math.isfinite(v) or v < 0 for v in weights.values()) or not sum(weights.values()):
        raise ValueError("Cartograms need an explicit nonnegative size for every selected region and positive total mass")
    centers = np.array([positions[k] for k in ids], dtype=float)
    original = centers.copy()
    span = max(float(np.ptp(centers[:,0])), float(np.ptp(centers[:,1])), 1)
    radii = np.sqrt(np.array([weights[k] for k in ids])/sum(weights.values())) * span * .4
    maximum = int(request.get("iterations") or 500)
    if not 1 <= maximum <= 3000:
        raise ValueError("iterations() must be 1-3000")
    overlap = 0
    for iteration in range(maximum):
        boxes = box(centers[:,0]-radii, centers[:,1]-radii, centers[:,0]+radii, centers[:,1]+radii)
        pairs = STRtree(boxes).query(boxes)
        a, b = pairs[:,pairs[0] < pairs[1]]
        if not len(a):
            break
        delta = centers[b]-centers[a]
        distance = np.linalg.norm(delta, axis=1)
        need = radii[a]+radii[b]-distance
        keep = need > 1e-7*span
        if not np.any(keep):
            break
        a, b, delta, distance, need = a[keep], b[keep], delta[keep], distance[keep], need[keep]
        zero = distance < 1e-12
        delta[zero] = np.column_stack((np.cos(a[zero]+b[zero]), np.sin(a[zero]+b[zero])))
        distance[zero] = 1
        forces = delta/distance[:,None]*(need[:,None]+1e-7*span)*.55
        motion, count = np.zeros_like(centers), np.zeros(len(ids))
        np.add.at(motion, a, -forces); np.add.at(motion, b, forces)
        np.add.at(count, a, 1); np.add.at(count, b, 1)
        centers += motion/np.maximum(count[:,None],1)
        if iteration < 30:
            centers += (original-centers)*.005
        overlap = float(np.max(need))
    else:
        raise ValueError("Cartogram did not resolve circle overlaps; increase iterations() or use a smaller region")
    features = []
    for ident, (x,y), radius in zip(ids, centers, radii):
        # Zero values are recorded but have zero visible area.
        if radius == 0:
            continue
        ring = [[float(x+radius*math.cos(t)),float(y+radius*math.sin(t))] for t in np.linspace(0,-2*math.pi,73)]
        features.append(dict(id=ident, panel="map", rings=[ring], bounds=[float(x-radius),float(y-radius),float(x+radius),float(y+radius)]))
    metadata = dict(kind="dorling", algorithm="dorling-relaxation-1", nongeographic=True,
                    iterations=iteration+1, max_overlap_tolerance=1e-7*span,
                    zero_area_ids=[k for k in ids if weights[k] == 0], area_proportional=True)
    return dict(schema=2, features=features, borders={"map": [f["rings"][0] for f in features]}, state_borders={}), metadata
