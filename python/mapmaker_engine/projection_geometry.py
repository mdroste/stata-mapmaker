"""Polygon/line clipping in a geographic frame, before applying a projection.

Edges in a pack are straight in its source CRS. They are sampled there before
normalization, then sampled in geographic coordinates at at most 0.5 degrees.
Azimuthal views rotate their center to the north pole so a horizon is a latitude
cut. Polygon subtraction retains holes even when a hole intersects that cut.
"""
import math

from shapely.geometry import Polygon, LineString, LinearRing, box
from shapely.geometry.polygon import orient
from shapely.affinity import translate
from shapely import make_valid, set_precision

STEP = .5
EPS = 1e-8
VERSION = 6


def parts(geometry, kind="Polygon"):
    if geometry.geom_type == kind and not geometry.is_empty:
        yield geometry
    elif hasattr(geometry, "geoms"):
        for part in geometry.geoms:
            yield from parts(part, kind)


def densify(points, step=STEP):
    output = []
    for a, b in zip(points, points[1:]):
        count = max(1, math.ceil(max(abs(a[0]-b[0]), abs(a[1]-b[1])) / step))
        if count > 20000:
            raise ValueError("Geometry edge exceeds projection sampling limit")
        output.extend((a[0]+(b[0]-a[0])*i/count, a[1]+(b[1]-a[1])*i/count) for i in range(count))
    return output + [tuple(points[-1])]


def groups(rings):
    """Schema-2 packs use clockwise exteriors followed by their CCW holes."""
    current = None
    for ring in rings:
        if not LinearRing(ring).is_ccw:
            if current:
                yield current
            current = [ring]
        elif current:
            current.append(ring)
        else:
            raise ValueError("Geography ring order is invalid: hole before exterior")
    if current:
        yield current


class Frame:
    def __init__(self, longitude=0, latitude=None):
        self.longitude, self.latitude = longitude, latitude
        if latitude is not None:
            lon, lat = map(math.radians, (longitude, latitude))
            self.basis = ((-math.sin(lon), math.cos(lon), 0),
                          (-math.sin(lat)*math.cos(lon), -math.sin(lat)*math.sin(lon), math.cos(lat)),
                          (math.cos(lat)*math.cos(lon), math.cos(lat)*math.sin(lon), math.sin(lat)))

    def forward(self, points):
        if self.latitude is None:
            return [((x-self.longitude+180) % 360-180, y) for x, y in points]
        output = []
        for x, y in points:
            lon, lat = math.radians(x), math.radians(y)
            vector = (math.cos(lat)*math.cos(lon), math.cos(lat)*math.sin(lon), math.sin(lat))
            a, b, c = [sum(u*v for u, v in zip(axis, vector)) for axis in self.basis]
            output.append((math.degrees(math.atan2(b, a)), math.degrees(math.asin(max(-1, min(1, c))))))
        return output

    def inverse(self, points):
        if self.latitude is None:
            return [(x+self.longitude, y) for x, y in points]
        output = []
        for x, y in points:
            lon, lat = math.radians(x), math.radians(y)
            v = (math.cos(lat)*math.cos(lon), math.cos(lat)*math.sin(lon), math.sin(lat))
            a, b, c = [sum(self.basis[j][i]*v[j] for j in range(3)) for i in range(3)]
            output.append((math.degrees(math.atan2(b, a)), math.degrees(math.asin(max(-1, min(1, c))))))
        return output


def unwrap(points, hole=False, closed=True):
    output = [points[0]]
    for x, y in points[1:]:
        x += 360 * round((output[-1][0]-x)/360)
        output.append((x, y))
    if closed:
        winding = round((output[-1][0]-output[0][0])/360)
        if winding:
            # A winding ring surrounds a pole in this rotated coordinate frame.
            pole = 90 if (winding > 0) == hole else -90
            output += [(output[-1][0], pole), (output[0][0], pole), output[0]]
        else:
            output[-1] = output[0]
    return output


def periodic(geometry, window, kind="Polygon"):
    if geometry.is_empty:
        return []
    low, _, high, _ = geometry.bounds
    output = []
    for turn in range(math.floor((low+180)/360), math.floor((high+180)/360)+1):
        # Coincident pole/seam cuts must remain coincident after floating-point
        # rotation; otherwise a microscopic radial sliver can fill a polar hole.
        shifted = set_precision(translate(geometry, xoff=-360*turn), 1e-9)
        output.extend(parts(shifted.intersection(window), kind))
    return output


def framed_polygon(rings, frame):
    """Cut each ring separately so seam-crossing holes cannot become exteriors."""
    window = box(-180, -90, 180, 90)
    exterior = Polygon(unwrap(frame.forward(rings[0])))
    if not exterior.is_valid:
        exterior = make_valid(exterior)
    from shapely import union_all
    result = union_all(periodic(exterior, window))
    for ring in rings[1:]:
        hole = Polygon(unwrap(frame.forward(ring), hole=True))
        if not hole.is_valid:
            hole = make_valid(hole)
        result = result.difference(union_all(periodic(hole, window)))
    return result


def project_rings(rings, normalize, forward, source, spec, line=False):
    """Return visible rings and the number of clipped source components."""
    geographic = []
    for ring in rings:
        if source.is_geographic:
            # Packs have deliberate seam vertices. Preserve edges along a pole.
            sampled = densify(ring)
        else:
            factor = source.axis_info[0].unit_conversion_factor
            sampled = densify(ring, 25000 / factor)
        xx, yy = normalize.transform(*zip(*sampled), errcheck=True)
        coords = list(zip(xx, yy))
        # Inverse projections can introduce a seam in otherwise continuous edges.
        unwrapped = unwrap(coords, closed=False)
        geographic.append(densify(unwrapped))
    frame = Frame(spec.get("longitude", 0), spec.get("latitude") if spec.get("cap") else None)
    bottom = 90-spec["cap"] if spec.get("cap") else -90
    top = 90
    if spec.get("mercator"):
        bottom, top = -85.0511287798066, 85.0511287798066
    windows = [(-180, bottom, 180, top)]
    if spec.get("interrupted"):
        windows = [(-180, 0, -40, 90), (-40, 0, 180, 90),
                   (-180, -90, -100, 0), (-100, -90, -20, 0),
                   (-20, -90, 80, 0), (80, -90, 180, 0)]
    output, projected_polygons, clipped = [], [], 0
    collection = [[r] for r in geographic] if line else list(groups_from_original(rings, geographic))
    if spec.get("region_bounds"):
        from shapely import union_all
        west, south, east, north = spec["region_bounds"]
        region = box(west, south, east, north) if west < east else union_all([box(west, south, 180, north), box(-180, south, east, north)])
        selected = []
        for component in collection:
            if line:
                geom = union_all(periodic(LineString(unwrap(Frame().forward(component[0]), closed=False)), box(-180,-90,180,90), "LineString"))
            else:
                geom = framed_polygon(component, Frame())
            if geom.is_empty:
                continue
            if not region.buffer(EPS).covers(geom):
                clipped += 1
            for item in parts(geom.intersection(region), "LineString" if line else "Polygon"):
                if line:
                    selected.append([list(item.coords)])
                else:
                    item = orient(item, sign=-1)
                    selected.append([list(item.exterior.coords), *[list(h.coords) for h in item.interiors]])
        collection = selected
    for component in collection:
        if line:
            geometry = LineString(unwrap(frame.forward(component[0]), closed=False))
            from shapely import union_all
            geometry = union_all(periodic(geometry, box(-180, -90, 180, 90), "LineString"))
        else:
            geometry = framed_polygon(component, frame)
        if geometry.is_empty:
            continue
        domain = box(-180, bottom, 180, top)
        if not domain.buffer(EPS).covers(geometry):
            clipped += 1
        for bounds in windows:
            piece = geometry.intersection(box(*bounds))
            for item in parts(piece, "LineString" if line else "Polygon"):
                sequences = [item.coords] if line else [item.exterior.coords, *[h.coords for h in item.interiors]]
                projected = []
                for seq in sequences:
                    points = densify(list(seq))
                    # Evaluate each side of an interruption in its own PROJ lobe.
                    if spec.get("interrupted"):
                        points = [(min(bounds[2]-EPS, max(bounds[0]+EPS, x)),
                                   max(EPS, y) if bounds[1] == 0 else min(-EPS, y)) for x, y in points]
                    elif spec.get("cap"):
                        # Nudge only the horizon, never the center/pole: moving
                        # the pole creates a false pinhole in a filled polygon.
                        points = [(x, max(bottom+EPS, y)) for x, y in points]
                    lonlat = frame.inverse(points)
                    xx, yy = forward.transform(*zip(*lonlat), errcheck=True)
                    coordinates = list(zip(xx, yy))
                    if not all(math.isfinite(v) for p in coordinates for v in p):
                        raise ValueError("Projection produced invalid coordinates; use a supported preset or a smaller region()")
                    projected.append(coordinates)
                if line:
                    output.extend(projected)
                else:
                    polygon = Polygon(projected[0], projected[1:])
                    precision = 1e-9 if forward.target_crs.is_geographic else 1e-5/forward.target_crs.axis_info[0].unit_conversion_factor
                    if not polygon.is_valid:
                        polygon = make_valid(polygon)
                    projected_polygons.extend(parts(set_precision(polygon, precision)))
    if projected_polygons:
        from shapely import union_all
        # Rotated-frame seams are artificial. Rejoin their coincident edges in
        # the destination plane so a pole is neither a slit nor a filled hole.
        for polygon in parts(union_all(projected_polygons)):
            polygon = orient(polygon, sign=-1)
            output.extend([list(polygon.exterior.coords), *[list(h.coords) for h in polygon.interiors]])
    return output, clipped


def groups_from_original(original, transformed):
    current = []
    for old, new in zip(original, transformed):
        if not LinearRing(old).is_ccw:
            if current:
                yield current
            current = [new]
        elif current:
            current.append(new)
        else:
            raise ValueError("Geography ring order is invalid")
    if current:
        yield current
