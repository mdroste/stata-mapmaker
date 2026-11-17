"""Verified, bounded offline pack exchange and explicit library maintenance."""
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import shutil
import tempfile
import zipfile

from . import geography as geo
from .geography_tables import atomic_bytes
from .render import load_pack

LIMIT = 1024*1024*1024
FILES = {"manifest.json","geometry.json.gz","ids.csv","attributes.csv","membership.csv"}


def run(request, root, home):
    action,target,revision = request["action"],request.get("target",""),request.get("revision") or "1"
    if action in {"inventory","updates"}:
        installed = []
        for path in sorted(set(list((root/"assets").glob("*/manifest.json"))+list((home/"packs").glob("*/*/manifest.json")))):
            try:
                manifest,_ = load_pack(path.parent)
                installed.append(dict(pack_id=manifest["pack_id"],revision=manifest["revision"],valid=True,path=str(path.parent)))
            except (ValueError,OSError,KeyError,json.JSONDecodeError) as error:
                installed.append(dict(pack_id=path.parent.parent.name,revision=path.parent.name,valid=False,path=str(path.parent),error=str(error)))
        updates = []
        if action == "updates":
            keys = {(e["pack_id"],e["revision"]) for e in installed if e["valid"]}
            names = {k[0] for k in keys}
            updates = [e for e in geo.read_catalog(root,home)["packs"] if e["pack_id"] in names and (e["pack_id"],e["revision"]) not in keys]
        return dict(inventory=installed,updates=updates), [f"{e['pack_id']} / {e['revision']}: {'verified' if e['valid'] else 'DAMAGED: '+e['error']}" for e in installed]+[f"Other available revision: {e['pack_id']} / {e['revision']} (explicit install; existing maps remain pinned)" for e in updates]
    if action == "export":
        path,manifest = geo.resolve(root,home,target,revision,request.get("vintage", ""))
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer,"w",zipfile.ZIP_DEFLATED) as archive:
            hashes = {}
            for file in sorted(path.iterdir()):
                if file.name not in FILES or not file.is_file():
                    continue
                data = file.read_bytes(); hashes[file.name] = hashlib.sha256(data).hexdigest()
                archive.writestr(file.name,data)
            archive.writestr("archive.json",json.dumps(dict(schema="mapmaker-pack-archive-1",files=hashes)))
        atomic_bytes(Path(request["saving"]),buffer.getvalue(),request.get("replace",False))
        return dict(path=request["saving"]), ["Exported verified offline pack. Preserve its provider attribution/license when sharing."]
    if action == "restore":
        source = Path(request["using"])
        with zipfile.ZipFile(source) as archive, tempfile.TemporaryDirectory(prefix="mapmaker-restore-") as tmp:
            names = archive.namelist()
            if len(names)!=len(set(names)) or set(names)-FILES-{"archive.json"} or sum(i.file_size for i in archive.infolist())>LIMIT:
                raise ValueError("Invalid/oversized offline archive")
            header = json.loads(archive.read("archive.json"))
            if header.get("schema") != "mapmaker-pack-archive-1" or set(header["files"]) != set(names)-{"archive.json"}:
                raise ValueError("Invalid archive inventory")
            stage = Path(tmp)
            for name,checksum in header["files"].items():
                data = archive.read(name)
                if hashlib.sha256(data).hexdigest()!=checksum:
                    raise ValueError("Archive checksum mismatch: " + name)
                (stage/name).write_bytes(data)
            manifest,_ = load_pack(stage)
            pack_id,revision = geo.token(manifest["pack_id"]),geo.token(manifest["revision"])
            existing,_ = geo.locate(root,home,pack_id,revision)
            if existing:
                actual,_ = load_pack(existing)
                if actual != manifest:
                    raise ValueError("This immutable pack revision already exists with different content")
                return dict(path=str(existing)), ["Identical verified revision already installed."]
            parent = home/"packs"/pack_id
            parent.mkdir(parents=True,exist_ok=True)
            with tempfile.TemporaryDirectory(prefix=".restore-",dir=parent) as work:
                shutil.copytree(stage,Path(work)/"pack")
                (Path(work)/"pack").rename(parent/revision)
        return dict(path=str(parent/revision)), [f"Restored {pack_id} revision {revision} offline."]
    if action == "repair":
        pack_id,revision = geo.token(target),geo.token(revision)
        path = home/"packs"/pack_id/revision
        base = (home/"packs").resolve()
        if not path.resolve().is_relative_to(base) or path.is_symlink() or path.parent.is_symlink():
            raise ValueError("Pack path escapes user library")
        entry = next((e for e in geo.read_catalog(root,home)["packs"] if (e["pack_id"],e["revision"])==(pack_id,revision)),None)
        if not entry or not path.is_dir():
            raise ValueError("Repair needs a catalog-managed user pack; restore custom packs from their archive or reinstall the bundle")
        with tempfile.TemporaryDirectory(prefix=".repair-",dir=path.parent) as work:
            backup = Path(work)/"original"
            path.rename(backup)
            try:
                geo.install(root,home,entry)
            except Exception:
                backup.rename(path)
                raise
        return dict(path=str(path)), ["Reinstalled the same pinned revision and verified its checksums."]
    raise ValueError("Unknown offline geography operation")
