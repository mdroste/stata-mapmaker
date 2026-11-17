"""Offline integration check using ZIPs downloaded by build_catalog.py."""
import argparse
import csv
from pathlib import Path
import sys
import urllib.parse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))
from mapmaker_engine.geography import install, read_catalog
from mapmaker_engine.render import render

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library", type=Path, default=ROOT / ".cache/geography-smoke/library")
    home = parser.parse_args().library.resolve()
    output = ROOT / "tests/output/library"
    output.mkdir(parents=True, exist_ok=True)
    for entry in read_catalog(ROOT)["packs"]:
        if not entry.get("source_url"):
            continue
        source = ROOT / ".cache/catalog-sources" / Path(urllib.parse.urlsplit(entry["source_url"]).path).name
        pack = install(ROOT, home, entry, source)
        data = output / (entry["pack_id"] + ".csv")
        with (pack / "ids.csv").open() as stream, data.open("w", newline="") as out:
            writer = csv.writer(out)
            writer.writerow(["mm_id", "mm_bin"])
            writer.writerows([row["mm_id"], i % 3 + 1] for i, row in enumerate(csv.DictReader(stream)))
        result = render(dict(schema=1, pack=str(pack), data=str(data), geography=entry["geography"],
                             vintage=entry["vintage"], nbins=3, labels=["One", "Two", "Three"],
                             title=entry["title"], output=str(output / (entry["pack_id"] + ".png")), replace=True))
        print(entry["pack_id"], result["matched"], "installed and rendered", flush=True)
