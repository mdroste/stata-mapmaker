"""Offline inspection/export without changing a Stata dataset."""
import csv
from collections import Counter
import io
import os
from pathlib import Path
import tempfile


def atomic_bytes(destination, raw, replace=False):
    destination = Path(destination).absolute()
    if not destination.parent.is_dir():
        raise ValueError("Output directory does not exist")
    fd, temporary = tempfile.mkstemp(prefix=".mapmaker-table-", dir=destination.parent)
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(raw)
        if replace:
            os.replace(temporary, destination)
        elif os.name == "nt":
            os.rename(temporary, destination)
        else:
            os.link(temporary, destination)
            os.unlink(temporary)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return str(destination)


def inspect(request, path, manifest, action):
    path = Path(path)
    if action in {"ids", "attributes", "membership"}:
        table = path / (action + ".csv")
        if not table.is_file():
            raise ValueError(f"This pack has no {action} table; older installed revisions may need reinstalling")
        if request.get("saving"):
            table = Path(atomic_bytes(request["saving"], table.read_bytes(), request.get("replace")))
        return dict(path=str(table)), [f"{action.title()} table: {table}"]
    if action == "diagnose":
        with (path / "ids.csv").open(encoding="utf-8", newline="") as stream:
            valid = {r["mm_id"] for r in csv.DictReader(stream)}
        with Path(request["data"]).open(encoding="utf-8-sig", newline="") as stream:
            input_rows = list(csv.DictReader(stream))
        if any(set(row) != {"mm_id"} for row in input_rows):
            raise ValueError("Diagnostic input must have one mm_id column")
        counts = Counter(r["mm_id"] for r in input_rows)
        rows = []
        width = manifest.get("id_width", 0)
        for ident, count in counts.items():
            suggestion = ident.strip()
            reason = ""
            if manifest.get("id_kind", "digits") == "digits" and suggestion.isdigit():
                suggestion = suggestion.zfill(width)
                if ident not in valid and width and len(ident.strip()) > width:
                    reason = f"Possible wrong geographic level: expected {width} digits"
                elif ident not in valid and suggestion not in valid:
                    reason = "Check boundary vintage, provider coverage, and geographic level"
            if suggestion != ident and suggestion in valid:
                reason = "Leading zeros or whitespace differ; suggested ID exists in this revision"
            rows.append(dict(mm_id=ident, occurrences=count, status="matched" if ident in valid else "missing" if not ident.strip() else "unmatched",
                             duplicate=int(count > 1), suggested_id=suggestion if suggestion != ident and suggestion in valid else "",reason=reason))
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, ["mm_id", "occurrences", "status", "duplicate", "suggested_id", "reason"])
        writer.writeheader()
        writer.writerows(rows)
        if not request.get("saving"):
            raise ValueError("diagnose requires saving() or frame()")
        destination = atomic_bytes(request["saving"], stream.getvalue().encode("utf-8"), request.get("replace"))
        return dict(path=destination, matched=sum(r["occurrences"] for r in rows if r["status"] == "matched"),
                    unmatched=sum(r["occurrences"] for r in rows if r["status"] != "matched"), duplicates=sum(r["occurrences"]-1 for r in rows)), [
            f"Checked {len(input_rows)} observations against {manifest['pack_id']} revision {manifest['revision']}.",
            f"Matched: {sum(r['occurrences'] for r in rows if r['status'] == 'matched')}; duplicate IDs: {sum(r['duplicate'] for r in rows)}.",
            "Suggestions are advisory. No IDs or data were changed; matching IDs do not prove vintage compatibility.",
            f"Diagnostic table: {destination}"]
    if action == "preview":
        if not request.get("saving"):
            raise ValueError("preview requires saving(filename.png/pdf/svg)")
        from .render import render
        with tempfile.TemporaryDirectory(prefix="mapmaker-preview-") as temporary:
            data = Path(temporary) / "bins.csv"
            with (path / "ids.csv").open(encoding="utf-8", newline="") as stream:
                ids = [r["mm_id"] for r in csv.DictReader(stream)]
            with data.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(["mm_id", "mm_bin"])
                writer.writerows((ident, 1) for ident in ids)
            result = render(dict(schema=1, output=request["saving"], replace=request.get("replace", False),
                data=str(data), pack=str(path), geography=manifest["geography"], vintage=manifest["vintage"],
                nbins=1, labels=["Boundary preview"], nolegend=True, width=10, height=6, dpi=120,
                title=manifest.get("title", manifest["pack_id"]), projection=request.get("projection") or "auto",
                note=manifest.get("provider", "") + "; revision " + manifest["revision"],
                **{k: request[k] for k in ("root", "datadir", "center", "region", "layout", "insets", "grids", "graticule", "distortion") if k in request}))
        return result, [f"Preview saved: {result['output']}", *result.get("warnings", [])]
    raise ValueError("Unknown inspection action")
