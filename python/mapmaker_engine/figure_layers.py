"""Typed local point/flow layers and deterministic publication decorations."""
import csv
import hashlib
import math
from pathlib import Path

from .figure_layouts import anchor


def read_table(path, required, maximum=100000):
    path = Path(path).expanduser()
    if path.stat().st_size > 64*1024*1024:
        raise ValueError("Layer table exceeds 64 MiB")
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not set(required).issubset(reader.fieldnames or []):
            raise ValueError("Layer table requires columns: " + ", ".join(required))
        rows = []
        for row in reader:
            if len(rows) >= maximum:
                raise ValueError(f"Layer exceeds {maximum:,} rows; aggregate before mapping")
            rows.append(row)
    return rows, hashlib.sha256(path.read_bytes()).hexdigest()


def finite(value, name, nonnegative=False):
    try:
        number = float(value)
    except (ValueError, TypeError):
        raise ValueError(f"{name} must be a number") from None
    if not math.isfinite(number) or (nonnegative and number < 0):
        raise ValueError(f"{name} must be finite" + (" and nonnegative" if nonnegative else ""))
    return number


def normalize_id(value, manifest):
    value = str(value).strip()
    if manifest.get("id_kind", "digits") == "digits":
        if not value.isascii() or not value.isdigit():
            raise ValueError("Geographic IDs must contain digits")
        width = int(manifest.get("id_width", 0))
        value = value.zfill(width) if width else str(int(value))
        if width and len(value) != width:
            raise ValueError("Geographic ID has the wrong width")
    if not value or len(value.encode()) > 244:
        raise ValueError("Invalid geographic ID")
    return value


def point_layer(request):
    if not request.get("points"):
        return [], {}
    rows, digest = read_table(request["points"], ["x", "y"])
    result = []
    for i, row in enumerate(rows):
        result.append(dict(id=row.get("id") or str(i+1), x=finite(row["x"], "Point x"), y=finite(row["y"], "Point y"),
                           size=finite(row.get("size") or 1, "Point size", True), label=row.get("label", ""),
                           facet=row.get("facet", ""), panel=row.get("panel", "")))
    return result, dict(sha256=digest, source_crs=request.get("pointcrs") or "EPSG:4326", rows=len(result), required=True)


def flow_layer(request, manifest, ids):
    if not request.get("flows"):
        return [], {}
    rows, digest = read_table(request["flows"], ["origin", "destination", "volume"], maximum=1000000)
    aggregated = {}
    for row in rows:
        origin, destination = (normalize_id(row[key], manifest) for key in ("origin", "destination"))
        if origin not in ids or destination not in ids:
            raise ValueError("Flow endpoint is absent from the selected geography; check IDs/vintage")
        key = (row.get("facet", ""), origin, destination)
        aggregated[key] = aggregated.get(key, 0) + finite(row["volume"], "Flow volume", True)
    result = [dict(facet=k[0], origin=k[1], destination=k[2], volume=v) for k,v in sorted(aggregated.items())]
    return result, dict(sha256=digest, source_rows=len(rows), aggregated_pairs=len(result), total_volume=sum(r["volume"] for r in result), required=True)


def selected_flows(rows, facet, request):
    available = [r for r in rows if not r["facet"] or r["facet"] == facet]
    minimum = finite(request.get("flowmin") or 0, "flowmin", True)
    maximum = int(request.get("flowtop") if request.get("flowtop") not in (None, "") else 50)
    if not 0 <= maximum <= 5000:
        raise ValueError("flowtop() must be 0-5000; zero includes all flows up to the 5,000-path drawing limit")
    selected = sorted([r for r in available if r["volume"] >= minimum and r["volume"] > 0 and r["origin"] != r["destination"]],
                      key=lambda r: (-r["volume"], r["origin"], r["destination"]))
    if maximum:
        selected = selected[:maximum]
    if len(selected) > 5000:
        raise ValueError("More than 5,000 flows remain; specify flowtop() or flowmin()")
    return selected, dict(total_volume=sum(r["volume"] for r in available), selected_volume=sum(r["volume"] for r in selected),
                          filtered_volume=sum(r["volume"] for r in available)-sum(r["volume"] for r in selected), selected_pairs=len(selected))


def draw_points(ax, points, facet, panel, target, request, limit, style):
    from pyproj import CRS, Transformer
    from .projection_resources import operation
    if target is None:
        raise ValueError("Coordinate point layers require a dated/imported geography with a known CRS")
    source = CRS.from_user_input(request.get("pointcrs") or "EPSG:4326")
    if len(source.axis_info) != 2:
        raise ValueError("Point coordinates require a 2D CRS")
    normalize, metadata = operation(source, target.geodetic_crs)
    forward = Transformer.from_crs(target.geodetic_crs, target, always_xy=True)
    shown, hidden = [], []
    for point in points:
        if point["facet"] and point["facet"] != facet or point["panel"] and point["panel"] != panel:
            continue
        lon, lat = normalize.transform(point["x"], point["y"], errcheck=True)
        x,y = forward.transform(lon, lat)
        if not math.isfinite(x+y) or not (ax.get_xlim()[0] <= x <= ax.get_xlim()[1] and ax.get_ylim()[0] <= y <= ax.get_ylim()[1]):
            hidden.append(point["id"])
            continue
        shown.append((point,x,y))
    # Larger symbols first, with translucent fill: small symbols remain visible.
    for point,x,y in sorted(shown, key=lambda r: (-r[0]["size"],r[0]["id"])):
        ax.scatter([x],[y],s=point["size"]/limit*float(request.get("symbolmax") or 500), c="#d46b32", alpha=.65,
                   edgecolors="white", linewidths=.35, zorder=7)
    return dict(shown=[p[0]["id"] for p in shown], outside_view=hidden, transformation=metadata), [(p[0]["id"],p[0]["label"],p[1],p[2],0,0) for p in shown if p[0]["label"]]


def draw_flows(ax, selected, features, target, spec, request, maximum):
    from matplotlib.collections import LineCollection
    from matplotlib.patches import FancyArrowPatch
    lookup = {f["id"]: f for f in features}
    shown, omitted = 0., 0.
    operation_meta = None
    for row in selected:
        if row["origin"] not in lookup or row["destination"] not in lookup:
            omitted += row["volume"]
            continue
        a, b = anchor(lookup[row["origin"]]), anchor(lookup[row["destination"]])
        width = 4*row["volume"]/maximum
        if target is not None:
            from pyproj import Transformer
            from .projection_geometry import project_rings, unwrap
            inverse = Transformer.from_crs(target, target.geodetic_crs, always_xy=True)
            forward = Transformer.from_crs(target.geodetic_crs, target, always_xy=True, force_over=True)
            identity = Transformer.from_crs(target.geodetic_crs, target.geodetic_crs, always_xy=True)
            lon1, lat1 = inverse.transform(*a, errcheck=True)
            lon2, lat2 = inverse.transform(*b, errcheck=True)
            points = [(lon1,lat1), *target.get_geod().npts(lon1,lat1,lon2,lat2,48), (lon2,lat2)]
            lines, _ = project_rings([unwrap(points, closed=False)], identity, forward, target.geodetic_crs, spec, line=True)
            ax.add_collection(LineCollection(lines, colors="#9d4729", linewidths=width, alpha=.55, zorder=6))
            if lines and len(lines[-1]) > 1:
                ax.add_patch(FancyArrowPatch(lines[-1][-2],lines[-1][-1],arrowstyle="-|>",mutation_scale=5+width*2,
                                            linewidth=0,color="#9d4729",alpha=.75,zorder=6))
        else:
            ax.add_patch(FancyArrowPatch(a,b,connectionstyle="arc3,rad=.18",arrowstyle="-|>",
                                        mutation_scale=6+width*2,linewidth=width,color="#9d4729",alpha=.55,zorder=6))
        shown += row["volume"]
    return dict(drawn_volume=shown, hidden_endpoint_volume=omitted)


def place_labels(fig, ax, candidates, maximum, fontsize):
    import matplotlib.patheffects as pe
    maximum = int(maximum)
    if not 0 <= maximum <= 1000:
        raise ValueError("labellimit() must be 0-1000")
    renderer = fig.canvas.get_renderer()
    boxes, placed, dropped = [], [], []
    for index, (ident,text,x,y,dx,dy) in enumerate(sorted(candidates, key=lambda r: r[0])):
        if not text:
            continue
        if len(placed) >= maximum:
            dropped.append(ident); continue
        offsets = [(dx,dy)] if dx or dy else [(0,0),(0,7),(0,-7),(7,0),(-7,0),(7,7),(-7,-7)]
        for ox,oy in offsets:
            artist = ax.annotate(text, (x,y), xytext=(ox,oy), textcoords="offset points", ha="center",va="center",
                                 fontsize=fontsize,zorder=9,clip_on=True,
                                 path_effects=[pe.withStroke(linewidth=1.6,foreground="white")],
                                 arrowprops=dict(arrowstyle="-",lw=.3,color="#777777") if ox or oy else None)
            bbox = artist.get_window_extent(renderer).expanded(1.08,1.15)
            manual = bool(dx or dy)
            inside = ax.bbox.contains(bbox.x0,bbox.y0) and ax.bbox.contains(bbox.x1,bbox.y1)
            if inside and (manual or not any(bbox.overlaps(b) for b in boxes)):
                boxes.append(bbox); placed.append(dict(id=ident, dx=ox,dy=oy,manual=manual)); break
            artist.remove()
        else:
            dropped.append(ident)
    return dict(placed=placed, omitted_ids=dropped)


def decorate(ax, target, features, request, fontsize):
    if not request.get("scalebar") and not request.get("northarrow"):
        return {}
    if target is None:
        raise ValueError("Scale bars and north arrows require a geographic layout with a known CRS")
    from pyproj import Transformer
    center = anchor(max(features, key=lambda f: (f["bounds"][2]-f["bounds"][0])*(f["bounds"][3]-f["bounds"][1])))
    inverse = Transformer.from_crs(target,target.geodetic_crs,always_xy=True)
    forward = Transformer.from_crs(target.geodetic_crs,target,always_xy=True)
    lon,lat = inverse.transform(*center,errcheck=True)
    geod = target.get_geod()
    metadata = dict(reference_longitude=lon, reference_latitude=lat)
    if request.get("scalebar"):
        lo,hi = ax.get_xlim()
        endpoint = inverse.transform(center[0]+(hi-lo)*.15,center[1])
        _,_,distance = geod.inv(lon,lat,*endpoint)
        if not math.isfinite(distance) or distance <= 0:
            raise ValueError("Cannot place a scale bar at this projection's reference point")
        power = 10**math.floor(math.log10(distance))
        meters = max(n*power for n in (1,2,5) if n*power <= distance)
        left,right = 0,(hi-lo)*.15
        for _ in range(40):
            middle = (left+right)/2
            endpoint = inverse.transform(center[0]+middle,center[1],errcheck=True)
            if geod.inv(lon,lat,*endpoint)[2] < meters:
                left = middle
            else:
                right = middle
        fraction = (left+right)/2/(hi-lo)
        ax.plot([.05,.05+fraction],[.06,.06],transform=ax.transAxes,color="#333333",lw=1.3,zorder=10)
        ax.text(.05,.085,f"{meters/1000:g} km at reference",transform=ax.transAxes,fontsize=fontsize-1,zorder=10)
        metadata["scale_meters"] = meters
    if request.get("northarrow"):
        nx,ny = forward.transform(*geod.fwd(lon,lat,0,1000)[:2],errcheck=True)
        dx,dy = nx-center[0],ny-center[1]
        length = math.hypot(dx,dy)
        if not length or abs(lat) > 89.99:
            raise ValueError("North direction is undefined at the reference point")
        pixel_length = .09*min(ax.bbox.width,ax.bbox.height)
        dx,dy = dx/length*pixel_length/ax.bbox.width,dy/length*pixel_length/ax.bbox.height
        ax.annotate("N",xy=(.9+dx,.8+dy),xytext=(.9,.8),xycoords="axes fraction",textcoords="axes fraction",
                    ha="center",fontsize=fontsize,arrowprops=dict(arrowstyle="-|>",lw=.7),zorder=10)
        metadata["north_reference"] = "local meridian at recorded reference point"
    return metadata
