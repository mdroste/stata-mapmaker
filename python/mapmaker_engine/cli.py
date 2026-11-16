"""One request per process; communicate errors without executable output."""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

from . import __version__


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", type=Path)
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args(argv)
    if args.request is None:
        parser.error("--request is required")
    request = {}
    try:
        request = json.loads(args.request.read_text(encoding="utf-8"))
        # No inherited matplotlibrc, external fonts, or shared writable run files.
        with tempfile.TemporaryDirectory(prefix="mapmaker-mpl-") as config:
            os.environ["MPLCONFIGDIR"] = config
            os.environ["MPLBACKEND"] = "Agg"
            from .render import render
            result = render(request)
        Path(request["response"]).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        Path(request["status"]).write_text("MAPMAKER_OK_V1\n", encoding="utf-8")
        return 0
    except Exception as error:
        message = str(error).replace("\n", " ")
        print("mapmaker: " + message, file=sys.stderr)
        if request.get("status"):
            Path(request["status"]).write_text("MAPMAKER_ERROR_V1\n" + message + "\n", encoding="utf-8")
        return 1


if __name__ == "__main__":
    sys.exit(main())
