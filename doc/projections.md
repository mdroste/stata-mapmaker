# Projections, globe views, and layouts

Projection definitions and algorithms are bundled. These commands run from
Stata using the packaged runtime; users do not install Python, a virtual
environment, or another GIS application. Optional datum grids are separate
downloads. The P1, P2, and P3 projection families in the roadmap are implemented
in this checkout, including the geometry work needed by globe and interrupted
views. This is a development build, not a published release.

## Start here

```stata
mapmaker projection browse
mapmaker projection search "Albers"
mapmaker projection describe canada-lambert

* Download a small world boundary pack once.
mapmaker geography install world_ne_country_110m
mapmaker projection recommend, geography(world_ne_country_110m) purpose(thematic)
mapmaker projection compare, geography(world_ne_country_110m) ///
    choices(equalearth robinson winkeltripel) graticule distortion ///
    saving("projection-options.pdf")

mapmaker geography preview world_ne_country_110m, ///
    projection(orthographic) center(-96 40) graticule saving("globe.png")
```

`compare` accepts two to six choices and writes PDF, SVG, or PNG. Every panel
uses the same source boundaries and styling, fitting its own extent; panel
scales are not directly comparable. `graticule` adds meridians/parallels.
`distortion` adds equal-geodesic-radius circles within each panel, a finite-size
visual aid rather than exact infinitesimal Tissot indicatrices. The radius is
recorded in the figure metadata. Visible-part labels identify clipped views.
Existing output files require `replace`.

The default county, state, and commuting-zone **legacy packs have fixed
projections**. To change their projection, install a dated pack. This preserves
the appearance of existing do-files rather than guessing a missing source CRS.

```stata
mapmaker geography install us_county_2020_500k
mapmaker income, geography(us_county_2020_500k) id(county_fips) ///
    layout(conus) saving("counties.pdf")
```

## Named presets

| Preset | Property and intended extent |
| --- | --- |
| `conus-albers` | NAD83 / EPSG:5070, equal area for the contiguous U.S. |
| `alaska-albers` | NAD83 / EPSG:3338, equal area for Alaska |
| `europe-laea` | ETRS89 / EPSG:3035, equal area for Europe |
| `regional-laea` (`laea`) | WGS84 Lambert azimuthal equal area; configurable center |
| `equalearth` | WGS84 Equal Earth, longitude origin 0°, equal area |
| `equalearth-atlantic` | Equal Earth, longitude origin −30° |
| `equalearth-pacific` | Equal Earth, longitude origin 150° |
| `australia-albers` | GDA2020 / EPSG:9473, equal area; the current-datum choice |
| `australia-albers-gda94` | GDA94 / EPSG:3577, an explicitly different older datum |
| `canada-lambert` | NAD83 / EPSG:3347, Statistics Canada Lambert; conformal, **not equal area** |
| `canada-equalarea` | WGS84 LAEA centered at 96° W, 60° N |
| `robinson` | World compromise projection, not equal area |
| `winkeltripel` | World compromise projection, not equal area |
| `auto-utm` (`utm`) | WGS84 UTM zone and hemisphere from the selected extent; includes Norway/Svalbard exceptions |
| `arctic-stereo` | WGS84 / EPSG:3413, conformal; northern hemisphere |
| `antarctic-stereo` | WGS84 / EPSG:3031, conformal; southern hemisphere |
| `arctic-equalarea` | North-polar WGS84 LAEA, equal area; northern hemisphere |
| `antarctic-equalarea` | South-polar WGS84 LAEA, equal area; southern hemisphere |
| `azimuthal-equidistant` (`aeqd`) | WGS84; distances from the selected origin, not between every pair of points |
| `orthographic` | WGS84 globe view; only the visible hemisphere is drawn |
| `interrupted-goode` (`igh`) | Interrupted Goode Homolosine, equal area; standard land-oriented lobes |
| `webmercator` | EPSG:3857 for web-map alignment; not an equal-area choropleth default |

EPSG codes, WKT, and PROJ CRS strings are also accepted. Arbitrary custom
projections do not inherit all the domain rules of the tested presets; an
invalid transformation fails explicitly. `projection(source)` preserves source
coordinates for packs whose datum is unknown or intentionally retained.
Interrupted Goode uses PROJ's spherical equal-area model; WGS84 supplies its
input datum. Its area property refers to that spherical model.

`center(longitude latitude)` applies to regional LAEA, azimuthal equidistant,
orthographic, and automatic UTM. It defaults to the center of the selected
geographic extent, using the short longitude span across the date line. Global
extents resolve to the ordinary world center. The actual origin, target WKT,
and UTM EPSG code are recorded. Centers and numeric region bounds use the
destination's geodetic coordinates; configurable-center presets use WGS84.

UTM reports multizone/equator extents and rejects latitudes beyond 80° S or
84° N. Regional EPSG presets report extent/area-of-use mismatches. These
bounding-box checks are guidance, not a claim about survey accuracy; offshore
polygons can extend slightly outside a CRS's onshore area of use. Polar presets
clip to their hemisphere. LAEA/azimuthal equidistant exclude a 0.1° cap around
the antipode. Web Mercator clips at approximately ±85.05113°.

## Recommendations and transformation preflight

```stata
mapmaker projection recommend, geography(us_county_2020_500k) ///
    region(conus) purpose(thematic) saving("recommendations.json")
mapmaker projection preflight australia-albers, geography(au_ste_2021)

* A source CRS can be inspected without installing a geography.
mapmaker projection preflight equalearth, crs(EPSG:27700) ///
    region(-6 50 2 58) saving("datum-preflight.json")
```

Use an installed pack ID from `geography browse` for `geography()`. Purposes are
`thematic` (default), `reference`, `distance`, `local`, `globe`, and `web`.
Recommendations report two or three alternatives, their properties, extent
warnings, and transformation availability, with executable preview commands.
Use the printed projection/center options in a `mapmaker value, ...` command
for your own data. Equal-area geometry does not make raw counts an appropriate
choropleth variable in every application.

Preflight identifies the source/destination CRS, selected operation, stated
accuracy, and higher-accuracy operations blocked by missing grids. It reports
each reviewed grid's exact byte count, license, checksum, affected operation,
installation command, and explicit selection option. Missing grids outside
the reviewed catalog are identified but not downloaded. Reports can be saved
as JSON. Ordinary maps select the best available **non-ballpark** operation in
the isolated resource set and report when a better known operation is missing.
If none is available, mapping fails; it never guesses an unknown datum.

## Optional datum grids

The catalog contains 112 reviewed horizontal grids from NOAA, Ordnance Survey,
ICSM, and Natural Resources Canada. License descriptions and complete provider
notices are bundled. Grid data are not included in the default download.
Mapmaker supports 2D mapping, not vertical transformations or coordinate epochs.

```stata
mapmaker projection grids, search(uk_os)
mapmaker projection grids, installed
mapmaker projection install uk_os_OSTN15_NTv2_OSGBtoETRS.tif
mapmaker projection verify uk_os_OSTN15_NTv2_OSGBtoETRS.tif
mapmaker projection preflight equalearth, crs(EPSG:27700) region(-6 50 2 58) ///
    grids(uk_os_OSTN15_NTv2_OSGBtoETRS.tif)
mapmaker projection remove uk_os_OSTN15_NTv2_OSGBtoETRS.tif
```

For durable do-files, copy the `filename@sha256` token printed by preflight into
`grids()`. Multiple tokens are space-separated. Installation alone never changes
a map. Each request uses the bundled PROJ database and only the selected,
checksum-verified grids; network transformations and the shared PROJ user cache
are disabled. The chosen operation is frozen into an explicit pipeline, rather
than silently switching operations for different points. Select a narrower
`region()` if a selected grid does not cover the whole source extent.

`datadir()` controls the user library for grids as well as geography packs.
Downloads go to a temporary file, are size/hash checked, and are committed
atomically. Explicit reinstallation repairs a corrupt grid. Removing a grid
causes do-files explicitly requiring it to fail instead of falling back.

## Regions and inset layout

`region()` declares a geographic subset independently of classification:

- For U.S. packs: one or more of `conus`, `alaska`, `hawaii`, `puerto_rico`,
  `samoa`, `guam`, `marianas`, and `virgin_islands`.
- For dated/imported packs: `region(west south east north)` clips the boundaries
  to a geographic rectangle. West greater than east crosses the date line.

`layout(conus)` selects the contiguous-U.S. panel and uses Conus Albers for dated
packs under `projection(auto)`. Legacy packs retain their fixed CONUS geometry.
Excluded feature IDs/counts and partially visible features are recorded, and
exclusions are reported in Stata. `layout(single)` uses one projection.
`layout(us-insets)` requires a U.S. pack and `projection(auto)`; each panel has
its own regional Albers CRS. Available territories receive panels automatically.

```stata
mapmaker geography preview us_county_2020_500k, region(alaska hawaii) ///
    layout(us-insets) ///
    insets("alaska .03 .2 .6 .6 Alaska (scaled); hawaii .68 .2 .25 .25 Hawaii") ///
    saving("islands.svg")
```

Each semicolon-separated `insets()` entry is
`panel left bottom width height [caption]`. Positions and dimensions are fractions
of the complete figure (0–1). A panel must be present; rectangles must fit inside
the figure. Width/height scale the panel, and a caption may contain spaces.
Inset scales are independent; caption any deliberate scale changes. User-set
rectangles may overlap other panels or the legend, so inspect the export.

## Geometry and reproducibility

The pipeline normalizes projected or geographic source coordinates into the
destination's geodetic datum, unwraps longitude, splits seams, densifies edges,
clips domains, reconstructs holes, and then projects. Orthographic and polar
views rotate the geographic frame before clipping; interrupted Goode cuts the
two northern and four southern land lobes separately. Pole-enclosing polygons
from projected files are supported. Geographic input must follow valid polygon
topology, including deliberate pole/seam closure where required by GeoJSON.

This is cartographic approximation, not an analytic GIS intersection engine.
Source projected edges are sampled at at most 25 km, geographic edges at 0.5°;
clipped edges are also densified. Boolean reconstruction snaps at 10⁻⁹ degrees
and 10⁻⁵ meters (converted for other destination units) to avoid numerical
slivers at seams/poles. Tests cover area retention, clipped holes, projected
date-line inputs, both poles, the hemisphere center, the antipode, and lobe cuts.
The source pack is not modified.

PDF/SVG/PNG metadata includes source/target WKT, resolved centers and clipping
parameters, exact transformation pipelines, stated accuracy, PROJ/database/grid
hashes and versions, geography revision/hash, selected region, exclusions,
partly visible IDs, panel rectangles/captions, and existing classification/style
metadata. Keep the engine bundle and geography revision alongside a do-file for
long-term reproducibility; definitions may evolve between engine releases.

Projected boundaries are cached separately from research values, with a default
64 MiB compressed limit and oldest-used eviction. Keys include source hash,
feature selection, resolved CRSs/operations/grids, geometry and dependency
versions, clipping parameters, and overlays. Entries larger than the budget
bypass caching. Cache contents are disposable and never replace source packs.

```stata
mapmaker projection cache
mapmaker projection cache limit, limit(32)
mapmaker projection cache purge
mapmaker projection cache limit, limit(0)   // disable
```

Technical references: [PROJ projection catalog](https://proj.org/en/stable/operations/projections/index.html),
[orthographic](https://proj.org/en/stable/operations/projections/ortho.html),
[interrupted Goode](https://proj.org/en/stable/operations/projections/igh.html),
[resource files](https://proj.org/en/stable/resource_files.html), and
[pyproj TransformerGroup](https://pyproj4.github.io/pyproj/stable/api/transformer.html#pyproj.transformer.TransformerGroup).

## Validation of this development build

The Python suite passes 55 tests, including the existing geography/rendering
regressions and new projection invariants. All 22 presets rendered through both
the source and frozen Windows runtimes, using Natural Earth, ABS, Statistics
Canada, and GISCO boundaries. Comparisons passed in PDF, SVG, and PNG. Stata
checks exercised the new commands, fixed legacy CONUS layout, custom insets,
output protection, and preservation of the active dataset.

The optional UK grid was downloaded, checksum verified, explicitly selected,
and used to transform a projected test geography inside the frozen executable.
An inherited shared-grid directory and enabled PROJ network setting did not
change the default operation. Cache usage remained within its 64 MiB budget.

World previews took seconds on the development machine. Detailed Australian
and Canadian national packs contain approximately 1.8 million and 1.3 million
vertices; their first projections took roughly 1½–2 minutes. Cached projections
avoid repeating the geometry work. These are illustrative development-machine
timings, not performance guarantees. The Windows bundle is unsigned; clean-machine
and macOS/Linux release validation remain separate release tasks.
