"""Small source adapters shared by the installer and maintainer catalog audit.

Source properties are retained in a separate table. Geometry never carries the
user's research data. GeoJSON follows RFC 7946 (longitude, latitude; WGS84).
"""
import csv
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import re


def records(source, entry, crs=None):
    """Return (CRS, property/geometry iterator, hashes) without extracting a ZIP."""
    from pyproj import CRS
    from .geography import shapefile_parts, MAX_UNPACKED
    crs = crs or entry.get("source_crs_override")
    if entry.get("format") == "geojson" or Path(source).suffix.lower() in {".json", ".geojson"}:
        raw = Path(source).read_bytes()
        if len(raw) > MAX_UNPACKED:
            raise ValueError("GeoJSON exceeds size limit")
        data = json.loads(raw)
        if data.get("exceededTransferLimit"):
            raise ValueError("Provider returned an incomplete layer (transfer limit)")
        if data.get("type") != "FeatureCollection" or not isinstance(data.get("features"), list):
            raise ValueError("Expected a GeoJSON FeatureCollection")
        if data.get("crs") and not crs:
            definition = data["crs"].get("properties", {}).get("name", "")
            if not definition or not CRS.from_user_input(definition).equals(CRS("EPSG:4326"), ignore_axis_order=True):
                raise ValueError("Legacy GeoJSON CRS requires an explicit crs() override")
        return CRS.from_user_input(crs or "EPSG:4326"), (
            (f.get("properties") or {}, f.get("geometry")) for f in data["features"]
        ), {"geojson": hashlib.sha256(raw).hexdigest()}
    import shapefile
    parts = shapefile_parts(source, entry.get("source_member"))
    if not {"shp", "shx", "dbf"}.issubset(parts):
        raise ValueError("A shapefile needs .shp, .shx and .dbf sidecars")
    definition = crs or entry.get("source_crs_override") or parts.get("prj", b"").decode("utf-8-sig").strip()
    if not definition:
        raise ValueError("Missing source CRS: include a .prj file or specify crs()")
    encoding = entry.get("encoding") or parts.get("cpg", b"utf-8").decode("ascii").strip()
    encoding = re.sub(r"^ISO\s*8859[- ]?(\d+)$", r"iso8859-\1", encoding, flags=re.I)
    if encoding.isdigit():
        encoding = "utf-8" if encoding == "65001" else "cp" + encoding
    def read():
        with shapefile.Reader(**{ext: io.BytesIO(parts[ext]) for ext in ("shp", "shx", "dbf")}, encoding=encoding) as reader:
            fields = {f[0] for f in reader.fields[1:]}
            if entry.get("id_method") == "1-based source record number, stable only within this source checksum":
                fields.add("_mm_source_row")
            required = set(entry["id_fields"]) | set(entry.get("filter", {}))
            if not required.issubset(fields):
                raise ValueError(f"Missing join/filter fields {required - fields}; available: {sorted(fields)}")
            for number, record in enumerate(reader.iterShapeRecords(), 1):
                values = record.record.as_dict()
                if entry.get("id_method") == "1-based source record number, stable only within this source checksum":
                    values["_mm_source_row"] = number
                if record.shape.shapeType == shapefile.NULL and entry.get("skip_null_geometry"):
                    yield values, None
                    continue
                allowed = {shapefile.POLYGON, shapefile.POLYLINE}
                if entry.get("dimensions") == "xy":
                    allowed.update({shapefile.POLYGONZ, shapefile.POLYGONM, shapefile.POLYLINEZ, shapefile.POLYLINEM})
                if record.shape.shapeType not in allowed:
                    raise ValueError("Expected a 2D polygon or line shapefile")
                yield values, record.shape.__geo_interface__
    return CRS.from_user_input(definition), read(), {k: hashlib.sha256(v).hexdigest() for k, v in parts.items()}


def identifier(values, entry):
    fields = entry["id_fields"]
    if any(values.get(k) is None or not str(values[k]).strip() for k in fields):
        raise ValueError("Missing geographic ID in source")
    widths = entry.get("id_field_widths", [0] * len(fields))
    ident = "".join(str(values[k]).strip().zfill(w) for k, w in zip(fields, widths))
    if entry.get("id_kind", "digits") == "digits":
        if not re.fullmatch(r"[0-9]+", ident):
            raise ValueError(f"Invalid numeric geography ID: {ident}")
        ident = ident.zfill(entry["id_width"])
        if entry["id_width"] and len(ident) != entry["id_width"]:
            raise ValueError(f"ID has unexpected width: {ident}")
    if not ident or len(ident.encode("utf-8")) > 244 or any(ord(c) < 32 for c in ident):
        raise ValueError(f"Empty or invalid geography ID: {ident}")
    return ident


def polygons(geometry):
    if geometry.geom_type == "Polygon":
        yield geometry
    elif hasattr(geometry, "geoms"):
        for part in geometry.geoms:
            yield from polygons(part)


def split_dateline(geometry):
    """Split geographic polygons at +/-180, preserving holes and ring winding.

    Already split world/polar polygons are left alone. Deliberate pole edges
    spanning the full longitude range are not treated as short dateline edges.
    """
    from shapely.geometry import Polygon, MultiPolygon, box
    from shapely.affinity import translate
    output = []
    for poly in polygons(geometry):
        ring = list(poly.exterior.coords)
        crossing = any(abs(a[0]-b[0]) > 180 and not (abs(a[1]) == 90 and abs(b[1]) == 90)
                       for a, b in zip(ring, ring[1:]))
        if not crossing:
            output.append(poly)
            continue
        def unwrap(points):
            unwrapped = [points[0][:2]]
            for x, y, *_ in points[1:]:
                x += 360 * round((unwrapped[-1][0]-x)/360)
                unwrapped.append((x, y))
            if unwrapped[-1] != unwrapped[0]:
                raise ValueError("Polar polygon needs explicit seam vertices before import")
            return unwrapped
        exterior = unwrap(ring)
        center = sum(p[0] for p in exterior)/len(exterior)
        holes = []
        for interior in poly.interiors:
            hole = unwrap(list(interior.coords))
            offset = 360 * round((center-sum(p[0] for p in hole)/len(hole))/360)
            holes.append([(x+offset, y) for x, y in hole])
        unwrapped = Polygon(exterior, holes)
        if not unwrapped.is_valid:
            raise ValueError("Invalid polygon at antimeridian; repair the source explicitly")
        lo, _, hi, _ = unwrapped.bounds
        for k in range(math.floor((lo+180)/360), math.floor((hi+180)/360)+1):
            clipped = unwrapped.intersection(box(-180+360*k, -90, 180+360*k, 90))
            output.extend(translate(p, xoff=-360*k) for p in polygons(clipped) if p.area)
    return MultiPolygon(output)


def split_lines(lines):
    """Clip line segments at the geographic seam without joining opposite edges."""
    output = []
    for line in lines:
        current = [line[0]]
        for a, b in zip(line, line[1:]):
            if abs(a[0]-b[0]) > 180:
                bx = b[0] + (360 if b[0] < a[0] else -360)
                edge = 180 if bx > a[0] else -180
                t = (edge-a[0])/(bx-a[0])
                y = a[1]+t*(b[1]-a[1])
                current.append((edge, y))
                if len(current) >= 2:
                    output.append(current)
                current = [(-edge, y), b]
            else:
                current.append(b)
        if len(current) >= 2:
            output.append(current)
    return output


def write_pack(destination, entry, source_crs, features, attributes, hashes, **extra):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    features.sort(key=lambda f: f["id"])
    attributes.sort(key=lambda r: r["mm_id"])
    payload = gzip.compress(json.dumps(dict(schema=2, features=features), separators=(",", ":")).encode(), mtime=0)
    (destination / "geometry.json.gz").write_bytes(payload)
    with (destination / "ids.csv").open("w", newline="", encoding="utf-8") as out:
        writer = csv.writer(out)
        writer.writerow(["mm_id"])
        writer.writerows([f["id"]] for f in features)
    fields = ["mm_id"] + sorted({k for row in attributes for k in row} - {"mm_id"})
    with (destination / "attributes.csv").open("w", newline="", encoding="utf-8") as out:
        writer = csv.DictWriter(out, fields)
        writer.writeheader()
        writer.writerows(attributes)
    digest = lambda name: hashlib.sha256((destination / name).read_bytes()).hexdigest()
    manifest = dict(entry, schema=2, feature_count=len(features), source_crs=source_crs.to_wkt(),
                    source_files_sha256=hashes, geometry_sha256=hashlib.sha256(payload).hexdigest(),
                    ids_sha256=digest("ids.csv"), attributes_sha256=digest("attributes.csv"),
                    attribute_fields=fields, id_examples=[f["id"] for f in features[:5]],
                    compiler_version=2, simplification="none beyond source", **extra)
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def compile_source(source, destination, entry, crs=None):
    from shapely.geometry import shape
    from shapely.geometry.polygon import orient
    from .geography import PANELS
    source_crs, rows, hashes = records(source, entry, crs)
    aggregate_count, aggregate_repairs = None, []
    if entry.get("dissolve"):
        from shapely import union_all, make_valid
        from shapely.geometry import mapping
        groups, common, aggregate_count = {}, {}, 0
        for values, raw_geometry in rows:
            aggregate_count += 1
            ident = identifier(values, entry)
            geom = shape(raw_geometry)
            if not geom.is_valid:
                if entry.get("repair") != "make_valid":
                    raise ValueError(f"Invalid source part for {ident}; explicit repair required")
                geom = make_valid(geom)
                aggregate_repairs.append(str(aggregate_count))
            groups.setdefault(ident, []).append(geom)
            if ident not in common:
                common[ident] = dict(values)
            else:
                common[ident] = {k:v for k,v in common[ident].items() if values.get(k) == v}
        rows = [(common[ident], mapping(union_all(geometries))) for ident, geometries in groups.items()]
    features, attributes, seen = [], [], set()
    source_count, repairs, nonspatial = 0, [], []
    panel_transform = None
    for values, raw_geometry in rows:
        source_count += 1
        if any(str(values.get(k)) != str(v) for k, v in entry.get("filter", {}).items()):
            continue
        ident = identifier(values, entry)
        if not raw_geometry and entry.get("skip_null_geometry"):
            nonspatial.append(ident)
            continue
        if ident in seen:
            raise ValueError(f"Duplicate geography ID: {ident}")
        seen.add(ident)
        if not raw_geometry or raw_geometry.get("type") not in {"Polygon", "MultiPolygon", "LineString", "MultiLineString"}:
            raise ValueError(f"Expected polygon or line geometry: {ident}")
        geometry = shape(raw_geometry)
        if geometry.is_empty:
            raise ValueError(f"Empty geometry: {ident}")
        is_line = geometry.geom_type in {"LineString", "MultiLineString"}
        if is_line != (entry.get("geometry_type", "polygon") == "line"):
            raise ValueError("Geometry type differs from the pack definition")
        if not geometry.is_valid and entry.get("repair") == "make_valid":
            from shapely import make_valid
            geometry = make_valid(geometry)
            repairs.append(ident)
        if not is_line and source_crs.is_geographic:
            geometry = split_dateline(geometry)
        if is_line:
            lines = [geometry] if geometry.geom_type == "LineString" else geometry.geoms
            rings = [list(line.coords) for line in lines]
            if source_crs.is_geographic:
                rings = split_lines(rings)
        else:
            rings = []
            for poly in polygons(geometry):
                poly = orient(poly, sign=-1)
                rings += [list(poly.exterior.coords)] + [list(r.coords) for r in poly.interiors]
        if not rings or not all(len(r) >= (2 if is_line else 4) and all(len(p) == 2 and all(math.isfinite(v) for v in p) for p in r) for r in rings):
            raise ValueError(f"Invalid 2D geometry: {ident}")
        state = entry.get("state_fips") or str(values.get("STATEFP", values.get("STATEFP20", "")))
        if not state and entry.get("country") == "US" and entry.get("layout") == "us-insets":
            # National nonhierarchical codes (CBSA, tribal areas, CZs) do not
            # encode a state. Choose the panel from location, never ID prefixes.
            from pyproj import Transformer
            point = geometry.representative_point()
            if panel_transform is None:
                panel_transform = Transformer.from_crs(source_crs, 4326, always_xy=True)
            lon, lat = panel_transform.transform(point.x, point.y)
            state = "02" if lat > 50 and (lon < -130 or lon > 170) else "15" if -165 < lon < -150 and 15 < lat < 25 else "72" if -68 < lon < -65 and 17 < lat < 20 else "66" if 140 < lon < 150 and 10 < lat < 15 else "69" if 140 < lon < 150 and 15 <= lat < 22 else "60" if lon < -165 and lat < 0 else "78" if -65 < lon < -64 and 17 < lat < 19 else ""
        panel = PANELS.get(state, "conus") if entry.get("layout") == "us-insets" else "map"
        features.append(dict(id=ident, panel=panel, rings=rings, geometry_type="line" if is_line else "polygon"))
        # Keep provider attributes (names, hierarchy, ISO alternatives) verbatim.
        attributes.append(dict({k: v if isinstance(v, (str, int, float, type(None))) else json.dumps(v, ensure_ascii=False, default=str)
                                for k, v in values.items() if k != "mm_id"}, mm_id=ident))
    if not features:
        raise ValueError("Source contains no selected features")
    expected = entry.get("source_feature_count")
    if expected and (aggregate_count if aggregate_count is not None else source_count) != expected:
        raise ValueError("Source feature count does not match catalog")
    if entry.get("feature_count") and len(features) != entry["feature_count"]:
        raise ValueError("Selected feature count does not match catalog")
    return write_pack(destination, entry, source_crs, features, attributes, hashes,
                      repaired_ids=repairs, repaired_source_parts=aggregate_repairs, nonspatial_ids=nonspatial,
                      antimeridian="split at +/-180 for geographic polygon sources")
