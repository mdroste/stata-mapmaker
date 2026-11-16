# Mapmaker rewrite

Design proposal, November 16, 2026. The public command remains `mapmaker`.
This document specifies the target architecture. A working source alpha now
implements the Stata front end, direct renderer, legacy pack compiler, and
regression tests. See `readme.md` for the current implementation and limitations;
the binary release and verified geography targets below remain incomplete.

## Recommendation

Build a Stata front end and a self-contained Python rendering executable.
Bundle the Python interpreter, Matplotlib, its required dependencies, and fonts.
Use prepared geographic assets so ordinary map rendering needs no GIS software.
Users should install Mapmaker once and then produce maps offline, without
configuring Python, running pip, or installing a browser.

The initial product is publication-quality static choropleths, with particular
attention to census tracts, consistent with the existing command's purpose.
PDF, SVG, and PNG are first-class outputs. Stata 16 is the proposed minimum;
the front end can use private frames even though the default execution path
does not depend on Stata's Python integration.

Stata's Python integration remains a possible development adapter. It should
not determine the end-user dependency model. Vendoring Python packages into
an ado directory does not supply the interpreter or resolve compiled-extension
compatibility with a user's Python. A frozen executable avoids that dependency
on the user's environment [1–3]. It runs outside Stata, so it cannot use `sfi`
to access Stata's live data; the front end must serialize its inputs.

## Findings from the existing implementation

The current route is Stata → CSV → Python → D3-generated SVG in PhantomJS →
image. The example image demonstrates the features worth preserving: crisp
boundaries, a compact legend, missing-data hatching, and Alaska/Hawaii insets.

| Finding | Evidence | Consequence for the rewrite |
| --- | --- | --- |
| Platform-dependent browser distribution | `src/bin` occupies approximately 89 MiB; `mac.phantomjs` is an Intel x86-64 Mach-O executable. Python sends all non-Windows platforms to that executable. | Provide explicit platform builds and eliminate the browser from static rendering. |
| Shared mutable run files | Stata exports `temp/temp`t'.csv`, but does not define `t`; Python overwrites `filepaths.js` and `map_settings.json`. | Give every invocation a private temporary workspace; treat installed code and map packs as read-only. |
| Silent duplicate-ID replacement | `csvDataDict[d[csv_id_col]] = ...` in both HTML templates. | Require one observation per normalized geographic ID after `if`/`in`. |
| Classification differs from the help file | The help claims `xtile` behavior; the implementation uses `d3.scale.quantile()` and right-bisect threshold assignment. | Calculate cutoffs and bin assignments in Stata and pass both to the renderer. |
| Zoom changes the geographic universe | `generatePathsFileFromTemplate()` switches from `usa_county_cz_zip.json` to `_2.json`. Those files contain 3,212 and 3,143 counties, respectively. Their ID sets differ in both directions. | A change in viewport must not silently change geographic vintage or coverage. |
| Fragile export and failure handling | `rasterize.js` waits a fixed 200 ms before capture. Python prints renderer failure without propagating a nonzero exit status. | Render synchronously and return structured success/failure information. |
| Mutable installation source | Setup downloads an archive from the `master` branch and runs `chmod 777` on the Mac browser. | Install immutable, versioned releases using ordinary permissions and platform signing. |
| Distribution drift | Root and installation copies of the ado differ; the package manifest omits the help file. | Generate distribution files from a single source tree. |

The source directory occupies approximately 211 MiB, including 119 MiB of
geography, and the installation archive is approximately 69 MiB compressed.
These are measurements of this checkout, not estimates for the replacement.

The classification discrepancy was checked using the installed StataNow 19.5
under `version 16`. For values 1, 2, 3, 4, 5, Stata's quartile assignments are
1, 1, 2, 3, 4. The checked-in D3 code gives 1, 2, 3, 4, 4: both have thresholds
2, 3, 4, but treat equality differently. The percentile estimators also differ
in general, as can be seen directly in the bundled `d3.quantile` formula.
This was a targeted statistical check, not a complete run of the legacy renderer.

## Alternatives

| Architecture | User setup | Maintenance implications | Assessment |
| --- | --- | --- | --- |
| Native Stata/Mata drawing | Stata and map assets | Most straightforward distribution; native graph objects. Existing `geoplot` also has separately installed ado/Mata dependencies [4]. | A credible alternative if `.gph` editing and Stata graph composition are primary requirements. Benchmark before dismissing it on speed or appearance. |
| Stata Python integration with vendored packages | A compatible Python installation and Stata configuration | Native wheels vary by operating system, CPU, and Python ABI; shared interpreter imports can conflict. | Suitable for development or an explicitly supported expert mode. |
| Frozen Python with Matplotlib | Mapmaker's platform bundle | Release engineering moves to the maintainer; one tested interpreter and dependency set per platform. | Recommended default. |
| D3 with bundled Chromium | A browser/runtime bundle supplied by Mapmaker | Browser lifecycle, subprocesses, fonts, asynchronous rendering, and a larger runtime surface. | Reconsider for a future interactive HTML product. |
| Custom SVG engine with a native conversion tool, or a Rust renderer | Mapmaker's platform bundle | Potentially smaller; requires more work on text, layout, projection, clipping, and multiple output formats. | Reconsider only if measured bundle size or startup time makes Python unsuitable. |

A frozen application still relies on supported operating-system facilities.
It removes separately installed application dependencies; it does not guarantee
execution on every OS version or on machines that prohibit external executables.
The outputs will be external graphics, without Stata Graph Editor support.

## Division of responsibility

| Component | Responsibility |
| --- | --- |
| `mapmaker.ado` and small private helpers | Syntax, sample selection, ID validation, geography lookup, classification, legend-number formatting, export policy, `r()` results, and error reporting. |
| Python core and Matplotlib renderer | Validate the request, load prepared paths, compose the map and legend, render PDF/SVG/PNG, and report output metadata. |
| Geography build tools | Acquire source boundaries, validate them, resolve IDs, simplify shared borders, project, prepare inset layouts, and generate immutable map packs. |
| Release tooling | Lock dependencies, build executables, bundle fonts/licenses, package assets, sign releases, and test installations on clean machines. |

Keep a small core that accepts ordinary data structures and has no dependency
on `sfi`. The executable adapter is the production entry point. An optional SFI
adapter can later feed the same request structure during development; it must
not silently select a different rendering engine or alter global Python settings.

### Stata behavior

1. Apply `if` and `in` in a private frame without dropping observations merely
   because the mapped value is missing.
2. Normalize identifiers according to the chosen pack's schema. Preserve strings
   and leading zeros. Accept integer numeric FIPS where representation is safe;
   refuse numeric tract IDs stored as Stata `float`, which cannot reliably
   preserve 11-digit codes. Converting an already rounded ID to `double` cannot
   repair it. Custom identifiers remain strings unless their schema says otherwise.
3. Validate uniqueness after normalization and fail on duplicate or missing IDs.
   Do not infer an aggregation rule for repeated observations.
4. Match against the pack's small ID table before calculating quantiles. Fail
   on unmatched selected IDs by default, with examples and a count. An explicit
   `unmatched(drop)` option may exclude them and report the exclusion.
5. Use `xtile`/`_pctile` for quantiles. For explicit cutoffs, use the same
   upper-inclusive convention: `x <= c1`, `c1 < x <= c2`, and so on. Retain
   requested bin identities and report empty bins caused by ties; never split
   identical values to manufacture equal counts. Reject non-increasing custom
   cutoffs. Weighted and alternative classifiers can be added with defined semantics.
6. Treat `.`, `.a`, …, `.z` as missing mapped values. Keep missing and valid zero
   distinct. Fail clearly on an entirely missing classification sample; allow a
   one-valued sample to produce a single-color map with an explicit message.
7. Separate sample, display, and extent. `if`/`in` determine the data and quantile
   sample; display options choose the geographic canvas; zoom changes the
   viewport. Cropping must not recompute bins. Missing-valued selected regions
   must not disappear from the extent without an explicit option.
8. Return cutoffs, bin counts, matched/unmatched counts, missing counts, output
   paths, engine version, and exact geography-pack version in `r()`.

The default map can show boundary features without a corresponding data row in
the missing-data style, while reporting absent rows separately from observed
rows with missing values. Explicit cutoffs make comparisons across panels and
years reproducible. The legend uses the actual cutoffs and interval convention;
rounding labels must not make distinct boundaries indistinguishable.

### Process and file contract

Use a versioned request document for styles, pack identity, paths, and output
settings, plus a small UTF-8 table of canonical ID, bin number, and missing-data
status. Do not export the user's full dataset. Include raw values only when a
requested feature needs them. Data transfer at one row per geographic unit is
unlikely to justify complicating installation for an in-process bridge; measure
it in the tract benchmark.

Pass only the generated request path to the executable. Encode user text in the
request with a real serializer rather than assembling executable Python or shell
source. Test quoting of the executable/request paths on Windows and POSIX,
including spaces and shell metacharacters. Supply a unique request ID and private
response path so an old output cannot be mistaken for a successful new run.

Use unique temporary files and always clean up on success or failure. Export to
a temporary sibling of the requested output and commit only after successful
rendering; preserve existing files unless `replace` was specified. The renderer
returns an exit status and structured diagnostics; Stata checks both the response
and the output. Never execute a renderer-generated do-file to obtain results.

The implementation must restore the user's frame, data, sort order, and settings
after errors, and need not change the working directory. Support simultaneous
Stata sessions. Provide `nodisplay` for batch work; preview through the operating
system only after the output has been verified.

## Rendering and appearance

Use Matplotlib's direct PDF and SVG backends and Agg for PNG [5]. Bundle all
required transitive dependencies [6], but exclude unused GUI backends after
testing. Built-in fonts and default styles should be isolated from the user's
Matplotlib configuration. External TeX is unnecessary for the default typography.

Prepared polygon paths, compound rings, and batched path/line collections are
sufficient for stock choropleths. Preserve holes, islands, and multipart regions.
Draw shared borders once, with separate styles for county and state outlines.
Verify raster seams and clipping in real exports. Use explicit layout for the
legend and insets, maintaining the existing command's compact appearance.

Default to five bins and a perceptually ordered sequential palette. Keep
ColorBrewer choices and explicit colors available, with diverging palettes for
signed quantities. Add a documented legacy style for users who want the older
ten-bin appearance, without claiming identical historical classification.

Support physical figure size and PNG DPI separately. Bundle licensed serif and
sans-serif fonts, subset/embed PDF fonts, and define SVG text handling explicitly.
Offer text-as-paths for portable SVG appearance and editable text as an option.
For very detailed tract maps, permit polygon rasterization within a PDF while
retaining vector labels and legend. Full vector output remains available.

## Geography as a versioned asset

Source provenance and vintage are part of the statistical specification. A pack
should contain a manifest, canonical ID table, projected geometry, shared-border
meshes, feature bounds, and several documented levels of detail. Record source
URLs, source checksums, boundary date, ID schema, projection, coverage, exclusions,
simplification parameters, attribution, and pack-format version. Quantization and
simplification must have a stated tolerance and preserve shared topology.

Use official Census cartographic boundary files for national thematic maps where
their simplification is appropriate [7]. Use more detailed source material for
close tract views. The build environment can contain GDAL, PROJ/pyproj,
Shapely/GEOS, and topology tools. Those tools need not ship to ordinary users.

For the first release, prepare projected coordinates for the supported layouts:
CONUS Albers, Alaska, Hawaii, and explicit national inset placement. A national
inset layout is a composition of separate projections. A local Alaska view must
use its geographic panel coordinates, not its scaled inset position. Other
territories require explicit coverage and layout rules. Keep geographic
coordinates in the reproducible source assets for subsequent pack builds.

Zoom can select bounds and a finer prepared level of detail without a runtime
projection library. Arbitrary user-selected projections, spatial dissolves,
crosswalks, and unrestricted shapefile import would require additional geometry
processing. Treat these as separate features. Initially, accept custom geography
through a documented pack-building workflow; do not promise general GIS import
with the minimal renderer.

Bundle a modest state/county starter pack. Distribute tracts, PUMAs, ZCTAs, and
commuting zones separately, with tract packs partitioned by state. Allow explicit
one-time downloads and installation from local archives for offline machines.
Mapmaking itself does not contact the network. Pins remain valid after new
releases; an unqualified geography alias resolves to a documented fixed default
for the installed release and reports its resolved version.

Audit the old assets before reuse. In particular, establish the original source
and vintage of the 741 commuting zones, and verify the old ZIP layer. New ZIP-area
support should be named ZCTA where that is what the source represents [8]. Never
silently reinterpret a postal ZIP code or crosswalk boundaries across vintages.

## Distribution

Start with PyInstaller one-folder builds: a single archive is downloaded and
installed once, then its executable runs in place [2]. One-file builds unpack at
each launch and complicate restricted temporary directories. The user need not
interact with the files inside either kind of bundle.

Target native macOS arm64 and x86-64, Windows x86-64, and Linux x86-64 builds.
Declare minimum supported OS versions and test each target; decide other CPU
targets from demand. Build Linux against a deliberately chosen older supported
glibc baseline. PyInstaller builds are platform-specific [3].

Use signed/notarized Mac releases and signed Windows releases for distribution.
PyInstaller's automatic ad-hoc Mac signing is not a substitute for release
signing [9]. Preserve symlinks and executable permissions when packaging and
extracting POSIX builds [10]; do not assume Stata's `unzipfile` preserves them.
A tested OS-native extraction path or a verified alternative bundle layout is a
release requirement. Ordinary users should not be asked to disable OS security.

Keep `mapmaker_setup` as a bootstrap helper if needed. Stata's normal package
installation supplies the ado/help files; setup installs the exact supported
runtime and starter assets in a writable per-user location. Setup must work when
Python is absent: OS/CPU detection, archive extraction, and initial checksum
verification cannot depend on the runtime it is about to install. Validate that
bootstrap on every target, using an audited native/Stata implementation or
available OS facilities. Test downloads and offline archives through the same
verification path. Pin release hashes and fail without replacing an existing
installation if verification or extraction fails.

Provide `mapmaker doctor` to report the selected ado, runtime path/version,
platform support, asset availability, and an actual tiny export test. Keep
runtime versions side by side and change the active version only after a smoke
test. Do not automatically upgrade when producing a map. Generate the package
manifest and installed ado/help files from one source of truth. Include the
licenses for the interpreter, libraries, fonts, and redistributed data.

## Proposed command surface

The syntax below is illustrative and is not implemented yet. Preserve familiar
options where their meaning is sound; keep `geovar()`/`id()` and
`savegraph()`/`saving()` as aliases. Use `vintage()` to identify boundary vintage
and a pack revision in metadata to identify subsequent corrections.

```stata
mapmaker income, geography(county) vintage(2020) id(county_fips) ///
    nquantiles(5) colorscheme(viridis) saving("income.pdf") replace

mapmaker poverty if state_fips == 6, geography(tract) vintage(2020) ///
    id(tract_geoid) zoomtoregion cutvalues(10 20 30 40) ///
    saving("california.svg") replace

mapmaker doctor
```

Provide a versioned legacy release for replication. The new command should not
claim bit-for-bit compatibility: corrected bins, audited boundaries, font
metrics, and default styling can change a figure. Avoid carrying forward
experiment-specific switches such as `maurice` into the main interface.

## Implementation sequence and acceptance criteria

1. **Packaging and rendering experiment.** Build a frozen renderer and invoke it
   from a minimal ado on clean Mac and Windows installations without Python.
   Export one county map and one dense tract map to all three formats. Measure
   cold/warm startup, transfer time, peak memory, archive size, export time, and
   file size. Exercise signing, archive extraction, fonts, path quoting, and
   failure reporting. This resolves the main architecture risk before expanding
   the option surface. Include a native Stata comparison for the same figures.
2. **Usable county/state command.** Implement the request contract, validation,
   Stata classifications, prepared starter assets, legends, insets, missing data,
   and atomic exports. Test leading zeros, duplicate IDs, extended missing values,
   equal cutoffs, ties, constant samples, all-missing samples, bad destinations,
   non-ASCII paths, simultaneous runs, and unchanged caller state after failure.
3. **Fine geography and replication.** Add audited commuting-zone assets and
   2010/2020 tract packs, appropriate detail selection, local extent handling,
   exact pack pins, reproducibility metadata, and custom-pack documentation.
4. **Distribution and documentation.** Complete the Linux target, offline setup,
   platform installation tests, visual regression examples, migrated help, and
   reproducible release builds. Published support follows actual tests rather
   than assumptions from a successful local Python run.

Use exact assertions for IDs, samples, bins, and geometry validity. Compare
rendered figures with tolerances appropriate to each supported platform and
inspect PDF/SVG fonts and paths. Byte-identical graphics across operating systems
are not an initial requirement; correct classifications, stable assets, and
consistent visual results are.

At the time of the initial proposal, only source/asset inspection and a targeted
Stata classification check had been completed. The subsequent source alpha has
been exercised locally on macOS with county/state exports and a Los Angeles
tract example. Its self-contained packaging remains unverified because the
build dependency could not be downloaded in the development environment. No
clean-machine or other-platform result should be inferred from the local tests.

## References

1. [Stata: Python integration manual](https://www.stata.com/manuals/ppystataintegration.pdf) and [Stata's setup walkthrough](https://blog.stata.com/2020/08/18/stata-python-integration-part-1-setting-up-stata-to-use-python/).
2. [PyInstaller: operating modes](https://www.pyinstaller.org/en/stable/operating-mode.html).
3. [PyInstaller manual: bundling and supported platforms](https://www.pyinstaller.org/en/stable/index.html).
4. [Ben Jann: geoplot source and installation requirements](https://github.com/benjann/geoplot).
5. [Matplotlib: static rendering backends](https://matplotlib.org/stable/users/explain/backends.html).
6. [Matplotlib: dependencies](https://matplotlib.org/stable/install/dependencies).
7. [Census Bureau: cartographic boundary files](https://www.census.gov/geographies/mapping-files/time-series/geo/cartographic-boundary.html).
8. [Census Bureau: ZIP Code Tabulation Areas](https://www.census.gov/programs-surveys/geography/guidance/geo-areas/zctas.html).
9. [PyInstaller: macOS architecture and signing](https://www.pyinstaller.org/en/stable/feature-notes.html).
10. [PyInstaller: archive and symlink requirements](https://pyinstaller.org/en/latest/common-issues-and-pitfalls.html).
