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
        # Previews use the same isolated renderer configuration as user maps.
        with tempfile.TemporaryDirectory(prefix="mapmaker-mpl-") as config:
            os.environ["MPLCONFIGDIR"] = config
            os.environ["MPLBACKEND"] = "Agg"
            # Set before pyproj is imported: never consult a shared PROJ grid cache.
            os.environ["PROJ_USER_WRITABLE_DIRECTORY"] = config
            os.environ["PROJ_NETWORK"] = "OFF"
            os.environ.pop("PROJ_AUX_DB", None)
            if request.get("operation") == "library":
                from .library import run
                result = run(request)
            elif request.get("operation") == "figure":
                from .figures import render
                result = render(request)
            else:
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
