"""Curated projections, explicit transformations, and geographic domain handling."""
import math
from pathlib import Path
import warnings

WGS = " +datum=WGS84 +units=m +type=crs"
PRESETS = {
    "equalearth": ("Equal Earth (world, equal area)", "+proj=eqearth" + WGS),
    "equalearth-atlantic": ("Equal Earth, Atlantic-centered (equal area)", "+proj=eqearth +lon_0=-30" + WGS),
    "equalearth-pacific": ("Equal Earth, Pacific-centered (equal area)", "+proj=eqearth +lon_0=150" + WGS),
    "conus-albers": ("NAD83 / Conus Albers (equal area)", "EPSG:5070"),
    "alaska-albers": ("NAD83 / Alaska Albers (equal area)", "EPSG:3338"),
    "europe-laea": ("ETRS89 / Europe LAEA (equal area)", "EPSG:3035"),
    "regional-laea": ("Regional Lambert azimuthal (equal area; configurable center)", "+proj=laea +lat_0=0 +lon_0=0" + WGS),
    "australia-albers": ("GDA2020 / Australian Albers (equal area)", "EPSG:9473"),
    "australia-albers-gda94": ("GDA94 / Australian Albers (equal area; older datum)", "EPSG:3577"),
    "canada-lambert": ("NAD83 / Statistics Canada Lambert (conformal, not equal area)", "EPSG:3347"),
    "canada-equalarea": ("Canada-centered WGS84 LAEA (equal area)", "+proj=laea +lat_0=60 +lon_0=-96" + WGS),
    "robinson": ("Robinson (world, compromise)", "+proj=robin" + WGS),
    "winkeltripel": ("Winkel Tripel (world, compromise)", "+proj=wintri" + WGS),
    "auto-utm": ("Automatic WGS84 UTM zone and hemisphere (conformal)", "EPSG:32631"),
    "arctic-stereo": ("WGS84 / NSIDC Arctic, EPSG:3413 (conformal)", "EPSG:3413"),
    "antarctic-stereo": ("WGS84 / Antarctic, EPSG:3031 (conformal)", "EPSG:3031"),
    "arctic-equalarea": ("North-polar WGS84 LAEA (equal area)", "+proj=laea +lat_0=90 +lon_0=0" + WGS),
    "antarctic-equalarea": ("South-polar WGS84 LAEA (equal area)", "+proj=laea +lat_0=-90 +lon_0=0" + WGS),
    "azimuthal-equidistant": ("Azimuthal equidistant (distances from configured origin)", "+proj=aeqd +lat_0=0 +lon_0=0" + WGS),
    "orthographic": ("Orthographic globe (visible hemisphere only)", "+proj=ortho +lat_0=0 +lon_0=0" + WGS),
    "interrupted-goode": ("Interrupted Goode Homolosine (equal area, land lobes)", "+proj=igh" + WGS),
    "webmercator": ("Web Mercator (tile alignment; not equal area)", "EPSG:3857"),
}
ALIASES = {"laea": "regional-laea", "aeqd": "azimuthal-equidistant", "utm": "auto-utm", "igh": "interrupted-goode"}
PANEL_CENTERS = {"conus": (-96, 37.5, 29.5, 45.5), "alaska": (-154, 58.5, 55, 65),
                 "hawaii": (-157, 20, 8, 18), "puerto_rico": (-66, 18, 8, 18),
                 "samoa": (-170, -14, -10, -20), "guam": (145, 13, 8, 18),
                 "marianas": (146, 18, 8, 24), "virgin_islands": (-65, 18, 8, 18)}
DYNAMIC = {"regional-laea": "laea", "azimuthal-equidistant": "aeqd", "orthographic": "ortho"}


def crs_from_name(name):
    from pyproj import CRS
    key = ALIASES.get(name.lower(), name.lower())
    return CRS.from_user_input(PRESETS.get(key, (None, name))[1])


def browse(query="", full=False, country=""):
    from pyproj.database import query_crs_info
    from pyproj.enums import PJType
    rows = [dict(code="auto", title="Pack-recommended projection and layout")]
    rows += [dict(code=key, title=value[0]) for key, value in PRESETS.items()]
    if full or query or country:
        country_query = {"US": "United States", "GB": "United Kingdom", "CA": "Canada", "AU": "Australia"}.get(country.upper(), country)
        rows += [dict(code=f"{item.auth_name}:{item.code}", title=item.name, area=item.area_of_use.name)
                 for item in query_crs_info(pj_types=PJType.PROJECTED_CRS)
                 if not country_query or country_query.lower() in item.area_of_use.name.lower()]
    if query:
        rows = [row for row in rows if query.lower() in " ".join(row.values()).lower()]
    if country:
        rows = [row for row in rows if row.get("area")]
    return rows


def numbers(value, count, option):
    try:
        result = list(map(float, value.replace(",", " ").split())) if isinstance(value, str) else list(map(float, value))
    except (ValueError, TypeError):
        raise ValueError(f"{option}() requires {count} numbers") from None
    if len(result) != count or not all(math.isfinite(v) for v in result):
        raise ValueError(f"{option}() requires {count} finite numbers")
    return result


def selection(manifest, features, request, bins):
    region = request.get("region") or "all"
    if request.get("layout") == "conus":
        if region not in {"all", "conus"}:
            raise ValueError("layout(conus) requires region(conus) or no region()")
        region = "conus"
    excluded = []
    bounds = None
    if region != "all":
        names = region.replace(",", " ").split()
        if all(n in PANEL_CENTERS for n in names):
            if manifest.get("country", "US" if manifest["schema"] == 1 else "") != "US":
                raise ValueError("Named U.S. regions require a U.S. pack; otherwise supply region(west south east north)")
            excluded = [f["id"] for f in features if f["panel"] not in names]
            features = [f for f in features if f["panel"] in names]
        else:
            bounds = numbers(region, 4, "region")
            w, s, e, n = bounds
            if not (-180 <= w <= 180 and -180 <= e <= 180 and w != e and -90 <= s < n <= 90):
                raise ValueError("Invalid geographic region bounds")
    if request.get("zoom") and not request.get("context"):
        features = [f for f in features if f["id"] in bins]
    if not features:
        raise ValueError("No geography features remain in the selected region")
    return features, bounds, excluded


def geographic_extent(source, features):
    from pyproj import Transformer
    inverse = Transformer.from_crs(source, source.geodetic_crs, always_xy=True)
    points = [point for f in features for ring in f["rings"] for point in ring]
    xx, yy = inverse.transform(*zip(*points), errcheck=True)
    longitudes = sorted(set((x+180) % 360-180 for x in xx))
    if not longitudes or not all(math.isfinite(v) for v in [*xx, *yy]):
        raise ValueError("Cannot determine the geography extent")
    gaps = [(longitudes[(i+1) % len(longitudes)] + (360 if i == len(longitudes)-1 else 0)-x, i) for i, x in enumerate(longitudes)]
    gap, index = max(gaps)
    west, east = longitudes[(index+1) % len(longitudes)], longitudes[index]
    if 360-gap > 300:
        west, east = -180, 180
    return [west, min(yy), east, max(yy)]


def resolve(name, extent, center=""):
    from pyproj import CRS
    key = name.lower()
    name = ALIASES.get(key, key) if key in PRESETS or key in ALIASES else name
    west, south, east, north = extent
    span = (east-west) % 360 if east < west else east-west
    auto_center = [((west+span/2+180) % 360)-180, (south+north)/2]
    lon, lat = numbers(center, 2, "center") if center else auto_center
    if not (-180 <= lon <= 180 and -90 <= lat <= 90):
        raise ValueError("center() is longitude latitude in degrees")
    notes = []
    if name in DYNAMIC:
        target = CRS.from_user_input(f"+proj={DYNAMIC[name]} +lon_0={lon:.12g} +lat_0={lat:.12g}" + WGS)
    elif name == "auto-utm":
        zone = min(60, max(1, int((lon+180)//6)+1))
        if 56 <= lat < 64 and 3 <= lon < 12:
            zone = 32
        if 72 <= lat < 84 and 0 <= lon < 42:
            zone = 31 if lon < 9 else 33 if lon < 21 else 35 if lon < 33 else 37
        target = CRS.from_epsg((32600 if lat >= 0 else 32700)+zone)
        if south < -80 or north > 84:
            raise ValueError("UTM is unsuitable beyond 80 S / 84 N; choose a polar projection")
        if span > 6 or west < zone*6-186 or east > zone*6-180 or south < 0 < north:
            notes.append("Extent crosses UTM zones or the equator; scale distortion grows away from the chosen zone.")
    else:
        if center:
            raise ValueError("center() is supported by regional-laea, azimuthal-equidistant, orthographic, and auto-utm")
        target = crs_from_name(name)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        params = target.to_dict()
    method = params.get("proj")
    spec = dict(longitude=float(params.get("lon_0", 0)), latitude=float(params.get("lat_0", 0)), method=method)
    if method in {"ortho", "laea", "aeqd"}:
        spec["cap"] = 90 if method == "ortho" or abs(spec["latitude"]) == 90 else 179.9
    if method == "stere" and abs(spec["latitude"]) == 90:
        spec["cap"] = 90
    if method in {"merc", "webmerc"}:
        spec["mercator"] = True
    if method == "igh":
        spec["interrupted"] = True
    area = target.area_of_use
    if area and (south < area.south or north > area.north or
                 (area.west < area.east and (west < area.west or east > area.east or west > east))):
        notes.append(f"Extent exceeds the CRS area-of-use bounds {tuple(area.bounds)}; inspect projection describe or use region(). Offshore boundaries can extend beyond an onshore CRS area.")
    if name == "azimuthal-equidistant":
        notes.append("Distances are preserved from the chosen origin only, not between arbitrary locations.")
    if len(target.axis_info) != 2 or not (target.is_geographic or target.is_projected):
        raise ValueError("Destination must be a 2D geographic or projected CRS")
    return target, spec, notes


def project_pack(manifest, pack, request, bins):
    from .geography import data_home
    from .projection_resources import resources
    root = Path(request.get("root") or Path(__file__).resolve().parents[2])
    with resources(root, data_home(request.get("datadir")), request.get("grids") or "") as resource_meta:
        return _project_pack(manifest, pack, request, bins, resource_meta)


def _project_pack(manifest, pack, request, bins, resource_meta):
    import pyproj
    from pyproj import CRS, Transformer
    from .projection_resources import operation
    from .projection_geometry import project_rings, VERSION, STEP
    projection, layout = request.get("projection") or "auto", request.get("layout") or "auto"
    if layout not in {"auto", "single", "us-insets", "conus"}:
        raise ValueError("layout() must be auto, single, us-insets, or conus")
    if manifest["schema"] == 1 and projection not in {"auto", "legacy"}:
        raise ValueError("Legacy boundaries have a fixed projection/layout. Install a dated Census pack to change projections.")
    features, region_bounds, excluded = selection(manifest, pack["features"], request, bins)
    if manifest["schema"] == 1:
        if projection not in {"auto", "legacy"} or layout not in {"auto", "us-insets", "conus"} or region_bounds:
            raise ValueError("Legacy boundaries have a fixed projection/layout. Install a dated Census pack to change projections.")
        if request.get("center") or request.get("grids") or request.get("graticule") or request.get("distortion"):
            raise ValueError("Legacy boundaries have no source CRS; install a dated pack for projection options")
        result = dict(pack, features=features)
        notes = [f"Declared region excludes {len(excluded)} features."] if excluded else []
        return result, dict(projection="legacy", layout="us-insets" if layout != "conus" else "conus",
                            region=request.get("region") or ("conus" if layout == "conus" else "all"),
                            visible_features=len(features), excluded_ids=excluded,
                            source_excluded_ids=manifest.get("excluded_ids", []), warnings=notes)
    if layout == "auto":
        layout = manifest.get("layout", "single") if projection == "auto" else "single"
    if layout == "conus":
        projection = "conus-albers" if projection == "auto" else projection
    if layout == "us-insets" and manifest.get("country") != "US":
        raise ValueError("U.S. insets require a U.S. geography pack")
    if layout == "us-insets" and (projection != "auto" or request.get("center")):
        raise ValueError("U.S. insets use regional projections; use projection(auto) or layout(single)")
    source = CRS.from_user_input(manifest["source_crs"])
    if len(source.axis_info) != 2 or not (source.is_geographic or source.is_projected):
        raise ValueError("Mapping requires a 2D geographic or projected source CRS; height/epoch transformations are unsupported")
    extent = region_bounds or geographic_extent(source, features)
    target_name = manifest.get("recommended_projection", "equalearth") if projection == "auto" else projection
    result = dict(schema=2, features=[], borders={}, state_borders={}, graticules={}, indicatrices={}, outlines={})
    transforms, definitions, operations, specs = {}, {}, {}, {}
    notes = []
    for panel in sorted({f["panel"] if layout == "us-insets" else "map" for f in features}):
        if layout == "us-insets":
            lon, lat, p1, p2 = PANEL_CENTERS[panel]
            target = CRS.from_user_input(f"+proj=aea +lon_0={lon} +lat_0={lat} +lat_1={p1} +lat_2={p2} +datum=NAD83 +units=m +type=crs")
            spec = dict(longitude=lon, latitude=lat)
            panel_extent = geographic_extent(source, [f for f in features if f["panel"] == panel])
        elif target_name == "source":
            target, spec, panel_extent = source, {}, extent
        else:
            target, spec, warnings_ = resolve(target_name, extent, request.get("center") or "")
            notes.extend(warnings_)
            panel_extent = extent
        definitions[panel] = target.to_wkt()
        spec["region_bounds"] = region_bounds
        specs[panel] = spec
        if target_name == "source" and layout != "us-insets":
            transforms[panel] = (None, None)
            operations[panel] = dict(description="Source coordinates preserved", pipeline="proj=noop", accuracy_m=0, best_available=True)
        else:
            normalize, op = operation(source, target.geodetic_crs, panel_extent)
            forward = Transformer.from_crs(target.geodetic_crs, target, always_xy=True, force_over=True)
            transforms[panel] = (normalize, forward)
            operations[panel] = dict(op, projection_pipeline=forward.definition)
            if not op["best_available"]:
                notes.append("A higher-accuracy datum operation needs optional grids. The recorded available non-ballpark operation is used; run projection preflight for details.")
    metadata = dict(projection=projection, resolved_projection=target_name, layout=layout,
                    target_crs=definitions, source_crs=source.to_wkt(), extent=extent,
                    pyproj_version=pyproj.__version__, proj_version=pyproj.proj_version_str,
                    transformations=operations, geometry_pipeline=VERSION, sampling_degrees=STEP,
                    sampling_source_projected_m=25000, normalization_precision_degrees=1e-9, projected_precision_m=1e-5,
                    resolved_parameters=specs, region=request.get("region") or ("conus" if layout == "conus" else "all"),
                    excluded_ids=excluded, **resource_meta)
    from . import projection_cache as cache
    from .geography import data_home
    import shapely
    metadata.update(shapely_version=shapely.__version__, geos_version=shapely.geos_version_string)
    home = data_home(request.get("datadir"))
    cache_key = cache.key(dict(metadata=metadata, geometry=manifest.get("geometry_sha256") or cache.key(pack),
                               selected=[f["id"] for f in features], geography=manifest["geography"], geometry_type=manifest.get("geometry_type", "polygon"),
                               graticule=bool(request.get("graticule")), distortion=bool(request.get("distortion"))))
    cached = cache.load(home, cache_key)
    if cached:
        result, metadata = cached
        metadata["projection_cache"] = "hit"
        return result, metadata
    for feature in features:
        panel = feature["panel"] if layout == "us-insets" else "map"
        normalize, forward = transforms[panel]
        if normalize is None:
            if region_bounds:
                raise ValueError("Numeric region() needs a destination projection; source coordinates are preserved")
            rings, clipped = feature["rings"], 0
        else:
            try:
                rings, clipped = project_rings(feature["rings"], normalize, forward, source, specs[panel], manifest.get("geometry_type") == "line")
            except Exception as error:
                raise ValueError(f"Projection failed for feature {feature['id']}: {error}") from error
        if not rings:
            metadata.setdefault("hidden_ids", []).append(feature["id"])
            continue
        if clipped:
            metadata.setdefault("partly_visible_ids", []).append(feature["id"])
        points = [p for ring in rings for p in ring]
        bounds = [min(p[0] for p in points), min(p[1] for p in points), max(p[0] for p in points), max(p[1] for p in points)]
        result["features"].append(dict(id=feature["id"], panel=panel, rings=rings, bounds=bounds))
        result["borders"].setdefault(panel, []).extend(rings)
        if manifest["geography"] == "state":
            result["state_borders"].setdefault(panel, []).extend(rings)
    if not result["features"]:
        raise ValueError("No geometry is visible in this region/projection")
    metadata["warnings"] = list(dict.fromkeys(notes))
    metadata["visible_features"] = len(result["features"])
    if metadata.get("hidden_ids") or metadata.get("partly_visible_ids"):
        metadata["warnings"].append(f"Visible portions only: {len(metadata.get('hidden_ids', []))} features outside the view; {len(metadata.get('partly_visible_ids', []))} partly clipped.")
    if excluded:
        metadata["warnings"].append(f"Declared region excludes {len(excluded)} features.")
    if request.get("graticule") or request.get("distortion"):
        for panel in definitions:
            if transforms[panel][0] is None:
                raise ValueError("Graticules and distortion indicators require a destination projection")
            lines, circles, radius = overlays(CRS.from_wkt(definitions[panel]), specs[panel], request, extent)
            result["graticules"][panel], result["indicatrices"][panel] = lines, circles
            metadata["distortion_radius_m"] = radius
    for panel, spec in specs.items():
        if spec.get("method") == "ortho":
            from .projection_geometry import Frame
            horizon = Frame(spec["longitude"], spec["latitude"]).inverse([(x*.5, 1e-7) for x in range(-360, 361)])
            xx, yy = transforms[panel][1].transform(*zip(*horizon), errcheck=True)
            result["outlines"][panel] = [list(zip(xx, yy))]
    metadata["projection_cache"] = cache.save(home, cache_key, result, metadata)
    return result, metadata


def overlays(target, spec, request, extent):
    """Graticules and equal geodesic-radius circles, clipped like the boundaries."""
    from pyproj import Transformer
    from .projection_geometry import project_rings
    geo = target.geodetic_crs
    identity = Transformer.from_crs(geo, geo, always_xy=True)
    forward = Transformer.from_crs(geo, target, always_xy=True, force_over=True)
    west, south, east, north = extent
    span = east-west if east >= west else east+360-west
    step = next((n for n in (1, 2, 5, 10, 15, 30) if n >= max(span, north-south)/12), 30)
    parallels = range(max(-80, math.ceil(south/step)*step), min(80, math.floor(north/step)*step)+1, step)
    meridians = range(math.ceil(west/step)*step, math.floor((west+span)/step)*step+1, step)
    clip_spec = dict(spec, region_bounds=spec.get("region_bounds") or extent)
    lines, circles = [], []
    radius = min(250000, max(1000, min(max(span, .1), max(north-south, .1))*111000/30))
    if request.get("graticule"):
        raw = [[(x, south), (x, north)] for x in meridians]
        raw += [[(west, y), (west+span, y)] for y in parallels]
        lines, _ = project_rings(raw, identity, forward, geo, clip_spec, line=True)
    if request.get("distortion"):
        geod = target.get_geod()
        raw = []
        for lon in list(meridians)[1::2]:
            for lat in list(parallels)[1::2]:
                points = [geod.fwd(lon, lat, angle, radius)[:2] for angle in range(0, 361, 10)]
                # Unwrap before source-edge sampling; a circle may cross the seam.
                from .projection_geometry import unwrap
                raw.append(unwrap(points, closed=False))
        if raw:
            circles, _ = project_rings(raw, identity, forward, geo, clip_spec, line=True)
    return lines, circles, radius
