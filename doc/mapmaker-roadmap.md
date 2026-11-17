# Mapmaker feature geography and projection roadmap

Draft for prioritization · November 16, 2026

Mapmaker should make publication-quality research maps easy to produce from a
Stata do-file: install one small bundle, choose a documented geography, and get
a reproducible figure. The next development cycle should concentrate on
**comparable maps across groups and years, trustworthy geographic joins, and a
broader geography catalog**. More expressive map types and international coverage
should follow the geometry and metadata work that makes them reliable.

This is a proposed roadmap, not a list of shipped functionality. All command
examples below are **proposed syntax**, except commands explicitly identified as
already available. Priorities describe implementation order, not release dates.

## Geography implementation update

The first P1–P3 geography implementation is now in the checkout. The
[geography guide](geographies.md) records the shipped catalog scope, source-specific
limits, commands, and remaining extensions. This includes the expanded optional
providers, documented CZ definitions and membership tables, source attributes,
GeoJSON import, previews, diagnostics, and date-line handling. The block family is
an explicit DC/Rhode Island county pilot; general crosswalk allocation, UK small
areas, GISCO LAU/FUA, and further annual layers remain follow-on work. Other feature
proposals below remain a roadmap unless covered by the implementation updates.

## Projection implementation update

The P1–P3 projection work is now implemented in the checkout. The
[projection guide](projections.md) documents named presets, recommendations,
comparison exports, regional/inset controls, horizon/pole/lobe handling,
explicit optional grids, and the bounded geometry cache. Legacy packs keep
their fixed geometry. New projections use dated/imported packs; unsupported
datums fail rather than being guessed. The guide states cartographic sampling
limits and distinguishes finite-radius distortion circles from exact indicatrices.
General map types and crosswalk allocation are covered by the subsequent feature
implementation below.

## Research-feature implementation update

The remaining P1–P3 feature rows in section 3 are now implemented in the checkout.
The [research-figure guide](research-figures.md) is the reference for shipped syntax;
the examples in the original proposal below remain design context. Implemented work
includes comparable panels and weighted/baseline scales; continuous, diverging,
categorical and bivariate classification; labels/outlines; styles and exact saved
scales; reproduction resource locks; symbols/points; supplied uncertainty; aggregate
flows; and deterministic tile and Dorling circle layouts. Offline archives, library
inventory/repair/update discovery, and explicit count/rate crosswalk allocation
complete the associated resource workflows. The typed figure request is schema 2;
ordinary map requests remain schema 1 and retain their original behavior.

Cartograms currently mean Dorling circles, not contiguous area deformation.
Private data remain necessary to reproduce a figure. Existing geography pilot and
provider limits still apply. Public artifact hosting, release signing, clean-machine
validation, and macOS/Linux release builds remain the separate P0 release work;
GeoPackage/spatial-DTA interoperability and later catalog growth remain follow-ons.

## 1. Starting point

The starting checkout, before roadmap implementation, provided:

- A Windows x64 bundle requiring no user Python setup: approximately **58.8 MB
  downloaded and 124.2 MB unpacked**, including documentation and the quickstart.
  It has development-machine validation but is not a published, signed release.
- Default U.S. county, state, and commuting-zone packs, with explicitly unverified
  `legacy` vintages and fixed projections.
- Fifteen catalog entries, including eleven downloadable Census packs: five
  congressional district plans, 2020 national states/counties, and California/New
  York tracts and PUMAs. Legacy tracts are optional and source/bundle dependent.
- Stata catalog browsing, installation, removal, local shapefile import, explicit
  catalog refresh, immutable revisions, source checksums, and offline rendering.
- Quantile/custom-cutoff choropleths, missing-value styling, zoom/context,
  regional insets, and PDF/SVG/PNG exports. Classification remains in Stata.
- PROJ/pyproj, a searchable CRS database, and four named projection presets:
  Equal Earth, Robinson, Conus Albers, and Web Mercator. Arbitrary supported CRS
  definitions are already accepted for source-coordinate packs.

Important limitations shape this plan: only 2D polygon shapefiles can be imported;
there are no general overlay layers or small multiples; non-state schema-2 packs
lack a separate state-outline layer; crossing the antimeridian in a single panel
can fail; specialized datum grids require manual installation; projected geometry
is rebuilt on each render. New downloadable providers currently require changing
the Census-only download adapter.

Implementation references: [maintainer guide](mapmaker-v2-design.md),
[catalog](../catalog/geographies.json), [projection module](../python/mapmaker_engine/projections.py),
and [Stata command reference](../mapmaker.sthlp).

## 2. Product decisions to preserve

1. **One prepackaged installation.** New capabilities must not send ordinary
   users to pip, a terminal, or a virtual environment. Build and validate native
   bundles separately for each supported OS/processor.
2. **A small base distribution.** Retain counties, states, and commuting zones as
   the default geography families. Treat 60 MB compressed and 150 MB unpacked as
   proposed base-bundle release gates, measured per platform. The current Windows
   ZIP has only about 1.2 MB of compressed headroom. These are engineering targets,
   not measurements of future builds.
3. **Explicit, optional downloads.** Detailed boundaries, historical collections,
   international packs, raster backgrounds, and datum grids stay outside the base
   bundle. Show download size, installed size, dependencies, and coverage first.
4. **No silent geographic or statistical changes.** A software upgrade must not
   change an existing script's boundary vintage, classification, or projection.
   Keep the current shorthand behavior until a documented migration is chosen.
5. **Stata remains the research interface.** Commands must work in batch mode,
   preserve the caller's dataset, and expose diagnostics and useful `r()` results.
   A browser/dialog can help compose commands, but the resulting do-file is the
   durable record.

## 3. Highest-value feature additions

Priority key: **P0** release foundation; **P1** next product increment; **P2**
follow-on capability; **P3** exploratory. Effort is relative: **S** is an isolated
change, **M** spans several modules, and **L** adds a substantial rendering/data
workflow. These are not person-week estimates; provider audits can change them.

| Addition | Research use and intended behavior | Priority / effort | Completion check |
| --- | --- | --- | --- |
| Small multiples with shared scales | Compare years, treatments, or outcomes with one extent, consistent bins, and a shared legend | P1 / L | A value receives the same color in every panel under shared-scale mode; missing panels/regions are explicit |
| Geographic join diagnostics | Explain unmatched IDs, leading-zero problems, wrong levels, duplicates, and suspected vintage mismatches before rendering | P1 / M | Export a diagnostic frame/table without changing the active dataset; suggestions never silently rewrite IDs |
| Diverging, continuous, and categorical maps | Center treatment effects at zero; display continuous rates; map named categories without imposing numeric quantile order | P1 / M | Tested handling of ties, missing values, zero, category order, legend units, and clipped scale endpoints |
| Labels and outline layers | Label selected places; highlight a treatment boundary; restore state outlines over county/district/tract maps | P1 / M | No silent vintage mismatch between layers; deterministic label placement and manual overrides |
| Reusable map styles and saved scales | Apply a paper's typography, colors, dimensions, and common cutoffs across figures | P1 / M | Style changes do not change data selection; saved scales preserve actual thresholds and interval rules |
| Pack previews and examples | Browse thumbnail maps, ID examples, extent, feature count, source notes, and ready-to-copy commands inside Stata | P1 / M | Preview requires no user data; the shown example runs against that exact pack revision |
| Reproduction manifest | Save the map specification, resolved dependencies, source attribution, cutoffs, and engine versions alongside output | P1 / M | A second machine can restore the required resources explicitly and verify their hashes |
| Bivariate choropleths | Show relationships such as income versus mobility or exposure versus vulnerability with a two-dimensional legend | P2 / M | Each axis has documented cutoffs; missing either variable is distinct; category count is bounded |
| Proportional symbols and point layers | Show counts, cities, facilities, or treatment sites above boundaries | P2 / L | Symbol **area**, not radius, tracks magnitude; a size legend and overlap strategy are present |
| Uncertainty overlays | Hatch low precision, small samples, or intervals spanning a supplied reference value | P2 / M | Legends distinguish missing data from uncertain estimates; the command does not infer significance from point estimates |
| Origin–destination flow maps | Display migration, commuting, or trade with curved paths and volume-scaled widths | P3 / L | Aggregate before drawing, support explicit top-N/threshold rules, and disclose omitted flow volume |
| Tile maps and cartograms | Make small states or dense urban areas visible when geographic area is a poor visual weight | P3 / L | Clearly label the nongeographic layout; pin the layout/algorithm revision for reproducibility |

### Comparable maps are the first flagship feature

Provide shared and panel-specific classification modes, with **shared** as the
default for a comparison figure. Shared cutoffs should be computed over the
declared comparison sample, not whichever panel happens to render first. A user
must be able to choose a baseline period or supply previously saved cutoffs.
Document whether pooled observations or explicitly supplied weights determine
the scale; never imply that each panel has equal influence automatically.

Support fixed extents and stable ordering. If missingness changes across years,
retain the selected boundary universe and distinguish missing from excluded.
A difference map must first use compatible units and a common geography. Different
boundaries require an explicit harmonization step, not merely matching ID strings.
Panel data should be unique on `(geographic ID, panel key)`, allowing an ID to
recur across years while still rejecting duplicates within a panel. Return matched,
missing, and excluded counts per panel as well as for the full figure.

```stata
* Proposed: common boundaries, common colors, and a shared legend.
mapmaker unemployment, geography(us_county_2020_500k) id(geoid) ///
    by(year) scale(shared) columns(3) saving("unemployment-panels.pdf")

* Proposed: keep zero visually meaningful for signed estimates.
mapmaker effect, geography(county) id(fips) ///
    classification(diverging) center(0) saving("effects.pdf")
```

Start with fixed, explicit cutoffs across panels, then add pooled quantiles and
saved-scale reuse. A multi-panel renderer is preferable to attempting to pass
external PDFs through Stata's Graph Editor or promising native `.gph` editing.

### Make styling useful rather than ornamental

Add a small set of accessible sequential/diverging palettes, grayscale-safe
themes, consistent fonts, configurable legend placement, and panel labels.
Palette choice must follow the data type; categorical values should not silently
inherit an ordered sequential ramp. Add color-vision/grayscale preview examples.

Labels need inside-polygon anchor points, a maximum label count, collision
avoidance, and explicit offsets for publication finishing. Scale bars and north
arrows must be computed per panel/projection; a composite U.S. inset map must not
suggest that all panels share a scale. Graticules should be optional and subtle.

## 4. Geography expansion

### U.S. catalog priorities

Use generalized cartographic boundaries by default and offer detailed sources
where they serve a real analytical need. Availability varies by geography and
vintage: for example, the Census 2025 page directs users to the 2020 collection
for PUMAs, urban areas, voting districts, and ZCTAs. Do not manufacture annual
versions by changing a URL template. [Census cartographic boundary catalog](https://www.census.gov/geographies/mapping-files/2025/geo/carto-boundary-file.html)

| Geography | Why add it | First scope and packaging | Priority |
| --- | --- | --- | --- |
| Documented commuting zones | Essential for labor, mobility, trade, and regional economics; replace uncertainty about the legacy source | Distinct ERS 1990, 2000, and 2020 candidates; separate Penn State series; county membership tables plus prepared dissolved polygons | P1 |
| Tracts and PUMAs nationwide | ACS and microdata research beyond California/New York | 2010 and 2020 definitions where available, packaged by state; one small index, no nationwide automatic download | P1 |
| Metro/micro areas and combined statistical areas | Housing, labor markets, urbanization, and regional comparisons | National packs with named delineation dates, metropolitan divisions as a separate level | P1 |
| More county/state vintages | Annual administrative changes and historical comparisons | Reviewed annual snapshots and decennial anchors; preserve county-equivalent definitions and ID changes | P1 |
| Congressional districts | Election and policy panels with the right district plan | Fill gaps in the modern Congress series, then add 2000s/1990s and earlier plans after source review | P1 modern; P2 historical |
| Places and county subdivisions | Municipal policies, local taxation, and urban/rural work | State packs; separate incorporated places, census-designated places, and subdivisions where appropriate | P2 |
| ZCTAs | Useful joins to survey and public demographic data | Explicitly named ZCTA packs, including boundary year; never label these as authoritative USPS ZIP polygons | P2 |
| School and state legislative districts | Education finance and state policy analysis | Separate elementary/secondary/unified school systems and upper/lower legislative chambers; state and year partitions | P2 |
| Tribal and Native statistical areas | Research poorly served by county-only maps | Census area types retained explicitly; no assumption that areas form an exclusive state hierarchy | P2 |
| Block groups and voting districts | Neighborhood and electoral research | State/county partitions where source organization permits; IDs and coverage audited separately | P2 |
| Census blocks | Very fine spatial work | County-scoped advanced packs only; benchmark memory, rendering, and simplification before offering national access | P3 |
| Watersheds and ecoregions | Environmental and climate exposure maps that need nonadministrative regions | Start with manageable hydrologic-unit levels and broad ecoregions; independently version the source taxonomy | P3 |

**Commuting zones need more than a year.** USDA ERS's current 2020 release has
598 zones covering 3,222 counties/county-equivalents in the United States and
Puerto Rico. ERS explicitly distinguishes its contiguous 2020 construction from
Penn State's 2020 zones. A proposed identifier such as `us_ers_cz_2020` should
therefore include provider/methodology; `cz2020` alone is ambiguous. Preserve
legacy IDs and never infer a vintage by matching feature counts.
[USDA ERS commuting zones](https://ers.usda.gov/data-products/commuting-zones-and-labor-market-areas)

For a derived CZ pack, audit the county membership file against a compatible
county boundary vintage, report missing/duplicate counties, and dissolve in the
maintainer build pipeline. Ship the exact membership table and source hashes.
Do not require every user to install a geometry-processing stack merely to
draw a commuting-zone map.

**Congressional districts need plan dates.** Store Congress, boundary reference
year, and effective dates where documented. A decade filter is a discovery aid,
not a unique map identity. UCLA's historical collection is a candidate for older
plans and currently describes coverage through the 119th Congress; audit its
release, identifiers, exceptions, and redistribution terms before packaging.
[UCLA congressional district boundaries](https://cdmaps.polisci.ucla.edu/)

**Boundary change detection should be concrete.** Include a regression example
for Connecticut's replacement of eight counties with nine planning regions in
Census reporting, rather than treating every county vintage as interchangeable.
[Census geography changes](https://www.census.gov/programs-surveys/economic-census/geographies/levels/2022-levels.html)
Likewise, ZCTAs are generalized representations of ZIP-code distributions, not a
one-to-one inventory of postal delivery areas.
[Census ZCTA guidance](https://www.census.gov/programs-surveys/geography/guidance/geo-areas/zctas.html)

Watershed and ecoregion candidates should come from reviewed official datasets,
not an opaque downloaded map: [USGS hydrography products](https://www.usgs.gov/national-hydrography/access-national-hydrography-products)
and [EPA ecoregions](https://www.epa.gov/eco-research/ecoregions).

### International catalog priorities

All entries below are optional downloads. Each provider needs an adapter,
attribution rules, documented IDs, and revision-pinned source URLs/checksums.

| Geography family | Proposed first offering | Source and important constraint | Priority |
| --- | --- | --- | --- |
| World countries and coastlines | Natural Earth 110m and 50m for small-scale figures; 10m as an optional detail pack | Natural Earth is public domain; its default disputed-boundary policy must be visible, not mistaken for a neutral universal administrative standard | P1, after global clipping |
| European statistical regions | NUTS 1–3, preserving each classification edition; LAU and functional urban areas later | Eurostat GISCO provides multiple editions; preserve NUTS codes and verify the specific download provisions | P2 |
| Canada | Provinces/territories, census divisions, metropolitan areas, then tracts | Statistics Canada; preserve UID/DGUID and distinguish cartographic from digital boundaries | P2 |
| Australia | States, SA2/SA3/SA4, then local government areas | ABS ASGS; distinguish editions and annual layers, including 2021 and 2026 definitions where relevant | P2 |
| United Kingdom | Local authorities and constituencies, then smaller statistical areas | ONS and relevant national statistical agencies; verify which products cover the UK versus particular nations | P2 |
| Other countries' subnational regions | A small reviewed ADM1/ADM2 pilot, then country-by-country growth | geoBoundaries gbOpen; retain per-country boundary year, source, and license rather than assuming one global vintage | P2 pilot; P3 broad catalog |

Sources: [Natural Earth terms](https://www.naturalearthdata.com/about/terms-of-use/)
and [boundary policy](https://www.naturalearthdata.com/about/disputed-boundaries-policy/);
[GISCO NUTS](https://ec.europa.eu/eurostat/web/gisco/geodata/statistical-units/territorial-units-statistics);
[Statistics Canada boundary guide](https://www150.statcan.gc.ca/n1/pub/92-160-g/92-160-g2021001-eng.htm);
[ABS ASGS downloads](https://www.abs.gov.au/statistics/standards/australian-statistical-geography-standard-asgs/edition-4-july-2026-june-2031/access-and-downloads/digital-boundary-files);
[ONS Open Geography Portal](https://geoportal.statistics.gov.uk/);
[geoBoundaries API](https://www.geoboundaries.org/api.html).

For world maps, use a provider-native primary ID plus an explicit ISO crosswalk.
Do not assume every feature has a unique ISO country code, or silently drop
territories and disputed areas. Distinguish dataset release version from boundary
vintage. `country()`, sovereign state, and map unit should not become interchangeable
labels merely because a single file contains all three concepts.

For geoBoundaries, start with **gbOpen**; its API documents CC-BY 4.0 compliance.
Other release families have different restrictions and should not inherit the
same installation policy. Avoid a giant all-country archive.

### Historical boundaries and crosswalks

Historical counties, tracts, and congressional plans could become a distinctive
strength for economic history. Begin with discovery, clear dates, and import
recipes; add hosted packs only when redistribution is permitted. NHGIS's terms
restrict redistribution without permission, so its downloadable files must not
automatically be mirrored into a public Mapmaker collection.
[NHGIS use terms](https://www.nhgis.org/citation-and-use-nhgis-data)

Crosswalks deserve a separate interface and schema. Census relationship files
describe geographic relationships; NHGIS additionally offers modeled interpolation
weights. Neither justifies silently matching identical-looking IDs across time.
[Census relationship files](https://www.census.gov/geographies/reference-files/time-series/geo/relationship-files.2020.html),
[NHGIS crosswalks](https://www.nhgis.org/geographic-crosswalks)

Recommended progression: inspect relationships → export a crosswalk frame →
explicitly request an allocation. Record source/target geography, direction,
weight universe, method, coverage, and any unallocated mass. For counts, verify
weight sums and conservation within documented coverage. For rates, transfer
numerators and denominators separately; do not average rates or medians as if
they were additive counts. Mapping and areal interpolation should remain
separate actions.

## 5. Projection and layout roadmap

Most useful projection mathematics is already in the bundled PROJ library.
The valuable additions are **good named presets, understandable recommendations,
preview comparisons, and correct geometry at projection boundaries**. Adding an
alias usually adds little data; adding a robust globe renderer is much larger work.

### Curated presets

EPSG names/methods below were checked against the local bundled pyproj database.
Many can already be selected by EPSG code; the proposed work is discoverability,
region checks, defaults, and tested rendering. Presets with configurable centers
must save the resolved parameters, not just an `auto` label.

| Preset or family | Intended use | New work and important tradeoff | Priority |
| --- | --- | --- | --- |
| Conus Albers, EPSG:5070 | U.S. thematic maps | Existing preset; add extent validation and make its relationship to the multi-projection U.S. layout explicit | P1 |
| Alaska Albers, EPSG:3338 | Alaska research maps | Named regional preset and examples; avoid silently changing existing legacy inset geometry | P1 |
| Europe LAEA, EPSG:3035 | European regional choropleths | Named equal-area preset with area-of-use guidance | P1 |
| Australia Albers, EPSG:9473 | Australian thematic maps | GDA2020 preset; distinguish the GDA94 alternative EPSG:3577 and required datum operations | P2 |
| Canada Lambert, EPSG:3347 | Canadian maps using the national statistical CRS | Conformal, **not equal-area**; also offer a clearly labeled regional equal-area option for thematic comparisons | P2 |
| Regional Lambert azimuthal equal-area | A country, continent, or study region without a good named preset | Resolve and record the center; check antipodal/domain behavior | P1 |
| Equal Earth | Worldwide choropleths | Existing preset; add robust seam handling and Atlantic-/Pacific-centered choices | P1 with global geometry work |
| Robinson and Winkel Tripel | General-purpose world reference maps | Robinson exists; add a tested Winkel Tripel preset and explain that these are compromise, not equal-area projections | P2 |
| Automatic UTM selection | Compact regional maps and coordinate overlays | Select the correct zone/hemisphere; warn for multizone or polar extents instead of presenting it as universally suitable | P2 |
| Polar stereographic and polar equal-area | Arctic/Antarctic research | EPSG:3413/3031 are stereographic options; distinguish conformal and equal-area choices and test pole-enclosing rings | P2 |
| Azimuthal equidistant | Distances from a selected origin, such as a port or city | Preserve distances from the center, not every pair of locations; store the origin and datum | P2 |
| Orthographic globe view | Presentations and global context | Hemisphere/horizon clipping, densification, and visible-part labels; do not expose as a polished mode before those work | P3 |
| Interrupted equal-area projections | Global land comparisons | Requires deliberate lobe cuts and hole preservation; defer behind ordinary world maps | P3 |

Technical references: [PROJ projection catalog](https://proj.org/en/stable/operations/projections/index.html),
[LAEA](https://proj.org/en/stable/operations/projections/laea.html),
[azimuthal equidistant](https://proj.org/en/stable/operations/projections/aeqd.html),
[Winkel Tripel](https://proj.org/en/stable/operations/projections/wintri.html),
and [orthographic](https://proj.org/en/stable/operations/projections/ortho.html).

### Projection recommendations and previews

Add a recommendation command that uses **intended purpose, geographic extent,
source CRS, and available transformation resources**. It should explain why a
choice fits, show two or three alternatives, and print the exact reproducible
command. Prefer equal-area options for thematic area comparisons; Web Mercator
remains available for alignment with web maps, not as the general choropleth
default. Do not promise that any projection makes raw population counts an ideal
choropleth; proportional symbols may be the better visual encoding.

```stata
* Proposed: inspect the same boundaries under several projections.
mapmaker projection compare, geography(world_ne_country_110m) ///
    choices(equalearth robinson winkeltripel) saving("projection-options.pdf")
```

A comparison should reuse the same geography and styling, optionally showing
graticules and distortion indicators. Keep it a local export initially; no new
browser runtime is needed.

### Separate layout from projection

Add `region()` for a declared geographic subset, `layout(conus)` and configurable
U.S. insets, plus movable/scaled inset panels with captions. Include Puerto Rico
and other territories when present, and make exclusions explicit. Country-specific
layouts can later handle overseas territories and island groups. A tile map is
a layout alternative, not an EPSG projection.

Before global packs are advertised, implement source-CRS normalization, longitude
wrapping, seam splitting, edge densification, projection-domain clipping, and
hole-preserving reconstruction. Test dateline-crossing islands, pole-enclosing
polygons, multipart features, and polygons crossing the visible hemisphere.
Clipping must also work for projected source CRSs after geographic conversion,
not just source files whose coordinates already look like longitude/latitude.

### Optional transformation grids

Keep ordinary CRS definitions bundled. Add a preflight that explains the exact
missing transformation grid, its size/license, and the affected operation; provide
an explicit installation command and pin the grid checksum. A shared PROJ cache
must not silently alter the transformation selected for an old figure. Grid
requirements depend on source and destination CRSs, not the destination alone.
[PROJ resource files](https://proj.org/en/stable/resource_files.html)

## 6. Catalog, architecture, and reproducibility work

### A geography pack should explain how to use it

Extend metadata with names, ID examples, hierarchy/parent fields, available
attributes, source edition, effective dates where known, jurisdiction coverage,
territory/dispute policy, compatible data products, and attribution text. Treat
compatibility as an explicit reviewed claim, not a guess from matching years.
Show actual download/installed sizes once built; label estimates as estimates.

Offer `ids`, `attributes`, and `diagnose` operations that can write to a named
Stata frame or file. The default action should not replace data in memory.
Truncate display text only, never identifiers. Review the current 32-character
ID limit before adding international sources with longer keys.

### Keep heavy work out of the user bundle where possible

Move reproducible dissolves, topology-preserving simplification, and provider
format conversion into maintainer builds. Generalize the existing pack schema
and retain a source-coordinate representation; do not ship separate full boundary
copies for every projection. If runtime geometry operations require a new compiled
library, benchmark the bundle impact before adopting it. A prepared-pack route
can reduce per-user work but requires actual artifact hosting and licensing.
Keep the existing direct-Census installer usable during that transition.

Split the Stata wrapper into reusable resolution, ID matching, classification,
and rendering stages before adding panels and layers. Evolve the request schema
explicitly: point coordinates, symbol sizes, category labels, and uncertainty
flags need typed fields rather than overloading `mm_bin`. Send only the required
selected/derived fields to the local renderer; a new visualization must not
implicitly export the whole dataset.

For custom imports, add GeoJSON first, then assess GeoPackage and Stata spatial
`.dta` interoperability. Keep topology repair opt-in with a report of changed
features. Store a layer's CRS and transform it explicitly; never overlay raw
coordinates from unrelated CRSs.

### Caching and storage

Add a bounded projected-geometry cache, initially targeting **64 MB** by default,
with visible usage and an explicit limit/purge command. Key it by geometry hash,
selected feature set where relevant, full source/target CRS, resolved operation
and grid hashes, PROJ/engine versions, simplification, and clipping parameters.
Oversized entries should bypass caching. Eviction must never delete installed
geography packs or their pinned revisions.

Add library inventory, verification, repair/reinstall, and update discovery.
An update should install a new revision beside the old one. Catalog publication
should validate provider hosts, hashes, metadata, and revision immutability;
distribute a verifiable catalog/release manifest before scaling public distribution.
Allow exporting/restoring an offline pack archive with required attribution.

A reproduction file should record engine/bundle, packs, classification settings,
cutoffs, selected projection operations, layout/style, and output dimensions.
It should **not embed the user's mapped dataset by default**. Restoring a manifest
can obtain permitted public resources explicitly, but reproducing the figure
still requires the user's input data. Promise semantic/visual reproducibility
within a pinned environment, not byte-identical PDFs across arbitrary platforms.

## 7. Proposed implementation sequence

| Milestone | Concrete deliverable | Dependencies | Exit criteria |
| --- | --- | --- | --- |
| M0: distributable release | Publish the reviewed catalog and a versioned Windows bundle; add signing, clean-machine checks, size reporting, then macOS/Linux release jobs | Existing bundle; platform build/signing environments | Fresh supported machine can install, browse, and map without Python; offline export works; base-size gates pass |
| M1: stronger U.S. research catalog | Nationwide state-partitioned tracts/PUMAs, metros, documented CZ candidates, modern district gaps, richer metadata and diagnostics | Provider adapters; ID schema review; build-time dissolve for CZs | Every released pack has verified joins, source/license metadata, and a small executable example; no silent default-vintage migration |
| M2: comparable publication figures | Shared-scale panels, diverging/categorical/continuous classifications, styles, outlines, basic labels, reproduction files | Classification refactor; layer/panel request schema | A three-year figure has identical scales/extents where requested; all counts/labels/attribution match expected fixtures |
| M3: international and projection experience | World countries, seam-safe rendering, regional projection recommendations/previews; then EU/Canada/Australia pilots | Global geometry pipeline; provider-specific IDs and distribution rules | Global seam/hole tests pass; each pilot joins to a documented sample table; unsuitable projections produce useful diagnostics |
| M4: richer analytical maps | Bivariate maps, proportional symbols, point layers, uncertainty styling, explicit crosswalk workflows | Typed payloads/layers; crosswalk schema; capacity benchmarks | Visual encodings and allocation tests pass; storage/runtime changes remain within published budgets |
| M5: experiments | Flow maps, cartograms, animated comparisons, orthographic views, optional standalone HTML exports | Stable static maps; appropriate clipping/layout methods | Each experiment has a distinct research use, reproducible semantics, and measured dependency cost before promotion |

M1 catalog expansion and M2 rendering can be developed independently after their
shared metadata/schema decisions. Regional preset aliases can land before M3;
world-map promotion must wait for global geometry correctness. Historical packs
can arrive incrementally when their dates, IDs, and distribution terms are settled.

## 8. Validation and release gates

- **Geography:** exact feature/ID counts, leading zeros, multipart geometry,
  holes, territory coverage, duplicate handling, source hashes, and known boundary
  changes. Test concurrent installs, interrupted downloads, offline use, and
  preservation of old revisions after updates.
- **Statistics:** classification on tied/constant/missing data; categorical
  ordering; shared-panel cutoffs; signed scales; bivariate legend mapping; explicit
  weight semantics; conservation and uncovered fractions for crosswalks.
- **Projection:** trusted coordinate fixtures, axis order, region/domain checks,
  antimeridian and horizon clipping, polar geometry, missing grids, and correct
  treatment of each inset's scale. Avoid relying solely on image similarity.
- **Stata integration:** active data/frame/sort order restored after success and
  failure; do-files work with the bundled runtime, paths containing spaces, and
  no network. Management commands should also work with no dataset loaded.
- **Publication output:** inspect PNG/PDF/SVG for clipped legends, tiny labels,
  overdraw, polygon holes, and accessibility. Keep reference figures for county,
  tract, district, global, and multi-panel maps.
- **Performance and footprint:** record download/unpacked sizes, optional pack
  sizes, cold/warm render times, peak memory, and output sizes on a stated machine.
  Establish baselines before choosing timing thresholds. Block unreviewed large
  dependency increases and never count external data/cache usage as zero.

## 9. Deliberately deferred

Do not turn Mapmaker into a full GIS, address geocoder, or general data downloader
in the next release. Defer live web tiles, satellite imagery, national block-level
defaults, automatic statistical smoothing, automatic rate interpolation, and
unrestricted third-party plugin code. Raster maps and multimedia encoders can be
optional components later, with explicit attribution, storage, and runtime costs.

Animations should reuse fixed classification and geography by default; exporting
a frame sequence is a smaller first step than bundling a video encoder. A future
HTML map should be an explicit export of selected fields with a clear disclosure
of embedded data, rather than a hidden upload or an alternative runtime required
for ordinary PDF output.

## 10. Recommended next slice

Start with a focused release containing:

1. Publishable bundles/catalog with measured size gates and clean-machine tests.
2. Nationwide tract/PUMA discovery and state-scoped installation, plus one vetted
   modern commuting-zone pack and one documented historical CZ candidate.
3. Geographic diagnostics, ID/attribute export, and a state-outline overlay.
4. A three-panel map with shared explicit cutoffs, a shared legend, and stable
   extent; add pooled cutoffs after the semantics are fixed.
5. Named Alaska/Europe/regional equal-area presets and useful selection guidance.

The first showcase should be a reproducible regional-economics figure: the same
outcome in three years, on one declared geography, with identical colors and a
clear boundary/source note. Follow it with a historical congressional comparison,
an international choropleth, and a bivariate county map. Those examples demonstrate
new research value while keeping the default installation small.
