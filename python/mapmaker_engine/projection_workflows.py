"""Projection discovery, preflight, recommendations, and comparison exports."""
import io
import json
import math
from pathlib import Path
import shlex

from . import geography as geo
from . import projections as proj
from . import projection_resources as grids


def inset_settings(value, panels):
    rectangles, captions = {}, {}
    for item in value.split(";"):
        if not item.strip():
            continue
        words = shlex.split(item)
        if len(words) < 5 or words[0] not in panels:
            raise ValueError("insets() entries: panel left bottom width height [caption]; panel must be visible")
        panel = words[0]
        if panel in rectangles:
            raise ValueError("Duplicate inset panel")
        x, y, width, height = proj.numbers(words[1:5], 4, "insets")
        if min(x, y) < 0 or min(width, height) <= 0 or x+width > 1 or y+height > 1:
            raise ValueError("Inset rectangles must fit within the figure (coordinates 0 to 1)")
        rectangles[panel] = [x, y, width, height]
        captions[panel] = " ".join(words[5:]) if len(words) > 5 else panel.replace("_", " ").title()
    return rectangles, captions


def context(request, home):
    from pyproj import CRS
    geography = request.get("geography") or (request.get("target") if request["action"] in {"recommend", "compare"} else "")
    if geography:
        path, manifest = geo.resolve(Path(request["root"]), home, geography, request.get("revision") or "1", request.get("vintage") or "")
        from .render import load_pack
        manifest, pack = load_pack(path)
        if manifest["schema"] == 1:
            raise ValueError("Legacy packs have fixed projections. Install a dated pack for projection preflight/recommend/compare.")
        source = CRS.from_user_input(manifest["source_crs"])
        features, bounds, _ = proj.selection(manifest, pack["features"], request, {})
        extent = bounds or proj.geographic_extent(source, features)
        return source, extent, manifest, pack
    if not request.get("crs"):
        raise ValueError("Specify geography(pack_id) or crs(source_crs) for projection preflight")
    source = CRS.from_user_input(request["crs"])
    area = source.area_of_use
    extent = proj.numbers(request["region"], 4, "region") if request.get("region") else list(area.bounds) if area else [-180, -90, 180, 90]
    return source, extent, {}, None


def preflight(request, home):
    source, extent, manifest, _ = context(request, home)
    if len(source.axis_info) != 2 or not (source.is_geographic or source.is_projected):
        raise ValueError("Preflight supports 2D geographic or projected source CRSs")
    name = request.get("projection") or request.get("target") or manifest.get("recommended_projection") or "equalearth"
    if name == "auto":
        name = manifest.get("recommended_projection", "equalearth")
    if name == "source":
        name = source.to_wkt()
    target, spec, notes = proj.resolve(name, extent, request.get("center") or "")
    from pyproj import Transformer
    with grids.resources(request["root"], home, request.get("grids") or "") as resource_meta:
        chosen, op = grids.inspect_operation(source, target.geodetic_crs, extent)
        available = chosen is not None
        if available:
            op["projection_pipeline"] = Transformer.from_crs(target.geodetic_crs, target, always_xy=True, force_over=True).definition
        indexed = {e["name"]: e for e in grids.catalog(request["root"])}
        missing = []
        for item in op.get("missing_operations", []):
            for name_ in item["grids"]:
                entry = indexed.get(name_)
                row = dict(name=name_, operation=item["operation"], available_for_install=bool(entry))
                if entry:
                    row.update(entry)
                    row["install_command"] = f"mapmaker projection install {name_}@{entry['sha256']}"
                    if request.get("datadir"):
                        row["install_command"] += f' datadir("{request["datadir"]}")'
                        row["install_command"] = row["install_command"].replace(' datadir(', ', datadir(', 1)
                missing.append(row)
        import pyproj
        return dict(available=available, source_crs=source.to_wkt(), source_name=source.name,
                    target_crs=target.to_wkt(), target_name=target.name, extent=extent,
                    resolved_parameters=spec, transformation=op, missing_grids=missing,
                    warnings=notes, pyproj_version=pyproj.__version__, proj_version=pyproj.proj_version_str, **resource_meta)


def preflight_lines(result):
    lines = ["Source: " + result["source_name"], "Destination: " + result["target_name"],
             "Operation: " + result["transformation"]["description"],
             "Operation accuracy (m; -1 = unknown): " + str(result["transformation"].get("accuracy_m", "unavailable")),
             "Best known operation available: " + str(result["transformation"]["best_available"])]
    lines += result["warnings"]
    seen = set()
    for item in result["missing_grids"]:
        lines.append("Affected operation: " + item["operation"])
        if item["name"] in seen:
            continue
        seen.add(item["name"])
        if item["available_for_install"]:
            lines += [f"  {item['name']}: {item['bytes']:,} bytes; {item['license']}",
                      "  SHA256: " + item["sha256"], "  " + item["install_command"],
                      f"  Select explicitly with grids({item['name']}@{item['sha256']})"]
        else:
            lines.append("  " + item["name"] + ": outside the reviewed grid catalog; no automatic download.")
    lines.append("Installing grids alone does not change a map. Select grids() explicitly; network transformations are disabled.")
    return lines


def recommend(request, home):
    source, extent, manifest, _ = context(request, home)
    purpose = request.get("purpose") or "thematic"
    if purpose not in {"thematic", "reference", "distance", "local", "globe", "web"}:
        raise ValueError("purpose() must be thematic, reference, distance, local, globe, or web")
    west, south, east, north = extent
    span = east-west if east >= west else east+360-west
    global_map = span > 150 and north-south > 80
    if purpose == "distance":
        candidates = ["azimuthal-equidistant", "regional-laea", "orthographic"]
    elif purpose == "web":
        candidates = ["webmercator", "equalearth", "regional-laea"]
    elif purpose == "globe":
        candidates = ["orthographic", "regional-laea", "equalearth"]
    elif global_map:
        candidates = ["equalearth", "robinson", "winkeltripel"] if purpose != "reference" else ["winkeltripel", "robinson", "equalearth"]
    elif south >= 55:
        candidates = ["arctic-equalarea", "arctic-stereo", "regional-laea"]
    elif north <= -55:
        candidates = ["antarctic-equalarea", "antarctic-stereo", "regional-laea"]
    elif purpose == "local" and span < 12:
        candidates = ["auto-utm", "regional-laea", "azimuthal-equidistant"]
    elif manifest.get("country") == "US":
        if south >= 48 and (west > east or west < -130):
            candidates = ["alaska-albers", "regional-laea", "equalearth"]
        elif -126 <= west < east <= -66 and south >= 24 and north <= 50:
            candidates = ["conus-albers", "regional-laea", "equalearth"]
        else:
            candidates = ["regional-laea", "equalearth", "orthographic"]
    elif manifest.get("country") == "CA":
        candidates = ["canada-equalarea", "canada-lambert", "regional-laea"]
    elif manifest.get("country") == "AU":
        candidates = ["australia-albers", "australia-albers-gda94", "regional-laea"]
    elif -30 < west < east < 50 and south > 25:
        candidates = ["europe-laea", "regional-laea", "azimuthal-equidistant"]
    else:
        candidates = ["regional-laea", "equalearth", "azimuthal-equidistant"]
    rows = []
    for name in candidates:
        center = request.get("center") or ""
        if name not in proj.DYNAMIC and name != "auto-utm":
            center = ""
        try:
            info = preflight(dict(request, projection=name, center=center), home)
            target, spec, _ = proj.resolve(name, extent, center)
            option = f"projection({name})"
            if name in proj.DYNAMIC:
                option += f" center({spec['longitude']:.12g} {spec['latitude']:.12g})"
            if name == "auto-utm":
                option = f"projection({target.to_authority()[0]}:{target.to_authority()[1]})"
            options = option + " layout(single)"
            for key in ("region", "grids", "datadir"):
                if request.get(key):
                    options += f' {key}("{request[key]}")'
            command = f"mapmaker geography preview {manifest['pack_id']}, revision({manifest['revision']}) {options} saving(\"{manifest['pack_id']}-{name}.pdf\")" if manifest else options
            rows.append(dict(preset=name, reason=proj.PRESETS[name][0], command=command, **info))
        except ValueError as error:
            rows.append(dict(preset=name, available=False, reason=str(error)))
    return rows


def compare(request, home):
    from .render import load_pack
    from .geography_tables import atomic_bytes
    from matplotlib.figure import Figure
    from matplotlib.collections import LineCollection, PatchCollection
    from matplotlib.patches import PathPatch
    from matplotlib.path import Path as MplPath
    import matplotlib as mpl
    _, _, manifest, pack = context(request, home)
    if pack is None:
        raise ValueError("Projection comparison requires geography(pack_id)")
    names = (request.get("choices") or "equalearth robinson winkeltripel").split()
    if not 2 <= len(names) <= 6:
        raise ValueError("choices() requires two to six projections")
    output = Path(request.get("saving") or "projection-options.pdf").expanduser().absolute()
    if output.suffix.lower() not in {".pdf", ".svg", ".png"}:
        raise ValueError("Comparison saving() must end in .pdf, .svg, or .png")
    if output.exists() and not request.get("replace"):
        raise FileExistsError("Comparison output exists; specify replace")
    cols = min(3, len(names))
    rows = math.ceil(len(names)/cols)
    results = []
    with mpl.rc_context({"font.family": "DejaVu Sans", "text.usetex": False, "text.parse_math": False,
                         "pdf.fonttype": 42, "svg.fonttype": "path", "svg.hashsalt": "mapmaker-projections"}):
        fig = Figure(figsize=(5*cols, 4.5*rows), dpi=150, facecolor="white")
        for i, name in enumerate(names):
            options = dict(request, projection=name, layout="single")
            canonical = proj.ALIASES.get(name.lower(), name.lower())
            if canonical not in proj.DYNAMIC and canonical != "auto-utm":
                options["center"] = ""
            projected, metadata = proj.project_pack(manifest, pack, options, {})
            results.append(metadata)
            ax = fig.add_subplot(rows, cols, i+1)
            ax.set_aspect("equal")
            ax.set_axis_off()
            patches = []
            for feature in projected["features"]:
                vertices, codes = [], []
                for ring in feature["rings"]:
                    vertices.extend(ring)
                    codes.extend([MplPath.MOVETO]+[MplPath.LINETO]*(len(ring)-2)+[MplPath.CLOSEPOLY])
                patches.append(PathPatch(MplPath(vertices, codes)))
            if manifest.get("geometry_type") == "line":
                ax.add_collection(LineCollection(projected["borders"].get("map", []), colors="#547f85", linewidths=.5))
            else:
                ax.add_collection(PatchCollection(patches, facecolor="#8fb5b4", edgecolor="white", linewidths=.25))
            ax.add_collection(LineCollection(projected["graticules"].get("map", []), colors="#9eaaaa", linewidths=.3))
            ax.add_collection(LineCollection(projected["indicatrices"].get("map", []), colors="#b6532f", linewidths=.6))
            bounds = [f["bounds"] for f in projected["features"]]
            if projected.get("outlines", {}).get("map"):
                points = [p for r in projected["outlines"]["map"] for p in r]
                bounds = [[min(p[0] for p in points), min(p[1] for p in points), max(p[0] for p in points), max(p[1] for p in points)]]
                ax.add_collection(LineCollection(projected["outlines"]["map"], colors="#9eaaaa", linewidths=.5))
            ax.set_xlim(min(b[0] for b in bounds), max(b[2] for b in bounds))
            ax.set_ylim(min(b[1] for b in bounds), max(b[3] for b in bounds))
            ax.margins(.02)
            ax.set_title(name, fontsize=13)
            if metadata.get("hidden_ids") or metadata.get("partly_visible_ids"):
                ax.text(.5, -.06, f"Visible portions: {metadata['visible_features']} of {len(pack['features'])} features", transform=ax.transAxes, ha="center", fontsize=8)
        fig.suptitle(f"{manifest['pack_id']} / revision {manifest['revision']}", fontsize=12)
        fig.subplots_adjust(left=.02, right=.98, top=.86, bottom=.12, wspace=.08, hspace=.30)
        caption = "Same boundaries and styling; each panel fits its own extent."
        if request.get("distortion"):
            caption += " Orange circles have equal geodesic radius within each panel."
        fig.text(.5, .025, caption, ha="center", fontsize=8)
        metadata = dict(pack=manifest["pack_id"], revision=manifest["revision"], geometry_sha256=manifest["geometry_sha256"], comparisons=results)
        fmt = output.suffix[1:].lower()
        encoded = json.dumps(metadata, separators=(",", ":"))
        file_meta = {"Subject": encoded} if fmt == "pdf" else {"Description": encoded}
        stream = io.BytesIO()
        fig.savefig(stream, format=fmt, metadata=file_meta)
        fig.clear()
        atomic_bytes(output, stream.getvalue(), request.get("replace", False))
    return dict(output=str(output), **metadata)


def run(request, home):
    from .library import safe_text
    action, target = request["action"], request.get("target", "").strip().strip('"')
    root = request["root"]
    result, lines = {}, []
    if action in {"browse", "search"}:
        rows = proj.browse(target or request.get("search", ""), request.get("all", False), request.get("country", ""))
        result["entries"] = rows
        lines = ["Projection definitions are bundled; no installation is needed."]
        lines += [f"{r['code']:24} {r['title']}" for r in rows]
    elif action == "describe":
        if target == "auto":
            lines = ["auto: pack-recommended projection and layout; legacy packs remain fixed."]
        else:
            crs = proj.crs_from_name(target)
            result.update(name=crs.name, wkt=crs.to_wkt())
            lines = [proj.PRESETS.get(target, (crs.name,))[0], str(crs.area_of_use), crs.to_wkt()]
            if target in proj.DYNAMIC:
                lines.insert(1, "center(longitude latitude) defaults to the selected extent center; the resolved center is saved.")
        lines += ["Use projection preflight with geography() or crs() to inspect datum operations and optional grids."]
    elif action == "preflight":
        result = preflight(request, home)
        lines = preflight_lines(result)
    elif action == "recommend":
        rows = recommend(request, home)
        result["recommendations"] = rows
        lines = ["Purpose: " + (request.get("purpose") or "thematic"), "Recommendations use extent, source CRS, and selected transformation resources."]
        for row in rows:
            lines += [row["preset"] + ": " + row["reason"], "  Available: " + str(row["available"])]
            if row.get("command"):
                lines += ["  " + row["command"], *["  " + note for note in row["warnings"]]]
                if not row["transformation"]["best_available"]:
                    lines.append("  Higher-accuracy operations need grids; run projection preflight.")
        lines.append("Equal-area projections support area comparisons; mapping raw counts can still be misleading.")
    elif action == "compare":
        result = compare(request, home)
        lines = ["Saved projection comparison: " + result["output"]]
    elif action == "cache":
        from .projection_cache import manage
        result = manage(home, target, request.get("limit"))
        lines = [f"Projected boundaries: {result['files']} entries, {result['bytes']:,} bytes; limit {result['limit_bytes']:,} bytes.",
                 "Use projection cache purge or projection cache limit, limit(MiB). Zero disables caching."]
    elif action in {"grids", "install", "remove", "verify"}:
        if action == "grids":
            rows = grids.catalog(root)
            if target or request.get("search"):
                query = (target or request["search"]).lower()
                rows = [r for r in rows if query in json.dumps(r).lower()]
            rows = [dict(r, installed=grids.grid_path(home, r).is_file()) for r in rows]
            if request.get("installed"):
                rows = [r for r in rows if r["installed"]]
            total = len(rows)
            if not request.get("all"):
                offset, limit = int(request.get("offset") or 0), int(request.get("limit") or 50)
                if offset < 0 or limit < 1:
                    raise ValueError("offset() must be nonnegative and limit() positive")
                rows = rows[offset:offset+limit]
            result.update(entries=rows, count=total)
            lines = [f"Optional grids: showing {len(rows)} of {total}. Install explicitly; select with grids() when mapping."]
            lines += [f"{r['name']} | {r['bytes']:,} bytes | {r['license']} | {'installed' if r['installed'] else 'available'}" for r in rows]
        else:
            entry = grids.grid_entry(root, target)
            if action == "install":
                grids.install(root, home, target)
            elif action == "verify":
                grids.verify(home, entry)
            else:
                grids.grid_path(home, entry).unlink(missing_ok=True)
            result["grid"] = entry
            lines = [f"Grid {action}: {entry['name']} / {entry['sha256']}", "Maps use this grid only when explicitly selected with grids()."]
    else:
        raise ValueError("Projection actions: browse, search, describe, recommend, preflight, compare, grids, install, remove, verify")
    if action in {"preflight", "recommend"} and request.get("saving"):
        from .geography_tables import atomic_bytes
        output = Path(request["saving"]).expanduser().absolute()
        if output.suffix.lower() != ".json":
            raise ValueError("Preflight/recommend saving() must end in .json")
        atomic_bytes(output, (json.dumps(result, indent=2)+"\n").encode(), request.get("replace", False))
        lines.append("Saved projection report: " + str(output))
    # Retain double quotes in the runnable command examples; strip SMCL/macro syntax.
    return result, ["".join(c if c.isprintable() and c not in '{}$`' else " " for c in str(line)) for line in lines]
