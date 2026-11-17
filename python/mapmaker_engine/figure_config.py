"""Versioned styles and scales. Statistical thresholds arrive from Stata."""
import csv
import io
import json
import math
from pathlib import Path

from .geography_tables import atomic_bytes

THEMES = {
    "publication": dict(fontsize=9, labelsize=7, title_size=14, background="white", missingcolor="#ededed",
                        excludedcolor="#ffffff", bordercolor="white", borderwidth=.25, outlinecolor="#444444",
                        outlinewidth=.65, legendposition="right", sequential="viridis", diverging="PuOr", categorical="tab10"),
    "grayscale": dict(fontsize=9, labelsize=7, title_size=14, background="white", missingcolor="#dddddd",
                      excludedcolor="white", bordercolor="white", borderwidth=.3, outlinecolor="black",
                      outlinewidth=.6, legendposition="right", sequential="Greys", diverging="Greys", categorical="gray"),
    "presentation": dict(fontsize=12, labelsize=10, title_size=20, background="white", missingcolor="#e5e7eb",
                         excludedcolor="white", bordercolor="white", borderwidth=.4, outlinecolor="#333333",
                         outlinewidth=.8, legendposition="bottom", sequential="cividis", diverging="BrBG", categorical="tab10"),
}
STYLE_KEYS = set(THEMES["publication"]) | {"palette", "colors", "width", "height", "dpi", "reverse", "missinglabel", "uncertainlabel"}
MODES = {"quantile", "custom", "diverging", "continuous", "categorical", "bivariate", "empty"}


def read_json(path):
    path = Path(path).expanduser()
    if path.stat().st_size > 4*1024*1024:
        raise ValueError("Configuration exceeds 4 MiB")
    return json.loads(path.read_text(encoding="utf-8"))


def style(request):
    name = request.get("style") or "publication"
    if name in THEMES:
        settings = dict(THEMES[name])
    else:
        saved = read_json(name)
        if saved.get("schema") != "mapmaker-style-1" or set(saved.get("settings", {})) - STYLE_KEYS:
            raise ValueError("Invalid style file; styles may contain appearance settings only")
        settings = dict(THEMES["publication"], **saved["settings"])
    for key in STYLE_KEYS:
        if key in {"width","height","dpi","reverse"} and not request.get(key):
            continue
        if request.get(key) not in (None, "", []):
            settings[key] = request[key]
    if settings["legendposition"] not in {"right", "bottom", "none"}:
        raise ValueError("legendposition() must be right, bottom, or none")
    for key in ("fontsize", "labelsize", "title_size"):
        value = float(settings[key])
        if not math.isfinite(value) or not 4 <= value <= 40:
            raise ValueError(f"{key} must be between 4 and 40 points")
        settings[key] = value
    for key in ("borderwidth", "outlinewidth"):
        value = float(settings[key])
        if not math.isfinite(value) or not 0 <= value <= 10:
            raise ValueError("Line widths must be between 0 and 10 points")
        settings[key] = value
    return settings


def validate_scale(scale):
    mode = scale.get("mode")
    if mode not in MODES or scale.get("interval", "upper-inclusive") != "upper-inclusive":
        raise ValueError("Unsupported scale mode or interval rule")
    for key in ("cutoffs", "cutoffs2", "limits"):
        numbers = scale.get(key, [])
        if not isinstance(numbers, list) or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in numbers):
            raise ValueError("Scale thresholds must be finite numbers")
        if any(b < a for a, b in zip(numbers, numbers[1:])):
            raise ValueError("Scale thresholds must be ordered")
    labels = scale.get("labels", [])
    if not 1 <= len(labels) <= 32 or not all(isinstance(v, str) and len(v) <= 244 for v in labels):
        raise ValueError("Scale needs 1-32 labels of at most 244 characters")
    if mode == "categorical":
        keys = scale.get("category_keys", [])
        if len(keys) != len(labels) or len(keys) != len(set(keys)) or any(not isinstance(k, str) or not k for k in keys):
            raise ValueError("Categories need unique nonempty keys and matching labels")
    elif mode == "continuous":
        limits = scale.get("limits", [])
        if len(limits) != 2 or limits[0] >= limits[1]:
            raise ValueError("Continuous limits must be finite and increasing")
    elif mode == "bivariate":
        nx, ny = len(scale.get("cutoffs", []))+1, len(scale.get("cutoffs2", []))+1
        if not 2 <= nx <= 4 or not 2 <= ny <= 4 or len(labels) != nx*ny:
            raise ValueError("Bivariate maps require 2-4 classes on each axis and a matching legend")
    elif len(labels) != len(scale.get("cutoffs", []))+1:
        raise ValueError("Scale labels do not match cutoffs")
    return scale


def save_scale(path, panels, scope, replace=False):
    scales = {p["key"] if scope == "panel" else "*": validate_scale(p["scale"]) for p in panels}
    value = dict(schema="mapmaker-scale-1", scope=scope, scales=scales)
    atomic_bytes(Path(path).expanduser().absolute(), (json.dumps(value, indent=2)+"\n").encode(), replace)


def scale_table(source, destination, replace=False):
    saved = read_json(source)
    if saved.get("schema") != "mapmaker-scale-1" or saved.get("scope") not in {"shared", "panel"}:
        raise ValueError("Invalid saved scale")
    stream = io.StringIO(newline="")
    fields = ["panel", "kind", "mode", "cutoffs", "cutoffs2", "limits", "midpoint", "nbins", "category", "code", "label", "units"]
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    for panel, scale in saved["scales"].items():
        validate_scale(scale)
        writer.writerow(dict(panel=panel, kind="config", mode=scale["mode"],
                             cutoffs=" ".join(format(v, ".17g") for v in scale.get("cutoffs", [])),
                             cutoffs2=" ".join(format(v, ".17g") for v in scale.get("cutoffs2", [])),
                             limits=" ".join(format(v, ".17g") for v in scale.get("limits", [])),
                             midpoint=scale.get("midpoint", 0), nbins=len(scale["labels"]), units=scale.get("units", "")))
        for i, label in enumerate(scale["labels"], 1):
            keys = scale.get("category_keys", [])
            writer.writerow(dict(panel=panel, kind="label", code=i, category=keys[i-1] if keys else "", label=label))
    atomic_bytes(Path(destination), stream.getvalue().encode(), replace)
    return dict(path=str(destination), scale=saved)


def run(request):
    category, action = request["category"], request["action"]
    if category == "scale":
        if action == "resolve":
            return scale_table(request["using"], request["saving"], True), []
        if action == "describe":
            saved = read_json(request.get("using") or request["target"])
            if saved.get("schema") != "mapmaker-scale-1":
                raise ValueError("Invalid saved scale")
            for scale in saved["scales"].values():
                validate_scale(scale)
            return dict(scale=saved), [json.dumps(saved, ensure_ascii=False)]
        raise ValueError("Scale actions: describe; use scalesave()/scaleuse() when mapping")
    if action in {"browse", "describe"}:
        names = [request["target"]] if request.get("target") else list(THEMES)
        settings = {name: style(dict(style=name)) for name in names}
        return dict(styles=settings), [f"{name}: {value['sequential']} / {value['diverging']} / {value['legendposition']} legend" for name, value in settings.items()]
    if action == "export":
        settings = style(dict(style=request.get("target") or "publication"))
        atomic_bytes(Path(request["saving"]), (json.dumps(dict(schema="mapmaker-style-1", settings=settings), indent=2)+"\n").encode(), request.get("replace", False))
        return dict(path=request["saving"]), ["Saved style: " + request["saving"]]
    raise ValueError("Style actions: browse, describe, export")
