"""Build an unsigned platform-specific development bundle; does not publish.

Install requirements-build.txt in a clean environment first. Run on each target
OS/architecture. A release still requires signing and clean-machine validation.
"""
import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import platform
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
FILES = ["mapmaker.ado", "_mapmaker_run.ado", "_mapmaker_launch.ado", "mapmaker_mata.mata",
         "mapmaker.sthlp", "mapmaker_setup.ado", "LICENSE", "readme.md"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--with-tracts", action="store_true")
    parser.add_argument("--python-license", type=Path, required=True,
                        help="Full CPython license from the interpreter's source distribution")
    args = parser.parse_args()
    if not args.python_license.is_file():
        parser.error("--python-license must point to an existing license file")
    if importlib.util.find_spec("PyInstaller") is None:
        parser.error("PyInstaller is missing; install requirements-build.txt in the build environment")
    target = platform.system().lower() + "-" + platform.machine().lower()
    stage = ROOT / "dist" / ("mapmaker-" + target)
    if stage.exists():
        parser.error(f"{stage} exists; move it aside before building")
    geographies = ["county", "state", "cz"] + (["tract"] if args.with_tracts else [])
    subprocess.run([sys.executable, str(ROOT / "tools/prepare_legacy.py"), *geographies], check=True)
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm",
                    "--workpath", str(ROOT / "build/freezer"), "--distpath", str(ROOT / "build/runtime"),
                    str(ROOT / "tools/mapmaker.spec")], check=True, cwd=ROOT)
    binary = ROOT / "build/runtime/mapmaker-render"
    executable = binary / ("mapmaker-render.exe" if platform.system() == "Windows" else "mapmaker-render")
    subprocess.run([str(executable), "--version"], check=True)
    stage.mkdir(parents=True)
    for name in FILES:
        shutil.copy2(ROOT / name, stage / name)
    shutil.copytree(binary, stage / "runtime/mapmaker-render", symlinks=True)
    for geo in geographies:
        shutil.copytree(ROOT / "assets" / (geo + "-legacy"), stage / "assets" / (geo + "-legacy"))
    notices = stage / "licenses"
    notices.mkdir()
    shutil.copy2(args.python_license, notices / "CPython-LICENSE.txt")
    dependencies = {}
    for line in (ROOT / "requirements.txt").read_text().splitlines():
        if not line or line.startswith("#"):
            continue
        name, expected = line.split("==")
        dist = importlib.metadata.distribution(name)
        if dist.version != expected:
            raise RuntimeError(f"Dependency lock mismatch: {name} {dist.version}, expected {expected}")
        dependencies[name] = dist.version
        found = []
        for file in dist.files or []:
            if any(word in str(file).lower() for word in ("license", "copying", "notice")):
                source = Path(dist.locate_file(file))
                if source.is_file():
                    relative = Path(file)
                    if relative.is_absolute() or ".." in relative.parts:
                        relative = Path(source.name)
                    destination = notices / name / relative
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, destination)
                    found.append(str(file))
        if not found:
            raise RuntimeError(f"No license collected for {name}; inspect its installed distribution")
    (stage / "build-info.json").write_text(json.dumps({"python": sys.version, "target": target,
        "dependencies": dependencies, "signed": False, "clean_machine_tested": False}, indent=2) + "\n")
    # tar preserves POSIX symlinks and executable permissions. Windows bundles use ZIP.
    archive = shutil.make_archive(str(stage), "zip" if platform.system() == "Windows" else "gztar",
                                 root_dir=stage.parent, base_dir=stage.name)
    digest = hashlib.sha256(Path(archive).read_bytes()).hexdigest()
    Path(archive + ".sha256").write_text(digest + "  " + Path(archive).name + "\n")
    print(f"Built unsigned development bundle: {archive}")


if __name__ == "__main__":
    main()
