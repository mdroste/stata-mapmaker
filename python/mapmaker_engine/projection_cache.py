"""Bounded, disposable projected-boundary cache; never stores mapped values."""
from contextlib import contextmanager
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import time

DEFAULT_LIMIT = 64*1024*1024
FILE = re.compile(r"[0-9a-f]{64}\.json\.gz")


def key(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def directory(home):
    return Path(home) / "projection-cache"


def files(home):
    return [p for p in directory(home).glob("*.json.gz") if FILE.fullmatch(p.name) and not p.is_symlink()]


def limit(home):
    path = directory(home) / "settings.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))["limit_bytes"]
        return value if isinstance(value, int) and 0 <= value <= 1024**3 else DEFAULT_LIMIT
    except (OSError, ValueError, KeyError):
        return DEFAULT_LIMIT


@contextmanager
def lock(home):
    folder = directory(home)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / ".lock"
    acquired = False
    try:
        # A dead process may leave this advisory cache lock; no map waits for it.
        if path.exists() and time.time()-path.stat().st_mtime > 600:
            path.unlink(missing_ok=True)
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
        acquired = True
    except FileExistsError:
        pass
    try:
        yield acquired
    finally:
        if acquired:
            path.unlink(missing_ok=True)


def load(home, cache_key):
    path = directory(home) / (cache_key + ".json.gz")
    try:
        if not limit(home) or path.stat().st_size > limit(home):
            return None
        raw = gzip.decompress(path.read_bytes())
        value = json.loads(raw)
        if value["sha256"] != hashlib.sha256(value["payload"].encode()).hexdigest():
            return None
        result = json.loads(value["payload"])
        pack = result[0]
        if "_state_panels" in pack:
            panels = pack.pop("_state_panels")
            pack["borders"], pack["state_borders"] = {}, {}
            for feature in pack["features"]:
                pack["borders"].setdefault(feature["panel"], []).extend(feature["rings"])
                if feature["panel"] in panels:
                    pack["state_borders"].setdefault(feature["panel"], []).extend(feature["rings"])
        path.touch()
        return result
    except (OSError, ValueError, KeyError, EOFError):
        return None


def save(home, cache_key, pack, metadata):
    if not limit(home):
        return "bypass"
    # Borders are the same coordinates as feature rings, not a second geometry.
    compact = {k: v for k, v in pack.items() if k not in {"borders", "state_borders"}}
    compact["_state_panels"] = list(pack["state_borders"])
    payload = json.dumps([compact, metadata], separators=(",", ":"))
    raw = gzip.compress(json.dumps(dict(payload=payload, sha256=hashlib.sha256(payload.encode()).hexdigest()), separators=(",", ":")).encode(), mtime=0)
    try:
        with lock(home) as acquired:
            if not acquired or len(raw) > limit(home):
                return "bypass"
            inventory = sorted(files(home), key=lambda p: p.stat().st_mtime)
            size = sum(p.stat().st_size for p in inventory)
            while inventory and size+len(raw) > limit(home):
                path = inventory.pop(0)
                size -= path.stat().st_size
                path.unlink(missing_ok=True)
            from .geography_tables import atomic_bytes
            atomic_bytes(directory(home) / (cache_key + ".json.gz"), raw, True)
            return "miss"
    except OSError:
        return "bypass"


def manage(home, action="", mib=None):
    if action not in {"", "status", "purge", "limit"}:
        raise ValueError("projection cache accepts status, purge, or limit, limit(MiB)")
    if action in {"purge", "limit"}:
        with lock(home) as acquired:
            if not acquired:
                raise ValueError("Projection cache is busy; retry")
            if action == "limit":
                value = int(mib)
                if not 0 <= value <= 1024:
                    raise ValueError("Projection cache limit must be 0-1024 MiB")
                from .geography_tables import atomic_bytes
                atomic_bytes(directory(home)/"settings.json", json.dumps(dict(limit_bytes=value*1024*1024)).encode(), True)
            inventory = sorted(files(home), key=lambda p: p.stat().st_mtime)
            size = sum(p.stat().st_size for p in inventory)
            maximum = 0 if action == "purge" else limit(home)
            while inventory and size > maximum:
                path = inventory.pop(0)
                size -= path.stat().st_size
                path.unlink(missing_ok=True)
    return dict(bytes=sum(p.stat().st_size for p in files(home)), files=len(files(home)), limit_bytes=limit(home))
