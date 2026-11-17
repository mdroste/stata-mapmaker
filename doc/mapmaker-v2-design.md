# Maintaining Mapmaker

This guide describes version 2.0.0a1. See the [README](../readme.md) for setup
and a first map, and [Stata help](../mapmaker.sthlp) for the command reference.
See the [feature, geography, and projection roadmap](mapmaker-roadmap.md) for
proposed additions, priorities, and implementation milestones.

## Source development setup

The supported installation path for users is the prepackaged bundle described
in the README. Python, Git, virtual environments, and package installation are
only needed when developing or building Mapmaker from source.

Clone the repository and enter it:

```sh
git clone https://github.com/mdroste/stata-mapmaker.git
cd stata-mapmaker
```

On Windows, run in PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe tools/prepare_legacy.py
```

On macOS or Linux:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python tools/prepare_legacy.py
```

In Stata, add the checkout to `adopath`. The launcher uses its `.venv` when no
bundled runtime is present. `python()` and `engine()` are optional development
overrides. `examples/smoke.do` and `examples/tracts.do` are source-development
examples; prepare `tract` with `tools/prepare_legacy.py tract` before running the
tract example. Bundle users can run `examples/quickstart.do` from a writable
project directory, with no runtime configuration.

## How a map is made

Stata selects observations, checks geographic IDs, and assigns values to bins.
It sends IDs, bin assignments, labels, and drawing options to a separate Python
process. Matplotlib draws the map and saves a PDF, SVG, or PNG. Rendering works
offline after dependencies and boundary files have been prepared.

| File | Role |
| --- | --- |
| `mapmaker.ado` | Preserve and restore the dataset; handle `mapmaker doctor`. |
| `_mapmaker_run.ado` | Parse options, match IDs, calculate bins, format labels, and return results. |
| `mapmaker_mata.mata` | Write the JSON request and quote command paths. |
| `_mapmaker_launch.ado` | Start the selected Python interpreter or bundled executable. |
| `_mapmaker_library.ado` | Browse, install, resolve, remove, and import geography packs without modifying Stata data. |
| `python/mapmaker_engine/cli.py` | Read the request, isolate Matplotlib settings, and report success or failure. |
| `python/mapmaker_engine/render.py` | Check inputs and boundary files, draw the figure, and save output. |
| `python/mapmaker_engine/geography.py` | Validate catalog/downloads, compile shapefiles, resolve and manage immutable revisions. |
| `python/mapmaker_engine/library.py` | Dispatch management requests and produce safe SMCL reports. |
| `python/mapmaker_engine/projections.py` | Browse bundled CRS definitions and project source coordinates offline. |
| `catalog/geographies.json` | Reviewed source URLs, hashes, sizes, join fields, and vintages. |
| `tools/prepare_legacy.py` | Convert the original boundary files into the format the renderer reads. |
| `tools/build_bundle.py` | Build and package an executable with Python and its dependencies. |

The root ado and help files define the current command. `legacy/`,
`stata_install/`, and the browser code in `src/` preserve the previous version.
Default legacy packs use boundary data from `src/geos/`. Optional dated Census
packs download verified shapefiles and compile them locally.

## Data and classification

`if` and `in` select observations before ID checks. Each selected area must
have one row. Mapmaker pads state, county, and tract IDs to 2, 5, and 11 digits,
respectively; it normalizes commuting-zone IDs to integer strings. It rejects
missing IDs, duplicate IDs, and numeric tract IDs stored as `float`.

Mapmaker matches IDs before calculating bins. An unmatched ID stops the command
unless the user specifies `unmatched(drop)`. `xtile` and `_pctile` calculate
quantile assignments and cutoffs in Stata. Custom cutoffs use the same rule:
a value equal to a cutoff belongs to the lower bin. Ties can leave bins empty.
With quantile classification, a constant sample uses one color.

System and extended missing values appear as missing on the map and do not
enter the quantiles. An entirely missing sample stops the command. Zoom fits
the view to matched selected areas, including those with missing values, and
keeps the existing bins. `context` adds surrounding areas in the missing-value
color. The wrapper restores the caller's data and sort order after success or
failure; it uses `preserve` and `restore`.

## Files exchanged with Python

Each call creates Stata temporary files for a CSV table, a JSON request, a JSON
response, and a text status. The CSV contains only `mm_id` and `mm_bin`; missing
bins use an empty field or `.`. The request uses schema version 1 and includes
file paths, geography, cutoffs, labels, colors, and output settings. The renderer
does not receive raw mapped values or the rest of the dataset.

The launcher passes the request path with `--request`. On success, Python writes
the response and a status beginning with `MAPMAKER_OK_V1`. On failure, it exits
with code 1 and, when a status path is available, writes `MAPMAKER_ERROR_V1` and
an error message. Stata reads the status and checks that the output exists.

The renderer writes to a temporary file in the destination directory, then
commits the completed file. With `replace`, it uses `os.replace`; otherwise,
it uses `os.link` to avoid overwriting a file created by another process.
The destination directory must already exist.

Graphics record the engine version, boundary revision and checksum, cutoffs,
labels, bin counts, and match counts in their metadata. Stata returns sample
counts, bins, cutoffs, output path, geography, and version information in `r()`;
the help file defines each result.

See the [geography library guide](geographies.md) for the expanded provider catalog,
source audits, membership resources, and Stata inspection commands.

## Boundary files

The original files do not establish their source or boundary dates. The code
keeps `legacy` as their identifier. Dated packs are separate catalog entries;
they never relabel the original boundaries. `vintage(2020)` with the county/state
shorthand resolves to the corresponding national 500k pack, which must be installed.

| Geography | Source in `src/geos/` | ID |
| --- | --- | --- |
| County | `counties_hr.json` | 5-digit FIPS |
| State | `usa_county_cz_zip.json` | 2-digit FIPS |
| Commuting zone | `usa_county_cz_zip.json` | Original numeric ID |
| Census tract | `tract2010_lores.json` | 11-digit GEOID |

The preparation script writes three files to `assets/<geography>-legacy/`:

- `ids.csv` lists the geographic IDs that Stata can match.
- `geometry.json.gz` stores projected polygons, bounds, and border lines.
- `manifest.json` records file hashes, projection parameters, coverage, and
  excluded IDs. The renderer checks the geometry and ID-table hashes when loading.

The script uses spherical Albers projections for the contiguous states, Alaska,
Hawaii, and Puerto Rico. It preserves polygon holes and applies no further
simplification. The state data cover 50 states, DC, and Puerto Rico. The tract
data contain 73,798 usable areas; five source features lack usable polygons.
The commuting-zone data contain 741 areas. Generated files are ignored by Git;
rebuild them with the commands in the README.

## Tests

From the repository root, after completing setup, run:

```sh
.venv/bin/python -m unittest discover -s tests -v
```

On Windows, use `.venv\Scripts\python.exe` in place of `.venv/bin/python`.
Then run these do-files in Stata from the same directory. They clear the data
in memory and write figures to `tests/output/`.

```stata
do tests/stata.do
do examples/smoke.do
do examples/tracts.do
```

The Python tests cover output formats, polygon holes, input checks, file hashes,
failed replacements, concurrent writes, and subprocess error reporting. The
Stata tests check bins, missing values, ID handling, and dataset restoration.
The examples draw county maps and 2,345 Los Angeles County tracts. Inspect their
figures for clipping, legibility, and boundary detail after rendering changes.

On November 16, 2026, source setup, all eight Python tests, the Stata tests,
and both example do-files passed on Windows x86-64 with Python 3.14.6 and
StataNow/MP 19.5 under `version 16`. The previous development record also
reports runs on macOS arm64 with Python 3.14 and StataNow 19.5. Tests on
Stata 16 itself, Linux, and standalone installations remain release tasks.

The geography-library extension subsequently passed 22 Python tests,
`tests/stata.do`, `tests/library.do`, and `tests/library_online.do` on the same
Windows/Stata environment. All 11 catalog downloads were fingerprinted, installed,
and rendered; the 119th Congress national PNG was visually inspected. The online
Stata test downloads a Census pack, maps it, and removes the test installation.
The library test checks dataset preservation across browsing, imports, successful
maps, and missing revisions. The original example results above predate this extension.

## Geography catalog and installation

`mapmaker geography browse` merges the bundled catalog, an explicitly refreshed
user catalog, and installed manifests. It shows installed/available status,
source detail, and sizes. Reports contain SMCL links built only from validated
identifiers and quoted runtime/library paths. Catalog text is escaped, never
executed. The catalog can be filtered without reading or replacing Stata data.

Defaults remain `county-legacy`, `state-legacy`, and `cz-legacy`; the tract legacy
pack is optional. `mapmaker_setup` validates existing defaults or compiles missing
ones from the source checkout. Bundles contain the three defaults already.

User packs live under `packs/<pack_id>/<revision>/` in an OS-specific user data
directory. `MAPMAKER_DATA` or `datadir()` selects another library. Resolution checks
the user library, then bundled assets, and validates geometry/ID hashes before
Stata matches observations. Revision defaults to 1 rather than a moving latest.
Removal only deletes an explicitly identified user revision inside the library.

Downloads are restricted to an explicit HTTPS provider allowlist, including
redirects and reviewed GitHub repository paths, and checked against the catalog's
SHA-256. Provider details and coverage are documented in [geographies.md](geographies.md). Download and uncompressed ZIP sizes
are bounded. ZIP sidecars are read in memory, never extracted by member path;
absolute/traversal paths and ambiguous shapefiles are rejected. Installation
stages on the destination filesystem, validates, then renames atomically.
An interruption or hash failure leaves no visible partial installation.

`geography refresh` fetches the fixed public repository catalog URL into an
atomic user cache. It retains old revisions and rejects changes to an existing
source checksum. `using()` supports reviewed local catalog updates. The online
endpoint becomes usable after this code/catalog is published; no publishing
was performed as part of implementation. Browsing uses only bundled/cached data.

Maintainers can run `tools/build_catalog.py` for the original Census sources or
`tools/expand_catalog.py --provider census` (and other provider names in the
geography guide) to audit the expanded sources. It reuses `.cache/catalog-sources/`; remove a specific cached source only
when deliberately reviewing an upstream replacement, and create a new revision.
`tools/check_catalog.py` installs those cached sources into an isolated test library
and renders each. Then run `do tests/library.do` in Stata. The separate
`do tests/library_online.do` requires network access and uses a test-only library.

## Source-coordinate geometry and projections

Schema 1 legacy packs remain fixed projected geometry. Schema 2 packs retain
source-CRS rings, IDs, and panel assignments. Their manifests include WKT,
source-sidecar hashes, the original download hash, ID rules, vintage, and revision.
The importer accepts polygon shapefiles and GeoJSON, requires CRS metadata (or an
explicit override), and rejects duplicate IDs, empty mapped features, invalid
coordinates, and missing sidecars. Catalog recipes may explicitly select a ZIP
member, filter a partition, discard Z/M coordinates, report nonspatial codes, or
dissolve/repair a reviewed source. General local imports do not silently repair
topology. Attribute and membership CSVs carry separate hashes. IDs preserve their
provider conventions and can contain up to 244 UTF-8 bytes. Native source coordinates are never
overwritten by a chosen display projection.

PROJ and its CRS database are supplied by the pinned pyproj dependency.
`projection(auto)` uses regional Albers panels for Census packs and Equal Earth
for custom packs. Explicit CRS selection uses a single panel. All Census source
territories are retained, including separate insets where present. New non-state
packs currently draw region boundaries without a separate state outline layer;
legacy/state packs supply that layer. Geographic source polygons and lines are
split at the antimeridian. More general projection-center/horizon clipping remains
future work. Older spherical CZ sources preserve their supplied projection under
auto because their datum is unnamed; a WGS84 transformation is not assumed.

Transformations use `always_xy`, disallow ballpark operations, and disable PROJ
networking. Missing specialized grids fail explicitly; grid installation remains
an advanced manual PROJ task. Output metadata records source/target WKT, selected
transformation descriptions, and PROJ/pyproj versions. Projected geometry is
currently computed per render; a bounded derived-geometry cache is a future
performance improvement. No geometry or mapped values are uploaded.

## Building an installer

The build script creates an unsigned folder containing the executable, Stata
files, boundaries, licenses, README/help, and `examples/quickstart.do`. It also
includes the maintainer guide and README image so its relative links work offline.
Run it from the repository root on each target
operating system and CPU, using a separate build environment:

```sh
python -m pip install -r requirements-build.txt
python tools/build_bundle.py --python-license /path/to/cpython/LICENSE
```

Pass `--with-tracts` to include tract boundaries; the default includes counties,
states, and commuting zones. The script checks dependency versions, collects
licenses, and creates an archive and SHA-256 file in `dist/`. Windows uses ZIP;
macOS and Linux use tar to preserve executable permissions and symlinks.

After extraction, add the bundle's top-level folder to Stata's `adopath`.
Mapmaker then selects `runtime/mapmaker-render/mapmaker-render` (`.exe` on
Windows). `engine()` selects another executable; `python()` selects a source
interpreter. A source checkout falls back to its `.venv` if no bundled executable
exists. Neither changes Stata's Python settings. `mapmaker_setup` prepares and
validates default packs; `mapmaker doctor` lists paths and bundled boundaries.
Use `mapmaker geography browse, installed` to include the user library.

The unsigned Windows amd64 bundle built successfully with the geography extension.
`tools/check_bundle.py dist/mapmaker-windows-amd64` verified its three defaults,
bundled CRS database, shapefile/GeoJSON import, date-line splitting, table export,
ERS 2020 county dissolve, and projected PNG/PDF/SVG exports through
the frozen executable. This was a development-machine check, not a clean-machine
or signed release; no standalone release has been published. Before publishing,
build and test each target on a clean machine,
choose supported OS versions, sign Windows and macOS executables, and test
archive extraction, paths with spaces, fonts, and all three output formats.
Record startup time, tract rendering time, memory use, and archive size.

The expanded geography catalog is documented in [geographies.md](geographies.md).
Further work includes additional small-area/annual editions, general crosswalk
allocation and broader county-block coverage. Projection presets, horizon/lobe
clipping, explicit datum grids, and bounded projected-geometry caching are now
documented in [projections.md](projections.md). New providers still require source
and distribution-term review. The frozen renderer includes Shapely/GEOS for seam
splitting and explicit dissolves; spreadsheet readers used to prepare historical
membership tables are build-only dependencies. Its fixed DejaVu Sans family keeps
four TTF faces and Matplotlib's required LastResort fallback; unused TTF fonts
are excluded from the bundle.

Projection checks run with `python -m unittest discover -s tests -q`,
`python tools/check_projections.py`, and `tests/projections.do` in Stata.
`tools/check_projections.py --bundle dist/mapmaker-windows-amd64` exercises every
named preset through the frozen executable, using offline cached world, ABS,
Statistics Canada, and GISCO sources. It checks three comparison formats,
recommendations, selected grid checksums, isolation from an inherited PROJ
cache/network setting, and the cache budget. Maintainer fixtures include the
optional UK OSTN15 grid; the grid is never included in the default bundle.
`tools/build_projection_catalog.py` refreshes the small reviewed horizontal-grid
catalog and provider notices without downloading grid data. Review license
changes before shipping a refreshed catalog.
