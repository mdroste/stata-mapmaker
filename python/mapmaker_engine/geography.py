"""Versioned, offline-first geography library and Census shapefile installer."""
import csv
import gzip
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sys
import tempfile
import urllib.parse
import urllib.request
import zipfile

TOKEN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,95}$")
MAX_DOWNLOAD = 256 * 1024 * 1024
MAX_UNPACKED = 1024 * 1024 * 1024
CATALOG_URL = "https://raw.githubusercontent.com/mdroste/stata-mapmaker/master/catalog/geographies.json"
PANELS = {"02": "alaska", "15": "hawaii", "72": "puerto_rico", "60": "samoa",
          "66": "guam", "69": "marianas", "78": "virgin_islands"}
# Explicit provider hosts; redirects are checked against the same policy.
SOURCE_HOSTS = {"www2.census.gov", "naciscdn.org", "gisco-services.ec.europa.eu",
                "www12.statcan.gc.ca", "www150.statcan.gc.ca", "www.abs.gov.au",
                "geoportal.statistics.gov.uk", "services1.arcgis.com", "services.arcgis.com",
                "open-geography-portalx-ons.hub.arcgis.com", "cdmaps.polisci.ucla.edu",
                "ers.usda.gov", "www.ers.usda.gov", "sites.psu.edu", "www.geoboundaries.org",
                "dmap-prod-oms-edc.s3.us-east-1.amazonaws.com", "prd-tnm.s3.amazonaws.com",
                "hydro.nationalmap.gov", "release-assets.githubusercontent.com", "geo.statcan.gc.ca"}
GITHUB_PATHS = {"/wmgeolab/geoBoundaries/", "/JeffreyBLewis/congressional-district-boundaries/",
                "/mdroste/stata-mapmaker/"}


def token(value):
    value = str(value)
    if not TOKEN.fullmatch(value):
        raise ValueError("Invalid pack ID or revision; use letters, digits, underscores and hyphens")
    return value


def data_home(value=None):
    if value or os.environ.get("MAPMAKER_DATA"):
        return Path(value or os.environ["MAPMAKER_DATA"]).expanduser().resolve()
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library/Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    return (base / "mapmaker").resolve()


def validate_catalog(catalog):
    if catalog.get("schema") != 1:
        raise ValueError("Unsupported geography catalog schema")
    seen = set()
    for entry in catalog["packs"]:
        if not isinstance(entry["pack_id"], str) or not isinstance(entry["revision"], str):
            raise ValueError("Catalog pack IDs and revisions must be strings")
        key = (token(entry["pack_id"]), token(entry["revision"]))
        if key in seen:
            raise ValueError("Duplicate catalog pack/revision")
        seen.add(key)
        if entry.get("source_url"):
            check_url(entry["source_url"])
            if not re.fullmatch(r"[0-9a-f]{64}", entry["source_sha256"]):
                raise ValueError("Catalog download has no valid checksum")
    return catalog


def check_revision(old, new):
    scientific_fields = ("source_sha256", "geography", "vintage", "country", "id_kind", "id_width",
                         "id_fields", "layout", "scale", "congress", "source_feature_count",
                         "format", "filter", "source_member", "id_field_widths", "recipe",
                         "geometry_type", "repair", "source_crs_override", "state_fips", "membership_sha256", "dissolve", "encoding", "skip_null_geometry", "id_method", "dimensions", "recommended_projection")
    if any(old.get(field) != new.get(field) for field in scientific_fields):
        raise ValueError("Catalog changes an immutable revision; publish a new revision instead")


def read_catalog(root, home=None):
    bundled = validate_catalog(json.loads((Path(root) / "catalog/geographies.json").read_text(encoding="utf-8")))
    cached = Path(home) / "catalog.json" if home else None
    if cached and cached.exists():
        remote = validate_catalog(json.loads(cached.read_text(encoding="utf-8")))
        # Retain bundled and older revisions so an update cannot break pinned scripts.
        entries = {(e["pack_id"], e["revision"]): e for e in bundled["packs"]}
        for entry in remote["packs"]:
            key = (entry["pack_id"], entry["revision"])
            if key in entries:
                check_revision(entries[key], entry)
            entries[key] = entry
        return dict(schema=1, updated=max(bundled["updated"], remote["updated"]), packs=list(entries.values()))
    return bundled


def refresh_catalog(root, home, source=None):
    """Only this explicit operation accesses the remote catalog; failures retain the cache."""
    if source:
        raw = Path(source).read_bytes()
    else:
        try:
            with urllib.request.urlopen(CATALOG_URL, timeout=30) as response:
                raw = response.read(16 * 1024 * 1024 + 1)
        except OSError as error:
            raise ValueError("Cannot refresh the published catalog; the bundled/cached catalog is still usable. The repository catalog must be published first.") from error
    if len(raw) > 16 * 1024 * 1024:
        raise ValueError("Catalog exceeds size limit")
    catalog = validate_catalog(json.loads(raw))
    current = read_catalog(root, home)
    entries = {(e["pack_id"], e["revision"]): e for e in current["packs"]}
    for entry in catalog["packs"]:
        key = (entry["pack_id"], entry["revision"])
        if key in entries:
            check_revision(entries[key], entry)
        entries[key] = entry
    combined = dict(schema=1, updated=max(current["updated"], catalog["updated"]), packs=list(entries.values()))
    home = Path(home)
    home.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".catalog-", dir=home)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(combined, out, indent=2)
        os.replace(temporary, home / "catalog.json")
    finally:
        Path(temporary).unlink(missing_ok=True)
    return combined


def check_url(url):
    parsed = urllib.parse.urlsplit(url)
    decoded_path = urllib.parse.unquote(parsed.path)
    if "\\" in decoded_path or any(part in {".", ".."} for part in decoded_path.split("/")):
        raise ValueError("Provider URL contains an ambiguous path")
    github = parsed.hostname in {"raw.githubusercontent.com", "media.githubusercontent.com", "github.com"}
    path = parsed.path.removeprefix("/media") if parsed.hostname == "media.githubusercontent.com" else parsed.path
    approved = parsed.hostname in SOURCE_HOSTS or (github and any(path.startswith(prefix) for prefix in GITHUB_PATHS))
    if parsed.scheme != "https" or not approved or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise ValueError("Catalog downloads must use HTTPS on a reviewed provider host/path")


class ProviderRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download(entry, destination):
    check_url(entry["source_url"])
    digest, size = hashlib.sha256(), 0
    opener = urllib.request.build_opener(ProviderRedirect)
    request = urllib.request.Request(entry["source_url"], headers={"User-Agent": "Mapmaker/2 geography installer"})
    with opener.open(request, timeout=60) as response, Path(destination).open("wb") as out:
        while chunk := response.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_DOWNLOAD:
                raise ValueError("Geography download exceeds the size limit")
            digest.update(chunk)
            out.write(chunk)
    if digest.hexdigest() != entry["source_sha256"]:
        raise ValueError("Source checksum mismatch; the provider may have revised this file. Update Mapmaker's catalog before installing.")
    if entry.get("download_bytes") and size != entry["download_bytes"]:
        raise ValueError("Source download size mismatch")


def shapefile_parts(path, member=None):
    """Read only sidecars; do not extract ZIP member paths to disk."""
    path = Path(path)
    if path.suffix.lower() != ".zip":
        if path.suffix.lower() != ".shp":
            raise ValueError("Import a .shp file or a ZIP containing one shapefile")
        return {ext: path.with_suffix("." + ext).read_bytes() for ext in ("shp", "shx", "dbf", "prj", "cpg")
                if path.with_suffix("." + ext).exists()}
    with zipfile.ZipFile(path) as archive:
        if sum(i.file_size for i in archive.infolist()) > MAX_UNPACKED:
            raise ValueError("Shapefile archive exceeds the uncompressed size limit")
        names = archive.namelist()
        for name in names:
            p = PurePosixPath(name.replace("\\", "/"))
            if p.is_absolute() or ".." in p.parts or ":" in name:
                raise ValueError("Unsafe archive member path")
        shapes = [n for n in names if n.lower().endswith(".shp")]
        if member:
            shapes = [n for n in shapes if n == member]
        if len(shapes) != 1:
            raise ValueError("Archive must contain exactly one shapefile")
        stem = shapes[0][:-4].lower()
        parts = {}
        for name in names:
            if name[:-4].lower() == stem and name[-3:].lower() in ("shp", "shx", "dbf", "prj", "cpg"):
                ext = name[-3:].lower()
                if ext in parts:
                    raise ValueError("Duplicate shapefile sidecar")
                parts[ext] = archive.read(name)
        return parts


def compile_shapefile(source, destination, entry, crs=None):
    # Compatibility entry point; supports GeoJSON as well as shapefiles.
    from .sources import compile_source
    return compile_source(source, destination, entry, crs)


def locate(root, home, pack_id, revision="1"):
    pack_id, revision = token(pack_id), token(revision or "1")
    for path in (Path(home) / "packs" / pack_id / revision, Path(root) / "assets" / pack_id):
        if (path / "manifest.json").exists():
            manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
            if manifest["pack_id"] == pack_id and str(manifest["revision"]) == revision:
                return path, manifest
    return None, None


def resolve(root, home, pack_id, revision="1", vintage=""):
    if pack_id in {"county", "state", "cz", "tract"}:
        pack_id = pack_id + "-legacy" if not vintage or vintage == "legacy" else f"us_{pack_id}_{token(vintage)}_500k"
    path, manifest = locate(root, home, pack_id, revision)
    if path is None:
        raise ValueError(f"Geography pack is missing: {pack_id}. Run mapmaker geography install {pack_id}, revision({revision or '1'})")
    if vintage and vintage != manifest["vintage"]:
        raise ValueError("Requested vintage does not match the selected geography pack")
    from .render import load_pack
    load_pack(path)  # Verify before Stata joins IDs and calculates bins.
    return path, manifest


def install(root, home, entry, source=None):
    from .render import load_pack
    pack_id, revision = token(entry["pack_id"]), token(entry["revision"])
    existing, _ = locate(root, home, pack_id, revision)
    if existing:
        load_pack(existing)
        return existing
    parent = Path(home) / "packs" / pack_id
    parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".install-", dir=parent) as work:
        work = Path(work)
        stage = work / "pack"
        if entry.get("recipe"):
            from .derived import dissolve
            dissolve(root, home, stage, entry)
        elif entry.get("source_url"):
            archive = work / "source.zip"
            if source:
                shutil.copyfile(source, archive)
                if hashlib.sha256(archive.read_bytes()).hexdigest() != entry["source_sha256"]:
                    raise ValueError("Source checksum mismatch")
            else:
                download(entry, archive)
            compile_shapefile(archive, stage, entry)
            if entry.get("membership_sha256"):
                from .derived import attach
                attach(root, stage, entry)
        elif pack_id.endswith("-legacy"):
            script = Path(root) / "tools/prepare_legacy.py"
            if not script.exists():
                raise ValueError("This legacy pack is not in the bundle. Install a dated Census pack or use a source checkout.")
            spec = importlib.util.spec_from_file_location("mapmaker_prepare_legacy", script)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.build(entry["geography"], stage)
        else:
            raise ValueError("No download source for this geography")
        load_pack(stage)
        target = parent / revision
        try:
            stage.rename(target)
        except OSError:
            if not target.exists():
                raise
            load_pack(target)  # Another installer may have completed first.
        return target


def remove(home, pack_id, revision):
    base = (Path(home) / "packs").resolve()
    target = base / token(pack_id) / token(revision)
    # Refuse symlinks/junctions escaping the library, even for a valid pack ID.
    if not target.resolve().is_relative_to(base) or target.is_symlink() or target.parent.is_symlink():
        raise ValueError("Pack path escapes the geography library")
    if not (target / "manifest.json").is_file():
        raise ValueError("No user-installed revision to remove; bundled defaults are retained")
    manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
    if manifest["pack_id"] != pack_id or str(manifest["revision"]) != revision:
        raise ValueError("Installed manifest does not match removal target")
    shutil.rmtree(target)


def installed_entries(root, home):
    entries = {}
    paths = list((Path(root) / "assets").glob("*/manifest.json")) + list((Path(home) / "packs").glob("*/*/manifest.json"))
    for path in paths:
        manifest = json.loads(path.read_text(encoding="utf-8"))
        entry = dict(manifest, installed_bytes=sum(f.stat().st_size for f in path.parent.iterdir() if f.is_file()))
        entries[(entry["pack_id"], str(entry["revision"]))] = entry
    return entries
