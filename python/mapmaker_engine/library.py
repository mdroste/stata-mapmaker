"""Management operations shared by the CLI and Stata; no user data is required."""
import hashlib
import json
from pathlib import Path
import tempfile

from . import geography as geo


def safe_text(value):
    # Catalog text is data, never executable SMCL or Stata macro expansion.
    return "".join(c if c.isprintable() and c not in '{}$`\"' else " " for c in str(value))


def command_link(request, action, pack_id, revision):
    # Use only validated identifiers and safely quoted paths in generated commands.
    command = f"mapmaker geography {action} {geo.token(pack_id)}, revision({geo.token(revision)})"
    for key in ("python", "engine", "datadir"):
        value = request.get(key, "")
        if value:
            if any(c in value for c in '{}$`\"\r\n'):
                return f"[{action}: {pack_id}]"
            command += f' {key}("{value}")'
    return '{stata `"' + command + '"\':' + action + '}'


def run(request):
    if request.get("schema") != 1:
        raise ValueError("Unsupported library request schema")
    root = Path(request["root"])
    home = geo.data_home(request.get("datadir"))
    category, action = request.get("category", "geography"), request.get("action", "browse")
    target = request.get("target", "").strip().strip('"')
    revision = request.get("revision") or "1"
    result = dict(schema=1, ok=True, datadir=str(home))
    lines = []
    if category in {"style", "scale"}:
        from .figure_config import run as config_run
        details, lines = config_run(request)
        result.update(details)
    elif category in {"reproduce", "crosswalk"}:
        if category == "reproduce":
            from .reproduction import run as extra_run
        else:
            from .crosswalks import run as extra_run
        details, lines = extra_run(request, home)
        result.update(details)
    elif category == "projection":
        from .projection_workflows import run as projection_run
        details, lines = projection_run(request, home)
        result.update(details)
    elif category == "geography":
        if action in {"export", "restore", "inventory", "updates", "repair"}:
            from .offline import run as offline_run
            details, lines = offline_run(request, root, home)
            result.update(details)
            if request.get("report"):
                Path(request["report"]).write_text("\n".join(map(safe_text,lines))+"\n",encoding="utf-8")
            return result
        catalog = geo.read_catalog(root, home)
        entries = {(e["pack_id"], e["revision"]): e for e in catalog["packs"]}
        installed = geo.installed_entries(root, home)
        if action in {"browse", "search"}:
            combined = {key: dict(entry) for key, entry in entries.items()}
            for key, entry in installed.items():
                combined[key] = dict(combined.get(key, {}), **entry)
            rows = []
            query = target or request.get("search", "")
            for key, entry in combined.items():
                if request.get("installed") and key not in installed:
                    continue
                if any(request.get(option) and str(entry.get(field, "")).lower() != request[option].lower()
                       for option, field in [("country", "country"), ("level", "geography"), ("vintage", "vintage")]):
                    continue
                if request.get("state"):
                    import re
                    match = re.match(r"us_(\d{2})_", entry["pack_id"])
                    if request["state"] != entry.get("state_fips", match[1] if match else ""):
                        continue
                if request.get("provider") and request["provider"].lower() not in entry.get("provider", "").lower():
                    continue
                if request.get("decade") and (not str(entry.get("vintage", "")).isdigit() or int(entry["vintage"])//10*10 != int(request["decade"])):
                    continue
                if query and query.lower() not in json.dumps(entry).lower():
                    continue
                rows.append(dict(entry, installed=key in installed))
            rows.sort(key=lambda e: (not e["installed"], e["pack_id"], e["revision"]))
            total = len(rows)
            offset, limit = int(request.get("offset") or 0), int(request.get("limit") or 50)
            if offset < 0 or limit < 1:
                raise ValueError("offset() must be nonnegative; limit() must be positive")
            if not request.get("all"):
                rows = rows[offset:offset+limit]
            result.update(entries=rows, count=total, shown=len(rows), catalog_updated=catalog["updated"])
            lines = [f"Geography catalog: {catalog['updated']} | user library: {safe_text(home)}",
                     "Browsing and rendering work offline; geography refresh explicitly updates the catalog.",
                     "Pack / revision                  Vintage  Detail   Status       Download / installed MiB"]
            for row in rows:
                pack_id, rev = row["pack_id"], str(row["revision"])
                size = f"{row['download_bytes']/1048576:.1f}" if row.get("download_bytes") else "-"
                disk = f"{row['installed_bytes']/1048576:.1f}" if row.get("installed_bytes") else "-"
                installable = bool(row.get("source_url") or row.get("recipe")) or (row["pack_id"].endswith("-legacy") and (root / "tools/prepare_legacy.py").is_file())
                status = "installed" if row["installed"] else "available" if installable else row.get("availability", "source only")
                lines += [f"{safe_text(pack_id + '/' + rev):32} {safe_text(row['vintage']):8} {safe_text(row.get('scale', '-')):8} {status:12} {size} / {disk}",
                          f"  {safe_text(row.get('title', pack_id))}  " + command_link(request, "describe", pack_id, rev) +
                          ("  " + command_link(request, "install", pack_id, rev) if not row["installed"] and installable else "")]
            if not rows:
                lines.append("No geographies match these filters.")
            lines.append(f"Showing {len(rows)} of {total} matching packs. Use country(), level(), state(), provider(), search(), offset(), or all.")
        elif action == "refresh":
            updated = geo.refresh_catalog(root, home, request.get("using") or None)
            result["catalog_updated"] = updated["updated"]
            lines = [f"Catalog refreshed: {updated['updated']}. Installed boundaries were not changed."]
        elif action == "describe":
            key = (geo.token(target), geo.token(revision))
            entry = dict(entries.get(key, {}), **installed.get(key, {}))
            if not entry:
                raise ValueError("Unknown geography pack/revision")
            result["entry"] = entry
            lines = [f"{key}: {'installed' if key in installed else 'available'}"]
            lines += [f"{name}: {safe_text(value)}" for name, value in entry.items() if name not in {"source_crs", "projection"}]
            if entry.get("availability") == "manual":
                lines.append("Download from the provider and import locally using the documented recipe.")
            else:
                lines.append(f"Map with geography({target}) revision({revision}); id() must contain the complete geographic ID.")
            if key in installed:
                path,manifest = geo.resolve(root,home,target,revision)
                import csv
                with (path/"ids.csv").open(encoding="utf-8",newline="") as stream:
                    examples = [row["mm_id"] for _,row in zip(range(3),csv.DictReader(stream))]
                lines += ["ID examples: " + ", ".join(map(safe_text,examples)),
                          f"Runnable offline preview: mapmaker geography preview {target}, revision({revision}) saving({target}-preview.png)",
                          f"ID table: mapmaker geography ids {target}, revision({revision}) frame(map_ids)"]
        elif action == "resolve":
            path, manifest = geo.resolve(root, home, target, revision, request.get("vintage", ""))
            result.update(path=str(path), manifest=manifest)
        elif action in {"ids", "attributes", "membership", "preview", "diagnose", "verify"}:
            path, manifest = geo.resolve(root, home, target, revision, request.get("vintage", ""))
            if action == "verify":
                result.update(path=str(path), manifest=manifest)
                lines = [f"Verified {manifest['pack_id']} revision {manifest['revision']}: geometry and table checksums match."]
            else:
                from .geography_tables import inspect
                details, lines = inspect(request, path, manifest, action)
                result.update(details)
        elif action in {"install", "defaults"}:
            selected = [e for e in entries.values() if e.get("default")] if action == "defaults" else [entries.get((geo.token(target), geo.token(revision)))]
            if not all(selected):
                raise ValueError("Unknown catalog pack/revision")
            for entry in selected:
                path = geo.install(root, home, entry)
                lines.append(f"Installed: {entry['pack_id']} revision {entry['revision']} at {safe_text(path)}")
            result["installed"] = [e["pack_id"] for e in selected]
        elif action == "remove":
            geo.remove(home, target, revision)
            lines = [f"Removed user-installed {target} revision {revision}. Bundled copies, if any, remain available."]
        elif action == "import":
            pack_id = geo.token(request.get("name", ""))
            if pack_id.lower() in {"county", "state", "cz", "tract"}:
                raise ValueError("That name is reserved for a built-in geography shorthand")
            revision = geo.token(revision)
            if (pack_id, revision) in entries or (pack_id, revision) in installed:
                raise ValueError("Pack/revision already exists; choose another name or revision")
            path = Path(request.get("using", ""))
            if not path.is_file() or not request.get("idfield"):
                raise ValueError("Import requires using(filename), name(pack_id), and idfield(field)")
            parent = home / "packs" / pack_id
            parent.mkdir(parents=True, exist_ok=True)
            entry = dict(pack_id=pack_id, revision=revision, geography="custom", vintage=request.get("vintage") or "custom",
                         id_fields=[request["idfield"]], id_width=0, id_kind="string", layout="single",
                         title=pack_id, source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                         source_path=str(path.resolve()), provenance="User-imported geography")
            with tempfile.TemporaryDirectory(prefix=".import-", dir=parent) as temporary:
                stage = Path(temporary) / "pack"
                manifest = geo.compile_shapefile(path, stage, entry, request.get("crs") or None)
                from .render import load_pack
                load_pack(stage)
                stage.rename(parent / revision)
            lines = [f"Imported {pack_id}: {manifest['feature_count']} features. Use id() with string identifiers."]
        else:
            raise ValueError("Geography actions: browse, search, describe, install, remove, defaults, import, refresh, ids, attributes, membership, preview, diagnose, verify")
    else:
        raise ValueError("Unknown library category")
    if request.get("report"):
        Path(request["report"]).write_text("\n".join(lines) + "\n", encoding="utf-8")
    if request.get("resolved"):
        m = result.get("manifest", {})
        values = [result.get("path", ""), m.get("geography", ""), m.get("vintage", ""),
                  m.get("id_width", 0), m.get("id_kind", "digits"), m.get("pack_id", ""), m.get("revision", "")]
        if any("\n" in str(v) or "\r" in str(v) for v in values):
            raise ValueError("Invalid line break in resolved metadata")
        Path(request["resolved"]).write_text("\n".join(map(str, values)) + "\n", encoding="utf-8")
    return result
