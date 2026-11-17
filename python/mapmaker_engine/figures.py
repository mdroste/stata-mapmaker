"""Schema-2 research figures: preclassified panels and explicit typed layers."""
import csv
import io
import json
import math
from pathlib import Path

from . import __version__
from . import geography as geo
from .figure_config import style as resolve_style, validate_scale, save_scale
from .figure_layers import finite, point_layer, flow_layer, selected_flows, draw_points, draw_flows, place_labels, decorate
from .figure_layouts import anchor, tiled, dorling
from .geography_tables import atomic_bytes
from .render import load_pack
from .reproduction import environment


def records(request, ids, panels):
    required = {"mm_id", "mm_panel", "mm_bin"}
    allowed = required | {"mm_value", "mm_bin2", "mm_size", "mm_uncertain", "mm_label", "mm_dx", "mm_dy", "mm_highlight"}
    result = {}
    with Path(request["data"]).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not required.issubset(reader.fieldnames or []) or set(reader.fieldnames)-allowed:
            raise ValueError("Invalid schema-2 data columns; export only declared typed fields")
        for row in reader:
            key = (row["mm_panel"], row["mm_id"])
            if key in result or key[0] not in panels or key[1] not in ids:
                raise ValueError("Duplicate panel/ID or an unknown panel/geographic ID")
            scale = panels[key[0]]["scale"]
            item = dict(id=key[1], panel=key[0], label=row.get("mm_label", ""))
            for column, name in [("mm_bin", "bin"), ("mm_bin2", "bin2"), ("mm_value", "value"), ("mm_size", "size"),
                                 ("mm_uncertain", "uncertain"), ("mm_dx", "dx"), ("mm_dy", "dy"), ("mm_highlight", "highlight")]:
                raw = row.get(column, "")
                item[name] = None if raw in {"", "."} or (raw.startswith(".") and len(raw) == 2 and raw[1].isalpha()) else finite(raw, name, name == "size")
            for name in ("bin", "bin2"):
                if item[name] is not None and (item[name] != int(item[name]) or item[name] < 1):
                    raise ValueError("Class codes must be positive integers or missing")
            if scale["mode"] == "bivariate":
                nx, ny = len(scale["cutoffs"])+1, len(scale["cutoffs2"])+1
                if item["bin"] is not None and item["bin"] > nx or item["bin2"] is not None and item["bin2"] > ny:
                    raise ValueError("Bivariate class code exceeds its axis scale")
                item["bin"] = None if item["bin"] is None or item["bin2"] is None else item["bin"]+(item["bin2"]-1)*nx
            elif scale["mode"] == "empty":
                item["bin"] = None
            elif item["bin"] is not None and item["bin"] > len(scale["labels"]):
                raise ValueError("Class code exceeds its scale")
            if scale["mode"] == "continuous" and (item["value"] is None) != (item["bin"] is None):
                raise ValueError("Continuous values and class missingness must agree")
            for name in ("uncertain", "highlight"):
                if item[name] not in (None, 0, 1):
                    raise ValueError(f"{name} flags must be 0, 1, or missing")
            if len(item["label"]) > 244:
                raise ValueError("Map labels must be at most 244 characters")
            result[key] = item
    if not result:
        raise ValueError("No selected observations")
    return result


def colors(scale, settings):
    import matplotlib as mpl
    import numpy as np
    mode = scale["mode"]
    if mode == "bivariate":
        nx,ny = len(scale["cutoffs"])+1,len(scale["cutoffs2"])+1
        if settings.get("sequential")=="Greys" and settings.get("categorical")=="gray":
            return [mpl.colormaps["Greys"](v) for v in np.linspace(.08,.92,nx*ny)]
        corners = [np.array(mpl.colors.to_rgb(c)) for c in ("#f1f0e9", "#397ca8", "#c86640", "#40305d")]
        return [tuple((1-x)*(1-y)*corners[0]+x*(1-y)*corners[1]+(1-x)*y*corners[2]+x*y*corners[3])
                for y in np.linspace(0,1,ny) for x in np.linspace(0,1,nx)]
    supplied = settings.get("colors") or []
    if isinstance(supplied, str):
        supplied = supplied.replace(",", " ").split()
    if supplied:
        if len(supplied) != len(scale["labels"]):
            raise ValueError("colors() needs one color per class")
        result = [mpl.colors.to_rgba(c) for c in supplied]
    else:
        palette = settings.get("palette") or settings["categorical" if mode == "categorical" else "diverging" if mode == "diverging" else "sequential"]
        if palette not in mpl.colormaps:
            raise ValueError("Unknown palette: " + palette)
        cmap = mpl.colormaps[palette]
        n = len(scale["labels"])
        result = [cmap(i % cmap.N) for i in range(n)] if mode == "categorical" and hasattr(cmap,"colors") else [cmap(v) for v in np.linspace(.08,.92,n)]
    return result[::-1] if settings.get("reverse") else result


def compound(feature):
    from matplotlib.path import Path as MplPath
    from matplotlib.patches import PathPatch
    vertices, codes = [], []
    for ring in feature["rings"]:
        vertices.extend(ring)
        codes += [MplPath.MOVETO]+[MplPath.LINETO]*(len(ring)-2)+[MplPath.CLOSEPOLY]
    return PathPatch(MplPath(vertices,codes))


def outlines(request, manifest, projection, panels):
    if not request.get("outline"):
        return {}, []
    if request.get("layout") in {"tile", "cartogram", "dorling"}:
        raise ValueError("Geographic outline layers cannot be overlaid on a nongeographic layout; use highlight()")
    from .projections import project_pack
    output, dependencies = {}, []
    for token in request["outline"].split():
        pack_id, _, revision = token.partition("@")
        if pack_id == "states":
            pack_id = "state-legacy" if manifest["vintage"] == "legacy" else f"us_state_{manifest['vintage']}_500k"
        path, _ = geo.resolve(Path(request["root"]), geo.data_home(request.get("datadir")), pack_id, revision or "1")
        layer, geometry = load_pack(path)
        mismatch = layer["vintage"] != manifest["vintage"]
        if mismatch and not request.get("allowvintagemismatch"):
            raise ValueError("Outline vintage differs from the base map; select matching boundaries or explicitly specify allowvintagemismatch")
        dependency = {k: layer[k] for k in ("pack_id", "revision", "geometry_sha256", "vintage")}
        dependency["vintage_mismatch_acknowledged"] = mismatch
        if manifest["schema"] == 1:
            if layer["schema"] != 1 or layer.get("projection") != manifest.get("projection"):
                raise ValueError("Legacy overlays require identical documented fixed projections; use dated packs for other layers")
            for feature in geometry["features"]:
                output.setdefault(feature["panel"], []).extend(feature["rings"])
        else:
            if layer["schema"] != 2:
                raise ValueError("A fixed legacy layer cannot be transformed to a dated base map")
            for panel in panels:
                subset = [f for f in geometry["features"] if panel == "map" or f["panel"] == panel]
                if not subset:
                    continue
                projected, meta = project_pack(layer, dict(geometry, features=subset),
                    dict(request, projection=projection["target_crs"][panel], layout="single", center="", zoom=False, context=False,
                         graticule=False, distortion=False), {})
                output.setdefault(panel, []).extend(r for f in projected["features"] for r in f["rings"])
                dependency.setdefault("transformations", {})[panel] = meta["transformations"]["map"]
        dependencies.append(dependency)
    return output, dependencies


def inset_rectangles(panels):
    if len(panels) == 1:
        return {next(iter(panels)): [0,0,1,1]}
    result = {"conus": [0,.25,1,.75]}
    others = sorted(panels-{"conus"})
    for i, panel in enumerate(others):
        result[panel] = [i/max(len(others),1),0,.95/max(len(others),1),.26]
    return result


def render(request):
    if request.get("schema") != 2:
        raise ValueError("Research figures require request schema 2")
    from .projection_resources import resources
    with resources(request["root"], geo.data_home(request.get("datadir")), request.get("grids") or ""):
        return _render(request)


def _render(request):
    import matplotlib as mpl
    mpl.use("Agg",force=True)
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.collections import PatchCollection, LineCollection
    from matplotlib.patches import Patch
    from matplotlib.lines import Line2D
    from matplotlib.colors import Normalize
    from matplotlib.cm import ScalarMappable
    from pyproj import CRS
    from .projections import project_pack
    settings = resolve_style(request)
    scope = request.get("scale") or "shared"
    if scope not in {"shared", "panel"}:
        raise ValueError("scale() must be shared or panel")
    panels = request.get("panels", [])
    if not 1 <= len(panels) <= 36 or len({p["key"] for p in panels}) != len(panels):
        raise ValueError("Supply 1-36 uniquely named panels")
    for panel in panels:
        validate_scale(panel["scale"])
    if scope == "shared" and any(p["scale"] != panels[0]["scale"] for p in panels):
        raise ValueError("Shared panels must have identical resolved scales")
    manifest, source = load_pack(request["pack"])
    if manifest.get("geometry_type", "polygon") != "polygon":
        raise ValueError("Research figures require polygon packs; use the ordinary renderer for line packs")
    if request.get("geography") != manifest["geography"] or request.get("vintage") != manifest["vintage"]:
        raise ValueError("Figure geography/vintage does not match its pack")
    ids = {f["id"] for f in source["features"]}
    data = records(request, ids, {p["key"]:p for p in panels})
    universe = {ident for _,ident in data}
    nongeographic = request.get("layout") in {"tile", "cartogram", "dorling"}
    if nongeographic and any(request.get(k) for k in ("points", "outline", "graticule", "distortion", "scalebar", "northarrow", "insets")):
        raise ValueError("Nongeographic layouts support ID labels, symbols, highlights, and ID flows; geographic overlays/decorations do not apply")
    project_request = dict(request)
    if nongeographic:
        project_request.update(layout="auto", zoom=True, context=False)
    projected, projection_meta = project_pack(manifest, source, project_request, dict.fromkeys(universe,1))
    if nongeographic:
        if request["layout"] == "tile":
            projected, layout_meta = tiled(projected, request)
        else:
            baseline = request.get("cartobase") or request.get("baseline") or panels[0]["key"]
            weights = {ident: row["size"] for (key,ident),row in data.items() if key == baseline and row["size"] is not None}
            projected, layout_meta = dorling(projected, weights, request)
            layout_meta["baseline_panel"] = baseline
        projection_meta["nongeographic_layout"] = layout_meta
    geographic_panels = {f["panel"] for f in projected["features"]}
    if not geographic_panels:
        raise ValueError("No visible features")
    outline_lines, outline_dependencies = outlines(request, manifest, projection_meta, geographic_panels)
    points, point_meta = point_layer(request)
    flows, flow_meta = flow_layer(request, manifest, ids)
    facet_keys = {p["key"] for p in panels}
    if any(p["facet"] and p["facet"] not in facet_keys for p in points+flows):
        raise ValueError("A layer facet is absent from the requested panels")
    if any(p["panel"] and p["panel"] not in geographic_panels for p in points):
        raise ValueError("A point layer panel is absent from the geography layout")
    flow_max = max((r["volume"] for p in panels for r in selected_flows(flows,p["key"],request)[0]),default=1)
    request = dict(request, flow_max=flow_max)
    size_values = [r["size"] for r in data.values() if r["size"] is not None] + [p["size"] for p in points]
    size_max = max(size_values, default=1) or 1
    symbol_max = finite(request.get("symbolmax") or 500,"symbolmax",True)
    if not 1 <= symbol_max <= 10000:
        raise ValueError("symbolmax() must be 1-10,000 square points")
    columns = int(request.get("columns") or min(len(panels),3))
    if not 1 <= columns <= 6:
        raise ValueError("columns() must be 1-6")
    rows = math.ceil(len(panels)/columns)
    width = float(settings.get("width") or min(40,4.8*columns + (2.7 if scope=="shared" else 0)))
    height = float(settings.get("height") or min(40,4*rows+1))
    dpi = float(settings.get("dpi") or 200)
    if not (2 <= width <= 40 and 2 <= height <= 40 and 36 <= dpi <= 1200) or width*height*dpi*dpi > 100_000_000:
        raise ValueError("Invalid figure dimensions/DPI or raster exceeds 100 million pixels")
    output = Path(request["output"]).expanduser().absolute()
    if output.suffix.lower() not in {".png", ".pdf", ".svg"}:
        raise ValueError("Output must end in .pdf, .svg, or .png")
    outputs = [output] + [Path(request[k]).expanduser().absolute() for k in ("manifest", "scalesave", "stylesave") if request.get(k)]
    if len(set(outputs)) != len(outputs):
        raise ValueError("Figure, manifest, style, and scale outputs must have different paths")
    for path in outputs:
        if not path.parent.is_dir() or path.exists() and not request.get("replace"):
            raise ValueError(f"Output directory missing or file exists without replace: {path}")
    metadata = dict(schema="mapmaker-figure-2", engine=__version__, pack=manifest["pack_id"], revision=manifest["revision"],
                    geometry_sha256=manifest["geometry_sha256"], scale_scope=scope, classification_engine="Stata",
                    interval="upper-inclusive", weight_semantics=request.get("weight_semantics") or "pooled observations, each row equally weighted",
                    baseline=request.get("baseline") or None, panels=[], style=settings, width=width,height=height,dpi=dpi,
                    outlines=outline_dependencies, point_layer=point_meta, flow_layer=flow_meta, runtime=environment(), **projection_meta)
    metadata["source"] = {k:manifest[k] for k in ("provider","source_url","source_sha256","license","license_url","attribution","vintage") if k in manifest}
    legend_position = "none" if request.get("nolegend") else settings["legendposition"]
    right = 1-2.7/width if scope == "shared" and legend_position == "right" else .97
    bottom = .22 if scope == "shared" and legend_position == "bottom" else .10
    top = .90 if request.get("title") else .94
    panel_width, panel_height = (right-.03)/columns, (top-bottom)/rows
    axes_for_labels, legend_artists = [], []
    with mpl.rc_context(dict(mpl.rcParamsDefault, **{"font.family":"DejaVu Sans","font.size":settings["fontsize"],
        "text.usetex":False,"text.parse_math":False,"pdf.fonttype":42,"svg.fonttype":"path","svg.hashsalt":"mapmaker-figure-2"})):
        fig = Figure(figsize=(width,height),dpi=dpi,facecolor=settings["background"])
        FigureCanvasAgg(fig)
        for index, panel in enumerate(panels):
            key, scale = panel["key"], panel["scale"]
            palette = colors(scale, settings)
            values = {ident:r for (facet,ident),r in data.items() if facet == key}
            counts = dict(panel=key, matched=len(values), missing=sum(r["bin"] is None for r in values.values()),
                          absent=len(universe-set(values)), excluded=len(ids-universe), unmatched=int(panel.get("unmatched",0)),
                          visible=0, scale=scale, colors=[mpl.colors.to_hex(c) for c in palette],
                          bin_counts=[sum(r["bin"] == i for r in values.values()) for i in range(1,len(palette)+1)],
                          uncertainty_unknown=sum(r["uncertain"] is None for r in values.values()) if request.get("uncertainty") else 0)
            if scale["mode"] == "continuous":
                low,high = scale["limits"]
                counts.update(clipped_low=sum(r["value"] is not None and r["value"] < low for r in values.values()),
                              clipped_high=sum(r["value"] is not None and r["value"] > high for r in values.values()))
                cmap = mpl.colormaps[settings.get("palette") or settings["sequential"]]
                if settings.get("reverse"):
                    cmap = cmap.reversed()
                normalizer = Normalize(low,high,clip=True)
                mappable = ScalarMappable(norm=normalizer,cmap=cmap)
            else:
                mappable = None
            cell = [.03+(index % columns)*panel_width, top-(index//columns+1)*panel_height, panel_width, panel_height]
            reserve = .28 if scope == "panel" and legend_position != "none" else 0
            area = [cell[0]+.008,cell[1]+.045,cell[2]*(.97-reserve),cell[3]-.10]
            fig.text(cell[0]+.01,cell[1]+cell[3]-.015,panel.get("label",key),va="top",fontsize=settings["fontsize"]+1)
            subrects = inset_rectangles(geographic_panels)
            if request.get("insets"):
                from .projection_workflows import inset_settings
                custom, captions = inset_settings(request["insets"],geographic_panels)
                subrects.update(custom)
            else:
                captions = {}
            selected, flow_counts = selected_flows(flows,key,request)
            flow_counts["drawn_volume"] = 0
            for geo_panel in sorted(geographic_panels):
                rect = subrects[geo_panel]
                ax = fig.add_axes([area[0]+area[2]*rect[0],area[1]+area[3]*rect[1],area[2]*rect[2],area[3]*rect[3]])
                ax.set_aspect("equal"); ax.set_axis_off()
                features = [f for f in projected["features"] if f["panel"] == geo_panel]
                extent_features = [f for f in features if f["id"] in universe] if request.get("zoom") else features
                if not extent_features:
                    continue
                bounds = [min(f["bounds"][0] for f in extent_features),min(f["bounds"][1] for f in extent_features),
                          max(f["bounds"][2] for f in extent_features),max(f["bounds"][3] for f in extent_features)]
                dx,dy = max(bounds[2]-bounds[0],1),max(bounds[3]-bounds[1],1)
                ax.set_xlim(bounds[0]-.02*dx,bounds[2]+.02*dx); ax.set_ylim(bounds[1]-.02*dy,bounds[3]+.02*dy)
                patches, facecolors, missing, uncertain, unknown, highlighted, labels = [], [], [], [], [], [], []
                for feature in features:
                    ident = feature["id"]
                    row = values.get(ident)
                    if ident not in universe and request.get("zoom") and not request.get("context"):
                        continue
                    patches.append(compound(feature))
                    if ident not in universe:
                        color = settings["excludedcolor"]
                    elif row is None or row["bin"] is None:
                        color = settings["missingcolor"]; missing.append(feature)
                    elif request.get("maptype") == "symbol":
                        color = "#f0f0f0"
                    else:
                        color = mappable.to_rgba(row["value"]) if mappable else palette[int(row["bin"])-1]
                    facecolors.append(color)
                    if row:
                        counts["visible"] += 1
                        if row["uncertain"] == 1 and row["bin"] is not None:
                            uncertain.append(feature)
                        elif request.get("uncertainty") and row["uncertain"] is None and row["bin"] is not None:
                            unknown.append(feature)
                        if row["highlight"]:
                            highlighted.append(feature)
                        if row["label"]:
                            x,y = anchor(feature); labels.append((ident,row["label"],x,y,row["dx"] or 0,row["dy"] or 0))
                ax.add_collection(PatchCollection(patches,facecolors=facecolors,edgecolors="none",antialiaseds=False,rasterized=bool(request.get("rasterize"))))
                for subset,hatch in [(missing,"////"),(uncertain,"...."),(unknown,"xx")]:
                    if subset and (subset is not missing or request.get("hatch")):
                        ax.add_collection(PatchCollection([compound(f) for f in subset],facecolors="none",edgecolors="#666666",linewidths=0,hatch=hatch,zorder=3))
                if not request.get("noborders"):
                    ax.add_collection(LineCollection([r for f in features for r in f["rings"]],colors=settings["bordercolor"],linewidths=settings["borderwidth"],zorder=4))
                if request.get("states",True):
                    ax.add_collection(LineCollection(projected["state_borders"].get(geo_panel,[]),colors=settings["outlinecolor"],linewidths=settings["outlinewidth"],zorder=5))
                for lines,color,lw in [(outline_lines.get(geo_panel,[]),settings["outlinecolor"],settings["outlinewidth"]),
                                      (projected.get("graticules",{}).get(geo_panel,[]),"#aaaaaa",.3),
                                      (projected.get("indicatrices",{}).get(geo_panel,[]),"#ba5b37",.5),
                                      ([r for f in highlighted for r in f["rings"]],"#222222",1.2)]:
                    if lines:
                        ax.add_collection(LineCollection(lines,colors=color,linewidths=lw,zorder=5))
                if not nongeographic or request["layout"] == "tile":
                    symbols = [(f,values[f["id"]]) for f in features if f["id"] in values and values[f["id"]]["size"] is not None]
                    for feature,row in sorted(symbols,key=lambda fr:(-fr[1]["size"],fr[0]["id"])):
                        x,y = anchor(feature)
                        ax.scatter([x],[y],s=row["size"]/size_max*symbol_max,c="#286b8a",alpha=.65,edgecolors="white",linewidths=.35,zorder=7)
                target = CRS.from_wkt(projection_meta["target_crs"][geo_panel]) if "target_crs" in projection_meta and not nongeographic else None
                if points:
                    point_counts, point_labels = draw_points(ax,points,key,geo_panel,target,request,size_max,settings)
                    counts.setdefault("points",{})[geo_panel] = point_counts; labels.extend(point_labels)
                if selected:
                    flow_drawn = draw_flows(ax,selected,features,target,projection_meta.get("resolved_parameters",{}).get(geo_panel,{}),request,flow_max)
                    flow_counts["drawn_volume"] += flow_drawn["drawn_volume"]
                ax.apply_aspect()
                counts.setdefault("decorations",{})[geo_panel] = decorate(ax,target,features,request,settings["labelsize"])
                axes_for_labels.append((ax,labels,counts,geo_panel))
                if len(geographic_panels)>1 and geo_panel != "conus":
                    ax.set_title(captions.get(geo_panel,geo_panel.replace("_"," ").title()),fontsize=max(5,settings["labelsize"]-1),pad=0)
            if flows:
                flow_counts["omitted_volume"] = flow_counts["total_volume"]-flow_counts["drawn_volume"]
                counts["flows"] = flow_counts
                fig.text(cell[0]+.01,cell[1]+.01,f"Flows omitted: {flow_counts['omitted_volume']:g} / {flow_counts['total_volume']:g}",fontsize=settings["labelsize"])
            if not values:
                fig.text(cell[0]+cell[2]/2,cell[1]+cell[3]/2,"No observations",ha="center",fontsize=settings["fontsize"])
            metadata["panels"].append(counts)
            if legend_position != "none" and (scope == "panel" or index == 0):
                rect = [cell[0]+cell[2]*.73,cell[1]+.08,cell[2]*.25,cell[3]-.15] if scope == "panel" else ([right+.015,.18,1-right-.03,.67] if legend_position == "right" else [.07,.015,.85,.17])
                add_legend(fig,scale,palette,mappable,settings,request,rect,legend_artists,size_values,size_max,symbol_max)
        if request.get("title"):
            fig.text(.035,.98,request["title"],va="top",fontsize=settings["title_size"])
        footer = request.get("note") or ""
        if nongeographic:
            footer = "NON-GEOGRAPHIC " + ("TILE GRID" if request["layout"] == "tile" else "DORLING CARTOGRAM") + ". " + footer
            if request["layout"] != "tile":
                footer += " Circle areas use baseline panel " + projection_meta["nongeographic_layout"]["baseline_panel"] + "."
        if scope == "panel":
            footer += " Panel-specific scales."
        if footer:
            fig.text(.035,.04 if legend_position != "bottom" else .20,footer,fontsize=settings["labelsize"])
        fig.canvas.draw()
        for ax,candidates,counts,panel in axes_for_labels:
            counts.setdefault("labels",{})[panel] = place_labels(fig,ax,candidates,request.get("labellimit",50),settings["labelsize"])
        fig.canvas.draw()
        for artist in legend_artists:
            bbox = artist.get_window_extent(fig.canvas.get_renderer())
            if bbox.x0 < 0 or bbox.y0 < 0 or bbox.x1 > fig.bbox.x1+1 or bbox.y1 > fig.bbox.y1+1:
                raise ValueError("Legend does not fit; increase xsize()/ysize(), shorten labels, or change legendposition()")
        encoded = json.dumps(metadata,separators=(",",":"))
        fmt = output.suffix[1:].lower()
        file_meta = {"Subject":encoded,"Creator":"Mapmaker "+__version__} if fmt == "pdf" else {"Description":encoded}
        stream = io.BytesIO(); fig.savefig(stream,format=fmt,dpi=dpi,metadata=file_meta,facecolor=settings["background"])
        fig.clear()
        if request.get("scalesave"):
            save_scale(request["scalesave"],panels,scope,request.get("replace",False))
        if request.get("stylesave"):
            atomic_bytes(Path(request["stylesave"]), (json.dumps(dict(schema="mapmaker-style-1",settings=settings),indent=2)+"\n").encode(),request.get("replace",False))
        if request.get("manifest"):
            from .reproduction import save_manifest
            save_manifest(request,manifest,metadata)
        atomic_bytes(output,stream.getvalue(),request.get("replace",False))
    lines = [f"Panel {p['panel']}: {p['matched']} matched, {p['missing']} missing, {p['absent']} absent from panel, {p['unmatched']} unmatched, {p['excluded']} outside comparison sample." for p in metadata["panels"]]
    lines += metadata.get("warnings",[])
    if request.get("report"):
        from .library import safe_text
        Path(request["report"]).write_text("\n".join(map(safe_text,lines))+"\n",encoding="utf-8")
    if request.get("results"):
        fields = ["panel","matched","missing","absent","unmatched","excluded","visible"]
        stream = io.StringIO(newline=""); writer = csv.DictWriter(stream,fieldnames=fields,extrasaction="ignore")
        writer.writeheader(); writer.writerows(metadata["panels"])
        atomic_bytes(Path(request["results"]),stream.getvalue().encode(),True)
    return dict(ok=True,output=str(output),**metadata)


def add_legend(fig,scale,palette,mappable,settings,request,rect,artists,sizes,size_max,symbol_max):
    from matplotlib.patches import Patch, Rectangle
    from matplotlib.lines import Line2D
    import numpy as np
    import textwrap
    mode = scale["mode"]
    handles = []
    if mode == "continuous":
        ax = fig.add_axes([rect[0],rect[1]+rect[3]*.5,rect[2]*.15,rect[3]*.45])
        fig.colorbar(mappable,cax=ax,label=scale.get("units") or request.get("legendtitle") or "Value",extend="both")
    elif mode == "bivariate":
        nx,ny = len(scale["cutoffs"])+1,len(scale["cutoffs2"])+1
        ax = fig.add_axes([rect[0]+rect[2]*.12,rect[1]+rect[3]*.55,rect[2]*.75,rect[3]*.4])
        for j in range(ny):
            for i in range(nx):
                ax.add_patch(Rectangle((i,j),1,1,facecolor=palette[j*nx+i],edgecolor="white",lw=.4))
        ax.set(xlim=(0,nx),ylim=(0,ny),xticks=np.arange(1,nx),yticks=np.arange(1,ny))
        ax.set_xticklabels([f"{v:g}" for v in scale["cutoffs"]],fontsize=settings["labelsize"])
        ax.set_yticklabels([f"{v:g}" for v in scale["cutoffs2"]],fontsize=settings["labelsize"])
        ax.set_xlabel(request.get("xlegend") or "X",fontsize=settings["labelsize"])
        ax.set_ylabel(request.get("ylegend") or "Y",fontsize=settings["labelsize"])
        ax.set_aspect("equal")
    elif mode != "empty":
        handles += [Patch(facecolor=c,edgecolor="none",label=label) for c,label in zip(palette,scale["labels"])]
    handles.append(Patch(facecolor=settings["missingcolor"],hatch="////" if request.get("hatch") else None,label=settings.get("missinglabel") or ("Missing X or Y" if mode == "bivariate" else "Missing / absent")))
    handles.append(Patch(facecolor=settings["excludedcolor"],edgecolor="#aaaaaa",label="Outside sample"))
    if request.get("uncertainty"):
        handles += [Patch(facecolor="white",edgecolor="#666666",hatch="....",label=settings.get("uncertainlabel") or "Uncertain (supplied rule)"),
                    Patch(facecolor="white",edgecolor="#666666",hatch="xx",label="Uncertainty not supplied")]
    if sizes and request.get("layout") not in {"cartogram","dorling"}:
        for value in [size_max/4,size_max]:
            marker = math.sqrt(value/size_max*symbol_max)
            padding = "\n"*max(0,math.ceil(marker/(settings["fontsize"]*1.2))-1)
            handles.append(Line2D([],[],ls="",marker="o",markersize=marker,color="#286b8a",alpha=.65,label=f"Size: {value:g}"+padding))
    if request.get("flows"):
        for ratio in (.25,1):
            handles.append(Line2D([],[],color="#9d4729",linewidth=4*ratio,label=f"Flow: {request['flow_max']*ratio:g}"))
    y = rect[1]+rect[3] if mode not in {"continuous","bivariate"} else rect[1]+rect[3]*.45
    available = rect[2]*fig.get_figwidth()*72 - 35
    for handle in handles:
        handle.set_label("\n".join(textwrap.fill(line,width=max(8,int(available/(settings["fontsize"]*.53)))) for line in handle.get_label().split("\n")))
    artist = fig.legend(handles=handles,loc="upper left",bbox_to_anchor=(rect[0],y),frameon=False,
                        title=request.get("legendtitle") or scale.get("units") or "",fontsize=settings["fontsize"],
                        ncol=3 if settings["legendposition"] == "bottom" else 1)
    artists.append(artist)
