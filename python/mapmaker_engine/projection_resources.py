"""Explicit, hash-pinned PROJ grids; installing never changes an ordinary map."""
from contextlib import contextmanager
from contextvars import ContextVar
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import urllib.request
import warnings

NAME = re.compile(r"[A-Za-z0-9_-]+\.tif")
SELECTED = ContextVar("mapmaker_selected_grids", default=frozenset())


def catalog(root):
    path = Path(root) / "catalog/projection-grids.json"
    return json.loads(path.read_text(encoding="utf-8"))["grids"] if path.is_file() else []


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def grid_entry(root, token):
    name, _, pin = token.partition("@")
    if not NAME.fullmatch(name) or (pin and not re.fullmatch(r"[0-9a-f]{64}", pin)):
        raise ValueError("Expected a catalog grid filename, optionally @sha256")
    entry = next((e for e in catalog(root) if e["name"] == name and (not pin or e["sha256"] == pin)), None)
    if entry is None:
        raise ValueError("Grid is not in the bundled reviewed catalog with that checksum")
    return entry


def grid_path(home, entry):
    return Path(home) / "grids" / entry["sha256"] / entry["name"]


def verify(home, entry):
    path = grid_path(home, entry)
    if not path.is_file() or path.stat().st_size != entry["bytes"] or digest(path) != entry["sha256"]:
        raise ValueError(f"Grid missing or checksum failed: {entry['name']}; run mapmaker projection install {entry['name']}")
    return path


def install(root, home, token):
    entry = grid_entry(root, token)
    path = grid_path(home, entry)
    if path.exists():
        try:
            verify(home, entry)
            return entry
        except ValueError:
            pass  # Explicit reinstall repairs a corrupt copy atomically.
    license_path = Path(root) / "catalog/grid-licenses" / entry["license_file"]
    license_raw = license_path.read_bytes()
    if entry.get("license_sha256") and hashlib.sha256(license_raw).hexdigest() != entry["license_sha256"]:
        raise ValueError("Bundled grid license checksum failed; reinstall the Mapmaker bundle")
    path.parent.mkdir(parents=True, exist_ok=True)
    # Only reviewed CDN filenames are accepted, including after redirects.
    url = "https://cdn.proj.org/" + entry["name"]
    class Redirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            if newurl != url:
                raise ValueError("Unexpected PROJ grid redirect")
            return super().redirect_request(req, fp, code, msg, headers, newurl)
    fd, temporary = tempfile.mkstemp(prefix=".download-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as dest, urllib.request.build_opener(Redirect).open(url, timeout=60) as response:
            total = 0
            while chunk := response.read(1024*1024):
                total += len(chunk)
                if total > entry["bytes"]:
                    raise ValueError("PROJ grid exceeds catalog size")
                dest.write(chunk)
        if total != entry["bytes"] or digest(temporary) != entry["sha256"]:
            raise ValueError("PROJ grid checksum failed")
        from .geography_tables import atomic_bytes
        atomic_bytes(path.parent / entry["license_file"], license_raw, True)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return entry


@contextmanager
def resources(root, home, selection=""):
    import pyproj
    from pyproj import datadir, network
    bundled = Path(pyproj.__file__).parent / "proj_dir/share/proj"
    if not (bundled / "proj.db").is_file():
        raise ValueError("Bundled PROJ database is missing; reinstall the runtime")
    original = datadir.get_data_dir()
    network.set_network_enabled(False)
    entries = [grid_entry(root, item) for item in selection.split()]
    if len({e["name"] for e in entries}) != len(entries):
        raise ValueError("Select each grid once")
    with tempfile.TemporaryDirectory(prefix="mapmaker-grids-") as directory:
        for entry in entries:
            shutil.copyfile(verify(home, entry), Path(directory) / entry["name"])
        datadir.set_data_dir(str(bundled) + os.pathsep + directory)
        token = SELECTED.set(frozenset(e["name"] for e in entries))
        try:
            yield {"proj_database_sha256": digest(bundled / "proj.db"),
                   "grids": [{k: e[k] for k in ("name", "sha256", "bytes", "license")} for e in entries]}
        finally:
            SELECTED.reset(token)
            datadir.set_data_dir(original)


def inspect_operation(source, target, extent=None):
    """Choose one named, non-ballpark operation and retain its exact pipeline."""
    from pyproj.transformer import TransformerGroup
    from pyproj.aoi import AreaOfInterest
    aoi = AreaOfInterest(*extent) if extent else None
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        group = TransformerGroup(source, target, always_xy=True, area_of_interest=aoi, allow_ballpark=False)
    missing = []
    eligible = []
    for candidate in group.transformers:
        unselected = sorted({g.short_name for op in candidate.operations for g in op.grids if g.short_name not in SELECTED.get()})
        if unselected:
            missing.append(dict(operation=candidate.description, accuracy_m=candidate.accuracy, grids=unselected))
        else:
            eligible.append(candidate)
    for op in group.unavailable_operations:
        grids = [g.short_name for g in op.grids if not g.available]
        if grids:
            missing.append(dict(operation=op.name, accuracy_m=op.accuracy, grids=grids))
    if not eligible:
        return None, dict(description="No non-ballpark coordinate operation available with selected grids", best_available=False, missing_operations=missing)
    chosen = eligible[0]
    area = chosen.area_of_use
    return chosen, dict(description=chosen.description, pipeline=chosen.definition,
                        accuracy_m=chosen.accuracy, best_available=group.best_available and chosen is group.transformers[0],
                        area_of_use=dict(name=area.name, bounds=list(area.bounds)) if area else None,
                        missing_operations=missing)


def operation(source, target, extent=None):
    chosen, metadata = inspect_operation(source, target, extent)
    if chosen is None:
        missing = metadata["missing_operations"]
        detail = "; missing grids: " + ", ".join(sorted({g for op in missing for g in op["grids"]})) if missing else ""
        raise ValueError("Cannot transform: no non-ballpark coordinate operation is available for this source/destination CRS" + detail + ". Use projection preflight.")
    return chosen, metadata
