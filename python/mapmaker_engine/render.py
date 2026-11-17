"""Render preclassified choropleths. No Stata, browser, or GIS imports."""
import csv
import gzip
import hashlib
import json
import math
import os
import tempfile
from pathlib import Path

from . import __version__


def load_pack(directory):
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema") not in (1, 2):
        raise ValueError("Unsupported geography-pack schema")
    payload = (directory / "geometry.json.gz").read_bytes()
    if hashlib.sha256(payload).hexdigest() != manifest["geometry_sha256"]:
        raise ValueError("Geography checksum failed; rebuild or reinstall this pack")
    if hashlib.sha256((directory / "ids.csv").read_bytes()).hexdigest() != manifest["ids_sha256"]:
        raise ValueError("Geographic ID table checksum failed")
    for name in ("attributes", "membership"):
        if manifest.get(name + "_sha256") and hashlib.sha256((directory / (name + ".csv")).read_bytes()).hexdigest() != manifest[name + "_sha256"]:
            raise ValueError(f"Geographic {name} table checksum failed")
    pack = json.loads(gzip.decompress(payload))
    ids = [f["id"] for f in pack["features"]]
    with (directory / "ids.csv").open(encoding="utf-8", newline="") as stream:
        id_rows = list(csv.DictReader(stream))
    if (pack.get("schema") != manifest["schema"] or len(ids) != len(set(ids))
            or len(ids) != manifest["feature_count"] or [row.get("mm_id") for row in id_rows] != ids):
        raise ValueError("Invalid geography features")
    return manifest, pack


def read_bins(filename, ids, nbins):
    values = {}
    with open(filename, encoding="utf-8-sig", newline="") as f:
        rows = csv.DictReader(f)
        if rows.fieldnames != ["mm_id", "mm_bin"]:
            raise ValueError("Input must have mm_id and mm_bin columns")
        for row in rows:
            ident, raw = row["mm_id"], row["mm_bin"].strip()
            if ident in values:
                raise ValueError(f"Duplicate geographic ID: {ident}")
            if ident not in ids:
                raise ValueError(f"Unmatched geographic ID: {ident}")
            if raw in ("", "."):
                values[ident] = None
            else:
                number = float(raw)
                if not math.isfinite(number) or number != int(number) or not 1 <= number <= nbins:
                    raise ValueError(f"Invalid bin for {ident}: {raw}")
                values[ident] = int(number)
    if not values or not any(v is not None for v in values.values()):
        raise ValueError("No nonmissing mapped observations")
    return values


def render(request):
    if request.get("schema") != 1:
        raise ValueError("Unsupported request schema")
    output = Path(request["output"]).expanduser().absolute()
    fmt = output.suffix.lower().lstrip(".")
    if fmt not in {"pdf", "svg", "png"}:
        raise ValueError("Output must end in .pdf, .svg, or .png")
    if not output.parent.is_dir():
        raise ValueError(f"Output directory does not exist: {output.parent}")
    if output.exists() and not request.get("replace", False):
        raise FileExistsError(f"Output already exists: {output}; specify replace")
    nbins = int(request["nbins"])
    labels = request["labels"]
    if not 1 <= nbins <= 32 or len(labels) != nbins or not all(isinstance(x, str) for x in labels):
        raise ValueError("Supply one legend label per bin (1–32 bins)")
    width, height, dpi = (float(request.get(k, d)) for k, d in [("width", 10), ("height", 6), ("dpi", 300)])
    if not (2 <= width <= 40 and 2 <= height <= 40 and 36 <= dpi <= 1200):
        raise ValueError("Width/height must be 2–40 inches and DPI 36–1200")
    if width * height * dpi * dpi > 100_000_000:
        raise ValueError("Requested raster size exceeds 100 million pixels")
    manifest, pack = load_pack(request["pack"])
    if request.get("geography") != manifest["geography"] or request.get("vintage") != manifest["vintage"]:
        raise ValueError("Requested geography/vintage does not match the pack")
    bins = read_bins(request["data"], {f["id"] for f in pack["features"]}, nbins)
    original_count = len(pack["features"])
    from .projections import project_pack
    pack, projection_metadata = project_pack(manifest, pack, request, bins)
    zoom = bool(request.get("zoom", False))
    selected = [f for f in pack["features"] if f["id"] in bins]
    if not selected:
        raise ValueError("None of the mapped observations is visible in this region/projection")
    visible_panels = {f["panel"] for f in (selected if zoom else pack["features"])}
    metadata = {"engine": __version__, "pack": manifest["pack_id"],
                "pack_revision": manifest["revision"], "geometry_sha256": manifest["geometry_sha256"],
                "cutoffs": request.get("cutoffs", []), "labels": labels,
                "bin_counts": [sum(v == i for v in bins.values()) for i in range(1, nbins + 1)],
                "matched": len(bins), "missing_values": sum(v is None for v in bins.values()),
                "visible_mapped": len(selected),
                "absent_features": original_count - len(bins), "zoom": zoom, **projection_metadata}
    metadata["source"] = {key: manifest[key] for key in
                          ("provider", "source_url", "source_sha256", "source_page", "license", "license_url",
                           "attribution", "vintage", "source_release", "boundary_policy", "derived_from", "membership_sha256") if key in manifest}

    # Import only after caller has supplied an isolated Matplotlib cache directory.
    import matplotlib as mpl
    mpl.use("Agg", force=True)
    from matplotlib.figure import Figure
    from matplotlib.collections import PatchCollection, LineCollection
    from matplotlib.patches import PathPatch, Patch
    from matplotlib.path import Path as MplPath
    from matplotlib.font_manager import FontProperties

    def compound(feature):
        verts, codes = [], []
        for ring in feature["rings"]:
            verts.extend(ring)
            codes.extend([MplPath.MOVETO] + [MplPath.LINETO] * (len(ring) - 2) + [MplPath.CLOSEPOLY])
        return PathPatch(MplPath(verts, codes))

    styles = dict(mpl.rcParamsDefault)
    styles.update({"font.family": "DejaVu Sans", "font.size": 10,
                   "pdf.fonttype": 42, "svg.fonttype": "path", "text.usetex": False,
                   "text.parse_math": False, "axes.unicode_minus": True,
                   "svg.hashsalt": "mapmaker-v2"})
    with mpl.rc_context(styles):
        palette = request.get("palette", "viridis")
        supplied = request.get("colors", [])
        if supplied:
            if len(supplied) != nbins:
                raise ValueError("The number of colors must equal the number of bins")
            colors = [mpl.colors.to_rgba(c) for c in supplied]
        else:
            if palette not in mpl.colormaps:
                raise ValueError(f"Unknown color scheme: {palette}")
            cmap = mpl.colormaps[palette]
            colors = [cmap(0.15 + .75 * i / max(nbins - 1, 1)) for i in range(nbins)]
        if request.get("reverse", False):
            colors.reverse()
        missingcolor = request.get("missingcolor", "#eeeeee")
        mpl.colors.to_rgba(missingcolor)
        metadata["style"] = dict(colors=[mpl.colors.to_hex(c, keep_alpha=True) for c in colors],
                                 palette=palette, missingcolor=missingcolor, width=width, height=height, dpi=dpi,
                                 title=request.get("title", ""), note=request.get("note", ""),
                                 legendtitle=request.get("legendtitle", ""),
                                 **{k: bool(request.get(k)) for k in ("nolegend", "noborders", "hatch", "rasterize", "graticule", "distortion")})
        fig = Figure(figsize=(width, height), facecolor="white", dpi=dpi)
        legend = not request.get("nolegend", False)
        map_width = .73 if legend else .94
        single = len(visible_panels) == 1
        rectangles = {"conus": [.025, .18, map_width, .70],
                      "alaska": [.035, .055, map_width * .28, .24],
                      "hawaii": [.035 + map_width * .31, .055, map_width * .18, .16],
                      "puerto_rico": [.035 + map_width * .55, .06, map_width * .17, .13]}
        any_missing = False
        other_panels = sorted(visible_panels - set(rectangles) - {"map"})
        if other_panels:
            # Fit all source territories, rather than silently dropping them.
            rectangles["conus"] = [.025, .31, map_width, .57]
            inset_panels = [p for p in ("alaska", "hawaii", "puerto_rico", *other_panels) if p in visible_panels]
            for index, panel in enumerate(inset_panels):
                rectangles[panel] = [.025 + index % 4 * map_width / 4, .04 + (1 - index // 4) * .125,
                                     map_width / 4 - .01, .11]
        from .projection_workflows import inset_settings
        inset_rectangles, captions = inset_settings(request.get("insets") or "", visible_panels)
        rectangles.update(inset_rectangles)
        metadata["panel_rectangles"], metadata["panel_captions"] = {}, {}
        for panel in ("map", "conus", "alaska", "hawaii", "puerto_rico", *other_panels):
            if panel not in visible_panels:
                continue
            rectangle = rectangles[panel] if panel in inset_rectangles else [.025, .10, map_width, .78] if single else rectangles[panel]
            metadata["panel_rectangles"][panel] = rectangle
            ax = fig.add_axes(rectangle)
            ax.set_aspect("equal")
            ax.set_axis_off()
            if pack.get("graticules", {}).get(panel):
                ax.add_collection(LineCollection(pack["graticules"][panel], colors="#aaaaaa", linewidths=.35, zorder=3))
            if pack.get("indicatrices", {}).get(panel):
                ax.add_collection(LineCollection(pack["indicatrices"][panel], colors="#ba5b37", linewidths=.55, zorder=4))
            extent_features = [f for f in (selected if zoom else pack["features"]) if f["panel"] == panel]
            bounds = [min(f["bounds"][0] for f in extent_features), min(f["bounds"][1] for f in extent_features),
                      max(f["bounds"][2] for f in extent_features), max(f["bounds"][3] for f in extent_features)]
            if pack.get("outlines", {}).get(panel) and not zoom:
                points = [p for r in pack["outlines"][panel] for p in r]
                bounds = [min(p[0] for p in points), min(p[1] for p in points), max(p[0] for p in points), max(p[1] for p in points)]
                ax.add_collection(LineCollection(pack["outlines"][panel], colors="#9eaaaa", linewidths=.5))
            dx, dy = max(bounds[2] - bounds[0], 1), max(bounds[3] - bounds[1], 1)
            # Optional context shows neighboring regions outside the sample.
            features = [f for f in pack["features"] if f["panel"] == panel and
                        (not zoom or request.get("context", False) or f["id"] in bins) and
                        f["bounds"][2] >= bounds[0] and f["bounds"][0] <= bounds[2] and
                        f["bounds"][3] >= bounds[1] and f["bounds"][1] <= bounds[3]]
            present = [f for f in features if bins.get(f["id"]) is not None]
            missing = [f for f in features if bins.get(f["id"]) is None]
            line_pack = manifest.get("geometry_type") == "line"
            if present and line_pack:
                for feature in present:
                    ax.add_collection(LineCollection(feature["rings"], colors=[colors[bins[feature["id"]]-1]], linewidths=.5))
            if missing and line_pack:
                ax.add_collection(LineCollection([r for f in missing for r in f["rings"]], colors=missingcolor, linewidths=.5))
            if present and not line_pack:
                patches = PatchCollection([compound(f) for f in present],
                    facecolors=[colors[bins[f["id"]] - 1] for f in present],
                    edgecolors="none", antialiaseds=False, rasterized=bool(request.get("rasterize", False)))
                ax.add_collection(patches)
            if missing and not line_pack:
                any_missing = True
                ax.add_collection(PatchCollection([compound(f) for f in missing],
                    facecolor=missingcolor, edgecolor="#b5b5b5" if request.get("hatch", False) else "none",
                    linewidth=0, hatch="////" if request.get("hatch", False) else None,
                    antialiaseds=False, rasterized=bool(request.get("rasterize", False))))
            def visible_lines(lines):
                if not zoom:
                    return lines
                return [line for line in lines if max(p[0] for p in line) >= bounds[0] and
                        min(p[0] for p in line) <= bounds[2] and max(p[1] for p in line) >= bounds[1] and
                        min(p[1] for p in line) <= bounds[3]]
            border_clip = None
            if zoom and not request.get("context", False) and not line_pack:
                border_clip = MplPath.make_compound_path(*[compound(f).get_path() for f in features])
            if not request.get("noborders", False) and not line_pack:
                collection = LineCollection(visible_lines(pack["borders"].get(panel, [])),
                    colors="white", linewidths=.22, antialiaseds=True)
                if border_clip is not None:
                    collection.set_clip_path(border_clip, ax.transData)
                ax.add_collection(collection)
            if request.get("states", True):
                collection = LineCollection(visible_lines(pack["state_borders"].get(panel, [])),
                    colors="#454545", linewidths=.45, antialiaseds=True)
                if border_clip is not None:
                    collection.set_clip_path(border_clip, ax.transData)
                ax.add_collection(collection)
            ax.set_xlim(bounds[0] - .015 * dx, bounds[2] + .015 * dx)
            ax.set_ylim(bounds[1] - .015 * dy, bounds[3] + .015 * dy)
            if (not single and panel != "conus") or panel in captions:
                caption = captions.get(panel, panel.replace("_", " ").title())
                metadata["panel_captions"][panel] = caption
                ax.set_title(caption, fontsize=8, color="#555555", pad=1)
        if legend:
            handles = [Patch(facecolor=colors[i], edgecolor="none", label=labels[i]) for i in range(nbins)]
            if any_missing:
                handles.append(Patch(facecolor=missingcolor, edgecolor="#b5b5b5" if request.get("hatch") else "none",
                    hatch="////" if request.get("hatch") else None, label=request.get("missinglabel", "No data")))
            legend_artist = fig.legend(handles=handles, loc="center left", bbox_to_anchor=(.78, .48),
                frameon=False, handlelength=1.4, handleheight=1.1,
                title=request.get("legendtitle", ""), fontsize=9 if nbins <= 10 else 7)
        title = request.get("title", "")
        if title:
            fig.text(.035, .96, title, va="top", fontsize=15)
        if request.get("note"):
            fig.text(.035, .015, request["note"], va="bottom", fontsize=8, color="#555555")
        if metadata.get("hidden_ids") or metadata.get("partly_visible_ids"):
            fig.text(.035, .045, "Visible portions only", va="bottom", fontsize=8, color="#555555")
        # Fail explicitly on clipped legends rather than silently exporting them.
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        canvas = FigureCanvasAgg(fig)
        canvas.draw()
        if legend:
            bb = legend_artist.get_window_extent(canvas.get_renderer())
            if bb.x1 > fig.bbox.x1 or bb.y0 < 0 or bb.y1 > fig.bbox.y1:
                raise ValueError("Legend does not fit; increase xsize()/ysize() or shorten its labels")
        meta_json = json.dumps(metadata, separators=(",", ":"))
        file_meta = ({"Creator": "Mapmaker " + __version__, "Subject": meta_json} if fmt == "pdf" else
                     {"Creator": "Mapmaker " + __version__, "Description": meta_json} if fmt == "svg" else
                     {"Software": "Mapmaker " + __version__, "Description": meta_json})
        fd, temporary = tempfile.mkstemp(prefix=".mapmaker-", suffix="." + fmt, dir=output.parent)
        os.close(fd)
        try:
            fig.savefig(temporary, format=fmt, dpi=dpi, metadata=file_meta, facecolor="white")
            if request.get("replace", False):
                os.replace(temporary, output)
            elif os.name == "nt":
                # Windows rename is atomic and refuses an existing destination;
                # unlike hard links, it also works in restricted app sandboxes.
                os.rename(temporary, output)
            else:
                # Atomic no-clobber commit, including when two invocations race.
                os.link(temporary, output)
                os.unlink(temporary)
        finally:
            Path(temporary).unlink(missing_ok=True)
            fig.clear()
    if request.get("report"):
        from .library import safe_text
        Path(request["report"]).write_text("\n".join(safe_text(s) for s in metadata.get("warnings", [])) + "\n", encoding="utf-8")
    return {"schema": 1, "ok": True, "output": str(output), **metadata}
