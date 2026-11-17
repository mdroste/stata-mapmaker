# Research figures from Stata

The P1–P3 map features are available in the development bundle. Stata 16 or later
uses the included renderer; no Python installation or environment setup is needed.
Existing single-map commands keep their original behavior. The examples below
use new options, which select the research-figure interface and its typed payload.
Use polygon geography packs for these figures.

## Comparable panels and classification

```stata
mapmaker income, geography(county) id(fips) by(year) scale(shared) columns(3) ///
    panelorder("2000|2010|2020") units("Income, dollars") ///
    scalesave("income-scale.json") manifest("income-manifest.json") ///
    results(map_counts) saving("income-panels.pdf")
```

IDs must be unique **within each panel** after normalization. `if`/`in` select
observations before joining and classification. Missing mapped values remain in
the comparison sample. By default, unmatched IDs cause an error; `unmatched(drop)`
drops them before calculating cutoffs and reports their counts.

`scale(shared)` is the default. It pools the selected, matched observations across
panels. Repeated regions therefore contribute once per observed panel. Supply
`baseline(2010)` to calculate cutoffs from that panel, or `[aw=population]`,
`[fw=frequency]`, or `[pw=weight]` to weight Stata's percentiles. Weights must be
positive and nonmissing; frequency weights must be integers. Weights affect
classification, not polygon area or symbols. The manifest records these semantics.

Panels use one common geographic extent and the same resolved projection. Numeric
panel keys sort numerically; strings sort lexically. `panelorder()` accepts a
pipe-separated explicit order, including absent panels. It must include every
observed key. An absent panel says “No observations”; an absent region within a
panel uses the missing color. Regions outside the comparison sample have a separate
legend entry. `scale(panel)` calculates separate scales, labels the figure accordingly,
and shows a legend per panel. An entirely missing panel gets an explicit empty scale.

The renderer receives preclassified bins. **All thresholds are calculated in Stata.**
Intervals are upper-inclusive: the first bin is `value <= first cutoff`; subsequent
bins use `previous < value <= next`. Tied percentile cutoffs retain empty bins.
Constant univariate references use one color. No hidden interpolation or statistical
classification occurs in the renderer.

| Option | Behavior |
| --- | --- |
| `classification(quantile)` | Default: five Stata percentile groups; `nquantiles(2..32)` |
| `cutvalues(10 20 30)` | Exact strictly increasing thresholds; selects custom classification |
| `classification(diverging) midpoint(0)` | Symmetric equal-width bins about the supplied midpoint, using the maximum reference deviation; five bins by default |
| `classification(continuous) limits(0 100)` | Continuous colorbar; optional fixed endpoints, with out-of-range values clipped and counted |
| `classification(categorical) categories("Low\|Medium\|High")` | Named categories, with explicit order; omit `categories()` to sort reference categories |
| `bivariate(other) nquantiles(3) nquantiles2(3)` | Separate Stata percentile scales, 2–4 classes on each axis; optional `cutvalues()`/`cutvalues2()` |

Categorical variables can be strings or numeric codes. Numeric value labels supply
display text; `categories()` uses the **raw numeric codes** for ordering. Unknown
categories in another panel or a saved scale cause an error. Missing categories
stay missing. Bivariate maps have a two-dimensional legend with actual cutoffs;
`xlegend()` and `ylegend()` name its axes. Missing either variable makes the region
missing. Bivariate colors are a fixed four-corner interpolation, with revision
captured by the engine fingerprint; inspect the exported figure for your audience.

`limits()` clips colors, not observations. Continuous maps without limits use the
reference minimum/maximum, expanding a constant range deterministically. Endpoint
arrows indicate clipping. `units()` supplies legend units. `midpoint()` is a
classification option; `center()` retains its longitude/latitude projection meaning.

`r(N)`, `r(N_missing)`, `r(N_unmatched)`, `r(panels)`, and `r(panel_counts)` describe
the selected data. The matrix columns are `matched missing absent unmatched excluded
visible`, ordered as the panels. `results(new_frame)` retains those counts and the
panel keys. The active dataset is restored after success and failure. Embedded figure
metadata additionally includes bin counts and continuous clipping counts.

## Labels, outlines, and decorations

```stata
mapmaker effect, geography(us_county_2020_500k) id(fips) ///
    classification(diverging) midpoint(0) labels(short_name) labellimit(25) ///
    highlight(treated) outline("states") layout(conus) ///
    scalebar northarrow saving("effects.pdf")
```

Install the base and outline packs explicitly first. `outline("states")` selects
the matching-year 500k state pack, or the fixed legacy state pack for legacy data.
Explicit layers use `outline("pack_id@revision other_pack@revision")`. Every layer
is checksum verified and transformed to the base projection. A vintage mismatch
fails unless `allowvintagemismatch` is supplied; that acknowledgment is recorded.
Fixed legacy layers must have the same documented fixed projection. `highlight()`
accepts a 0/1 variable and emphasizes the selected base boundaries.

`labels()` accepts a variable; blank labels are skipped. Anchors are interior points
of the largest visible polygon component, respecting holes. Legacy geometry is made
valid for **anchor calculation only**; its drawn boundaries are preserved. Placement
is deterministic by ID, avoids collisions, and tries short offsets with leader lines.
`labellimit(50)` caps labels **per geographic panel/inset**; zero suppresses labels.
`labeldx()`/`labeldy()` provide manual offsets in typographic points. Manual placement
can override collision avoidance, but labels remain within the axes. Metadata lists
omitted IDs and the selected offsets; it omits label text from reproduction files.

Scale bars and north arrows require source-coordinate packs with known CRSs.
Each is computed at a recorded reference point for its geographic panel. A scale
bar describes distance **at that reference**, not everywhere in a distorted map.
North follows the local meridian; polar reference points where it is undefined
are rejected. Geographic decorations cannot be applied to tile maps/cartograms.

## Symbols, points, uncertainty, and flows

```stata
mapmaker rate, geography(state) id(state) by(year) size(population) ///
    uncertain(low_precision) saving("rates-and-population.pdf")

mapmaker count, geography(state) id(state) maptype(symbol) size(count) ///
    saving("counts.pdf")

mapmaker effect, geography(county) id(fips) classification(diverging) ///
    cilower(lower95) ciupper(upper95) reference(0) saving("intervals.pdf")
```

Symbol **area** is proportional to nonnegative size. A shared size scale spans all
panels and point layers. Larger symbols draw first with translucent fill so smaller
symbols remain visible; a size legend uses the same areas. `symbolmax(500)` sets
the largest symbol's area in square points. Missing sizes are omitted; zeros have
zero area. `maptype(symbol)` uses neutral polygon fills. Other modes can combine
colored polygons and symbols.

Uncertainty is explicit: `uncertain(flag)` accepts 0/1/missing, or `cilower()` and
`ciupper()` flag intervals containing `reference()` (zero by default, endpoints
included). The command does not compute confidence intervals or infer significance.
Dot hatching means flagged uncertainty; cross hatching means unavailable uncertainty;
missing mapped values have their own fill and optional `hatchmissing` treatment.

`points("places.csv") pointcrs("EPSG:4326")` reads a local UTF-8 CSV with required
`x,y`, optional `size,label,id,facet,panel`. The default CRS is longitude/latitude
WGS84; coordinate order is always x/y. `facet` selects a `by()` key; blank repeats
across facets. `panel` optionally selects a geographic inset (e.g. `conus`); blank
uses every view containing the point. Points outside each view are counted. Known
source CRSs and explicit selected datum grids are required for transformation.

`flows("commutes.csv") flowtop(50) flowmin(100)` reads `origin,destination,volume`
and optional `facet`. IDs use the base geography's normalization rules. Rows with
the same facet/origin/destination are **summed before filtering and ranking**.
Thresholding precedes top-N selection; ties break by endpoint IDs. `flowtop(0)`
keeps all qualifying paths up to the drawing limit. Width is proportional to volume
using one scale across facets. Known-CRS maps draw sampled geodesic paths; fixed
legacy and nongeographic layouts use schematic curved paths. Arrowheads indicate
direction. Self-flows, filtered pairs, and endpoints outside the view or in different
insets are omitted, with their combined volume disclosed beneath each panel.

Layer inputs are local files: Stata users can create them with `export delimited`.
No Python tools are needed. Point/flow files are never copied into reproduction
manifests; only hashes and aggregate diagnostics are retained.

## Styles, saved scales, and nongeographic layouts

`style(publication)`, `style(presentation)`, and `style(grayscale)` control appearance.
The sequential defaults are viridis, cividis, and grayscale respectively. Explicit
`colorscheme()`, `colors()`, dimensions, and `legendposition(right|bottom|none)`
override the style. `stylesave("paper-style.json")` writes a portable style;
`style("paper-style.json")` reuses it. Styles contain only appearance settings,
never data selection, projections, or classification rules. `mapmaker style browse`
lists presets; `mapmaker style export publication, saving("style.json")` exports one.

`scalesave("scale.json")` stores exact thresholds, category codes/order, labels,
limits, and interval rules. `scaleuse("scale.json")` reuses them without estimating
new cutoffs. Panel-specific scales are keyed by panel name; missing keys fail.
An empty saved scale rejects new nonmissing observations. Supply `bivariate(other)`
again when reusing a bivariate scale. Keep saved scale files with the project.

```stata
mapmaker rate, geography(state) id(state) by(year) layout(tile) labels(abbrev) ///
    saving("tiles.pdf")
mapmaker rate, geography(state) id(state) by(year) layout(cartogram) ///
    size(population) cartobase(2010) labels(abbrev) saving("cartogram.pdf")
```

Tile maps use the deterministic `geographic-sort-grid-1` algorithm. A custom
`tiles("layout.json")` file has schema `mapmaker-tile-1`, a nonempty `revision`,
and `cells: {"06": [0, 1], ...}` with unique integer cells for exactly the selected
IDs. Its revision and checksum are recorded. Automatic grids may change when the
comparison sample changes; use a pinned custom layout for a stable publication series.

Cartograms currently mean **Dorling circle cartograms**, algorithm
`dorling-relaxation-1`. Circle areas are proportional to `size()` in one baseline
panel (`cartobase()`, then `baseline()`, then the first panel). All facets reuse
that geometry; colors can change by year while areas continue to represent the
declared baseline. Every selected region needs a finite nonnegative baseline size;
total size must be positive. Zero-area IDs are recorded. `iterations(500)` controls
the deterministic overlap solver; unresolved overlaps fail rather than returning
an unfinished figure. These are not contiguous area-deforming cartograms.
Every tile/cartogram export is visibly labeled nongeographic.

## Reproduction and offline resources

`manifest("figure.json")` writes a declarative recipe and resource lock alongside
the figure. It records pack revisions/hashes, attribution, actual scales, selected
grids, resolved CRS/pipelines, engine code fingerprint, style, layout algorithm,
panel diagnostics, and hashes of private layer/classified-input files. It contains
no observation table, point coordinates, flow rows, or label text. Thresholds and
aggregate counts/totals are part of the specification; review those before sharing.

```stata
mapmaker reproduce describe, using("figure.json")
mapmaker reproduce restore, using("figure.json")
mapmaker reproduce verify, using("figure.json")
```

`restore` explicitly installs missing catalog packs and selected grids; it never
silently updates to another revision. Custom/retired resources require their saved
offline archive. `verify` checks geometry hashes and the engine fingerprint, failing
on differences. Preserve the exact bundle, do-file, source data, and private layers
to rerun the figure; the manifest does not execute code or recover private data.

```stata
mapmaker geography inventory
mapmaker geography updates
mapmaker geography repair us_county_2020_500k, revision(1)
mapmaker geography export us_county_2020_500k, revision(1) saving("counties.zip")
mapmaker geography restore, using("counties.zip")
```

Inventory verifies installed packs; updates reports other catalog revisions without
changing installed resources. Repair reinstalls the **same** catalog-managed user
revision and rolls back on failure. Archives include verified geometry, ID/attribute/
membership tables, and provenance. Restore is offline, bounded, checksum verified,
and cannot overwrite a different immutable revision. Preserve providers' licenses
when sharing archives. Bundled defaults are repaired by re-extracting the bundle.

## Explicit crosswalk allocation

```stata
mapmaker crosswalk import, using("weights.csv") saving("county-crosswalk.json") ///
    source(us_county_2020_500k@1) targetpack(us_county_2024_500k@1) ///
    universe("Population, 2020") method("Published allocation weights")
mapmaker crosswalk describe, using("county-crosswalk.json")
mapmaker crosswalk apply, using("county-crosswalk.json") id(fips) value(count) ///
    frame(allocated) audit("allocation.json")
```

Weights CSV columns are `source,target,weight`; weights are fractions of each source
total allocated to each target. Import pins and validates both geography revisions,
rejects duplicate pairs/unknown IDs/negative weights, and reports coverage. Source
sums above one fail (apart from numerical tolerance); sums below one remain below
one. No normalization, weight selection, or reverse allocation is automatic.

For rates, supply **both** `numerator(events) denominator(population)` instead of
`value()`. The allocator splits both totals, then divides at the target; it does not
average rates. Counts/numerators/denominators must be nonnegative and nonmissing,
with unique source IDs. This deterministic allocation is a separate library operation,
not part of rendering or Stata's classification step. Output includes contributing
and missing-source counts. All expected target IDs appear; entirely absent targets
have missing values. Inspect incomplete coverage before using the resulting estimates.
The report and optional audit JSON disclose input, allocated, and unallocated mass.
Allocation validity depends on the declared weight universe and substantive assumptions.

## Bounds and validation

Figures support 1–36 facets and 1–6 columns, dimensions 2–40 inches, and at most
100 million raster pixels. Labels are at most 244 UTF-8 bytes; CSV layers are capped
at 64 MiB, 100,000 points, and 1,000,000 flow input rows. Aggregate large data before
mapping; at most 5,000 flow paths or cartogram regions are drawn. Crosswalk files
are bounded at 128 MiB; offline archives at 1 GiB unpacked. No new binary dependency
is required by these features.

The regression suite checks classification in Stata, panel missingness, exact saved
scales, duplicate/error preservation, flow aggregation, cartogram area and overlaps,
label anchors/holes, vintage checks, explicit crosswalk conservation, and offline
archive restore. `tools/check_features.py` exercises all output formats with more
than 6,000 synthetic observations on real Census county polygons and state outlines.
The same checks and Stata examples run against the frozen bundle.
See [feature validation](feature-validation.md) for measured capacity, bundle size,
and the distinction between development validation and release testing.
