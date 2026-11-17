"""A declarative resource lock and render recipe, never an executable script."""
import hashlib
import json
from pathlib import Path

from . import geography as geo
from .figure_config import read_json
from .geography_tables import atomic_bytes


def environment():
    import sys
    import platform
    import matplotlib
    import numpy
    import pyproj
    import shapely
    return dict(python=sys.version.split()[0],platform=platform.system(),matplotlib=matplotlib.__version__,
                numpy=numpy.__version__,pyproj=pyproj.__version__,shapely=shapely.__version__,proj=pyproj.proj_version_str)


def fingerprint(root):
    root = Path(root)
    if (root / "python/mapmaker_engine").is_dir():
        files = sorted(list((root / "python/mapmaker_engine").glob("*.py")) + list(root.glob("*.ado")) + list(root.glob("*.mata")))
        digest = hashlib.sha256()
        for path in files:
            digest.update(path.relative_to(root).as_posix().encode())
            digest.update(path.read_bytes())
        return digest.hexdigest()
    info = read_json(root / "build-info.json")
    return info.get("engine_sha256", "unrecorded")


def save_manifest(request, pack, metadata):
    excluded = {"data","pack","root","datadir","response","status","report","results","output","manifest","scalesave","stylesave","python","engine","replace","style"}
    recipe = {k:v for k,v in request.items() if k not in excluded}
    layers = {}
    for key in ("points","flows","tiles"):
        path = recipe.pop(key, "")
        if path:
            layers[key] = dict(sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest(), required=True)
    recipe["style_settings"] = metadata["style"]
    packs = [{k:pack[k] for k in ("pack_id","revision","geometry_sha256","vintage")}]
    packs += [{k:d[k] for k in ("pack_id","revision","geometry_sha256","vintage")} for d in metadata.get("outlines",[])]
    value = dict(schema="mapmaker-reproduction-1", engine_sha256=fingerprint(request["root"]), engine=metadata["engine"],
                 packs=packs, recipe=recipe, figure_metadata=metadata, layers=layers,
                 classified_input_sha256=hashlib.sha256(Path(request["data"]).read_bytes()).hexdigest(),
                 contains_observation_data=False,
                 instructions="Retain the original Stata do-file/data. Verify or explicitly restore resources, then rerun with these pinned scales/settings. Observation values, labels, point coordinates and flows are not stored here.")
    atomic_bytes(Path(request["manifest"]), (json.dumps(value,indent=2,ensure_ascii=False)+"\n").encode(),request.get("replace",False))


def run(request, home):
    from .projection_resources import catalog as grid_catalog, install as grid_install, grid_path
    root = Path(request["root"])
    value = read_json(request.get("using") or request["target"])
    if value.get("schema") != "mapmaker-reproduction-1":
        raise ValueError("Unsupported reproduction manifest")
    if request["action"] not in {"describe","verify","restore"}:
        raise ValueError("Reproduce actions: describe, verify, restore")
    if request["action"] == "describe":
        return dict(manifest=value), [value["instructions"], f"Pinned packs: {len(value['packs'])}; private layers required again: {', '.join(value['layers']) or 'none'}"]
    entries = {(e["pack_id"],e["revision"]):e for e in geo.read_catalog(root,home)["packs"]}
    for pack in value["packs"]:
        if request["action"] == "restore" and geo.locate(root,home,pack["pack_id"],pack["revision"])[0] is None:
            entry = entries.get((pack["pack_id"],pack["revision"]))
            if not entry:
                raise ValueError("Pinned custom/retired pack must be restored from an offline archive: " + pack["pack_id"])
            geo.install(root,home,entry)
        _, actual = geo.resolve(root,home,pack["pack_id"],pack["revision"])
        if actual["geometry_sha256"] != pack["geometry_sha256"] or actual["vintage"] != pack["vintage"]:
            raise ValueError("Pinned geography differs: " + pack["pack_id"])
    grids = {e["name"]:e for e in grid_catalog(root)}
    selected = value["figure_metadata"].get("grids", [])
    for pinned in selected:
        name = pinned["name"]
        if name not in grids or grids[name]["sha256"] != pinned["sha256"]:
            raise ValueError("Pinned grid is absent from this catalog: " + name)
        if request["action"] == "restore":
            grid_install(root,home,name+"@"+pinned["sha256"])
        path = grid_path(home,grids[name])
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != grids[name]["sha256"]:
            raise ValueError("Pinned grid is absent or damaged: " + name)
    same_engine = value["engine_sha256"] == fingerprint(root)
    same_engine = same_engine and value["figure_metadata"].get("runtime")==environment()
    if value["figure_metadata"].get("proj_database_sha256"):
        import pyproj
        database = Path(pyproj.__file__).parent/"proj_dir/share/proj/proj.db"
        same_engine = same_engine and hashlib.sha256(database.read_bytes()).hexdigest()==value["figure_metadata"]["proj_database_sha256"]
    if request["action"] == "verify" and not same_engine:
        raise ValueError("Resources verified, but engine code differs. Use the recorded bundle for exact reproduction.")
    return dict(verified=True,engine_match=same_engine), ["Pinned geography/grid resources verified.",
        "Engine matches." if same_engine else "Engine differs: retain the original bundle for exact reproduction.",value["instructions"]]
