{smcl}
{* *! version 2.0.0a1 16nov2026}{...}
{title:mapmaker — Choropleth maps with direct PDF, SVG, and PNG output}

{pstd}
Mapmaker draws maps using default states, counties, and commuting zones,
optional U.S./international/historical boundaries, and local shapefiles or GeoJSON.
Install the prepackaged bundle for your operating system. It includes the runtime,
libraries, projection definitions, and default boundaries; no separate Python
installation or virtual environment is needed.

{title:Installation}

{pstd}
Extract the entire bundle into a permanent folder. Keep runtime/, assets/, and
catalog/ alongside mapmaker.ado. With Stata 16 or newer, run the following,
replacing the path with the extracted folder containing mapmaker.ado:

{phang2}{cmd:adopath ++ "C:/Tools/mapmaker-windows-amd64"}{p_end}
{phang2}{cmd:mapmaker_setup}{p_end}

{pstd}
Repeat the adopath line in new sessions or include it in your project do-files
or existing profile.do. Mapmaker automatically uses its packaged runtime.
The current development bundle is for Windows x64; macOS/Linux release builds
and a public release download are not yet available. See the supplied README.

{title:Syntax}

{p 8 12 2}
{cmd:mapmaker} {varname} {ifin}{cmd:, geography(}{it:pack_id|county|state|cz|tract}{cmd:)}
[{it:options}]

{synoptset 28 tabbed}{...}
{synopthdr:option}
{synoptline}
{synopt:{opt geovar(varname)}}geographic ID; defaults to the geography name{p_end}
{synopt:{opt id(varname)}}alias for geovar(){p_end}
{synopt:{opt vintage(string)}}optional boundary vintage check; shorthand county/state with 2020 selects the dated 500k pack{p_end}
{synopt:{opt revision(string)}}immutable pack revision; default 1{p_end}
{synopt:{opt datadir(path)}}user geography library; also used on installation commands{p_end}
{synopt:{opt projection(string)}}auto, named preset, or CRS such as EPSG:5070; legacy packs are fixed{p_end}
{synopt:{opt layout(string)}}auto, single, us-insets, or conus; explicit projections use a single panel{p_end}
{synopt:{opt center(string)}}longitude latitude for regional LAEA, equidistant, orthographic, or automatic UTM{p_end}
{synopt:{opt region(string)}}U.S. panel names, or west south east north bounds (date-line crossing allowed){p_end}
{synopt:{opt insets(string)}}semicolon-separated panel left bottom width height [caption] entries; positions 0-1{p_end}
{synopt:{opt grids(string)}}explicit optional grid filenames, preferably filename@sha256; installation alone has no effect{p_end}
{synopt:{opt graticule}}draw projected meridians and parallels{p_end}
{synopt:{opt distortion}}draw equal-geodesic-radius distortion circles{p_end}
{synopt:{opt nquantiles(#)}}Stata quantile bins; default 5; range 2–32{p_end}
{synopt:{opt cutvalues(numlist)}}strictly increasing custom cutoffs; excludes nquantiles(){p_end}
{synopt:{opt colorscheme(string)}}Matplotlib palette; default viridis{p_end}
{synopt:{opt colors(string)}}space/comma-separated colors; one per bin{p_end}
{synopt:{opt revcolors}}reverse palette; invertcolors is an alias{p_end}
{synopt:{opt zoomtoregion}}fit extent to selected geographic IDs, including missing values{p_end}
{synopt:{opt context}}show neighboring unsampled regions as missing when zoomed{p_end}
{synopt:{opt noborders}}suppress region boundaries{p_end}
{synopt:{opt nostates}}suppress state boundaries (shown by default){p_end}
{synopt:{opt meshstates}}accepted for compatibility; state boundaries are already enabled{p_end}
{synopt:{opt hatchmissing}}hatch missing regions{p_end}
{synopt:{opt rasterize}}rasterize polygon fills within otherwise vector output{p_end}
{synopt:{opt title(string)}}figure title{p_end}
{synopt:{opt note(string)}}figure note{p_end}
{synopt:{opt legendtitle(string)}}legend title{p_end}
{synopt:{opt labelmissing(string)}}missing-data legend label; default No data{p_end}
{synopt:{opt legdecimals(#)}}legend decimal places, 0–10{p_end}
{synopt:{opt legpercent}}multiply displayed legend values by 100 and add %{p_end}
{synopt:{opt formatstr(string)}}Stata numeric display format; default %9.3g{p_end}
{synopt:{opt nolegend}}suppress legend{p_end}
{synopt:{opt savegraph(filename)}}.pdf, .svg, or .png; default mapmaker.pdf{p_end}
{synopt:{opt saving(filename)}}alias for savegraph(){p_end}
{synopt:{opt replace}}allow replacement of an existing output{p_end}
{synopt:{opt xsize(#)} {opt ysize(#)}}figure dimensions in inches; default 10 by 6; each 2–40{p_end}
{synopt:{opt dpi(#)}}PNG/rasterized-layer resolution; default 300; range 36–1200{p_end}
{synopt:{opt nodisplay}}suppress external file preview{p_end}
{synopt:{opt unmatched(error|drop)}}unmatched selected IDs; default error{p_end}
{synoptline}

{title:Research figures: panels, layers, and saved specifications}

{pstd}
Add {cmd:by(year)} for panels with one common extent and a shared scale by default.
{cmd:scale(panel)} uses separate legends; {cmd:baseline(2010)} chooses a reference
panel for shared cutoffs. {cmd:columns(3)} controls the grid and
{cmd:panelorder("2010|2020|2030")} includes explicit absent panels.
IDs must be unique within panels. Stata calculates thresholds, including optional
analytic, frequency, or probability weights. Caller data are restored on errors.

{phang2}{cmd:mapmaker income, geography(county) id(fips) by(year) scale(shared) scalesave("income-scale.json") manifest("income-manifest.json") saving("income-panels.pdf")}{p_end}

{pstd}
{cmd:classification(diverging) midpoint(0)} uses symmetric bins;
{cmd:classification(continuous) limits(0 100)} uses a clipped colorbar;
{cmd:classification(categorical) categories("Low|Medium|High")} uses named categories.
{cmd:bivariate(other) nquantiles(3) nquantiles2(3)} creates a two-dimensional legend.
Missing either variable is missing. {cmd:units()}, {cmd:xlegend()}, and {cmd:ylegend()}
name the value/axis units. The research interface uses exact stored thresholds.

{pstd}
{cmd:labels(name)} uses interior anchors and deterministic collision avoidance;
{cmd:labellimit()}, {cmd:labeldx()}, and {cmd:labeldy()} control placement.
{cmd:outline("states")} uses installed vintage-matched state boundaries;
explicit packs use {cmd:outline("pack@revision")}. Mismatches require
{cmd:allowvintagemismatch}. {cmd:highlight(flag)} emphasizes base-map regions.
{cmd:scalebar} and {cmd:northarrow} require known source CRSs and use recorded local
reference points. Fixed legacy packs cannot supply those decorations.

{pstd}
{cmd:size(population)} draws proportional-area symbols; {cmd:maptype(symbol)} uses
neutral polygons. {cmd:symbolmax()} is the largest area in square points.
{cmd:uncertain(flag)} uses a supplied 0/1 indicator, or use
{cmd:cilower(lower) ciupper(upper) reference(0)} to flag intervals containing a
reference. Missing data and missing uncertainty have distinct legend entries.
{cmd:points("places.csv")} reads x,y plus optional size,label,id,facet,panel;
{cmd:pointcrs()} declares the source CRS (default EPSG:4326).
{cmd:flows("flows.csv")} reads origin,destination,volume plus optional facet.
Flows aggregate before {cmd:flowtop()} and {cmd:flowmin()}; omitted volume is shown.

{pstd}
{cmd:style(publication|presentation|grayscale)} supplies appearance defaults.
{cmd:stylesave()} writes a JSON style; {cmd:style("paper.json")} reuses it.
{cmd:scalesave()} and {cmd:scaleuse()} preserve exact thresholds and category order.
{cmd:legendposition(right|bottom|none)} controls legends. Research figures choose
dimensions from the panel grid and default to 200 DPI. Styles never change selection.

{pstd}
{cmd:layout(tile)} uses a deterministic tile grid; {cmd:tiles("layout.json")}
supplies a revision-pinned grid. {cmd:layout(cartogram) size(population)} uses Dorling
circles with areas from {cmd:cartobase(2010)} (otherwise the baseline or first panel).
All facets reuse that geometry. The nongeographic layout is visibly labeled.

{pstd}
{cmd:manifest("figure.json")} records scales, style, dependencies, versions, hashes,
and aggregate diagnostics without storing observation rows or private layer data.
Use {cmd:mapmaker reproduce describe|restore|verify, using("figure.json")}.
Restore explicitly obtains missing public resources. Retain the exact bundle,
do-file, data, and private layers to reproduce the figure.
{cmd:mapmaker geography inventory|updates|repair} manages installed resources;
{cmd:geography export pack, saving("pack.zip")} and
{cmd:geography restore, using("pack.zip")} exchange verified offline archives.

{pstd}
{cmd:mapmaker crosswalk import, using("weights.csv") saving("crosswalk.json") source(pack@rev) targetpack(pack@rev) universe("Population") method("Published weights")}
imports explicit source,target,weight fractions. Use
{cmd:mapmaker crosswalk apply, using("crosswalk.json") id(fips) value(count) frame(allocated)}
for counts, or supply {cmd:numerator(events) denominator(population)} for rates.
Weights are never renormalized; coverage and unallocated mass are reported.
{cmd:audit("allocation.json")} retains the allocation report.

{pstd}
Research commands return {cmd:r(panel_counts)} (matched, missing, absent, unmatched,
excluded, visible), {cmd:r(panels)}, and row totals. {cmd:results(new_frame)} retains
panel keys/counts. See {browse "doc/research-figures.md":doc/research-figures.md}
and the bundled {cmd:examples/research-figures.do} for complete contracts and limits.

{title:Data and classification}

{pstd}
Supply one observation per geographic ID. Aggregate repeated observations before
running Mapmaker. The command stops on duplicate IDs, missing IDs, or IDs absent
from the boundary files. {cmd:unmatched(drop)} drops unmatched IDs before
calculating bins. Mapmaker accepts string and numeric FIPS and adds leading zeros
to reach the expected width. Store tract IDs as strings or doubles; {cmd:float}
cannot preserve all 11 digits. Reimport rounded IDs from the original data.

{pstd}
{cmd:if}/{cmd:in} select the classification sample. Quantiles use Stata's
{cmd:xtile}/{cmd:_pctile}. Cutoff intervals are upper-inclusive: values equal to a
cutoff stay in the lower bin. Mapmaker reports and retains empty bins caused by
ties. Under quantile classification, a constant sample uses one color. An
all-missing sample produces an error. Mapmaker excludes system and extended
missing values from quantiles and shades them in gray. Zero remains a valid value.

{pstd}
Zoom changes the displayed extent, without further changing the sample or bins.
Zoom shows selected regions; {cmd:context} additionally fills neighboring regions
outside the sample in gray. The full map shows all areas in the boundary files,
with separate panels for Alaska, Hawaii, and Puerto Rico where available.
Mapmaker restores the caller's data and sort order after success or failure.

{title:Geography}

{pstd}
Run {cmd:mapmaker_setup} to check the included states, counties, and commuting zones.
The included defaults come from the original Mapmaker project; their boundary
dates are unverified and they retain the identifier {cmd:legacy}. Dated Census
packs are separate downloads. The bundled runtime is selected automatically.

{phang2}{cmd:mapmaker geography browse}{p_end}
{phang2}{cmd:mapmaker geography browse, installed}{p_end}
{phang2}{cmd:mapmaker geography browse, country(US) level(cd) vintage(2020)}{p_end}
{phang2}{cmd:mapmaker geography search "tract"}{p_end}
{phang2}{cmd:mapmaker geography describe us_cd116_2020}{p_end}
{phang2}{cmd:mapmaker geography install us_cd116_2020, revision(1)}{p_end}
{phang2}{cmd:mapmaker geography remove us_cd116_2020, revision(1)}{p_end}

{pstd}
The optional catalog includes national/state Census families, ERS and Penn State
commuting zones with membership tables, Congresses 1-119, Natural Earth, NUTS,
Canada, Australia, the UK, geoBoundaries, environmental regions, and a county-level
block pilot. See doc/geographies.md in the installation for coverage and source terms.
Named packs require {cmd:id()}; provider ID conventions differ. Historical UCLA IDs
are not four-digit Census district IDs. String IDs retain letters and punctuation.
All management commands preserve the active dataset.

{pstd}
Browse filters include {cmd:country()}, {cmd:level()}, {cmd:vintage()},
{cmd:state()} (two-digit U.S. FIPS), {cmd:provider()}, {cmd:decade()},
{cmd:search()}, and {cmd:installed}. The default page has 50 matches; use
{cmd:limit()}, {cmd:offset()}, or {cmd:all} for more.

{phang2}{cmd:mapmaker geography attributes world_ne_country_110m, frame(world_names)}{p_end}
{phang2}{cmd:mapmaker geography membership us_ers_cz_2020, frame(county_to_cz)}{p_end}
{phang2}{cmd:mapmaker geography ids us_county_2020_500k, saving("county-ids.csv")}{p_end}
{phang2}{cmd:mapmaker geography diagnose us_county_2020_500k, id(fips) frame(checks)}{p_end}
{phang2}{cmd:mapmaker geography preview world_ne_country_110m, saving("world.pdf")}{p_end}
{phang2}{cmd:mapmaker geography verify world_ne_country_110m}{p_end}

{pstd}
Table commands accept {cmd:frame(new_name)} or {cmd:saving(filename.csv)}.
Existing frames are rejected; existing files require {cmd:replace}. They return
{cmd:r(path)} and, when applicable, {cmd:r(frame)}. Diagnostic suggestions do not
rewrite IDs and cannot prove vintage compatibility. Preview accepts PNG/PDF/SVG
and optional {cmd:projection()}. Exact ERS/PSU definitions remain separate from
{cmd:cz-legacy}; ERS 2020 uses 2024 county polygons to match its final membership.

{pstd}
Optional packs are stored in the user application-data directory. Override with
{cmd:datadir(path)} on both installation and mapping commands, or the
{cmd:MAPMAKER_DATA} environment variable. Bundled packs are retained when user
copies are removed. Maps use revision 1 unless another revision is requested.
An unavailable pack produces an installation command; rendering never downloads.

{pstd}
{cmd:mapmaker geography refresh} downloads the catalog from the repository's
master branch after publication. Failed refreshes preserve the cached catalog.
The shipped catalog works immediately, including installation from reviewed providers.
For an offline update, use {cmd:mapmaker geography refresh, using("geographies.json")}.

{title:Projections and imports}

{phang2}{cmd:mapmaker projection browse}{p_end}
{phang2}{cmd:mapmaker projection browse, all}{p_end}
{phang2}{cmd:mapmaker projection search "Albers"}{p_end}
{phang2}{cmd:mapmaker projection describe "EPSG:5070"}{p_end}

{pstd}
Projection algorithms and CRS definitions are included. Presets include
regional Albers/LAEA, Atlantic/Pacific Equal Earth, Robinson, Winkel Tripel,
automatic UTM, polar stereographic/equal-area, azimuthal equidistant,
orthographic, interrupted Goode, and Web Mercator. See doc/projections.md
for names, properties, datums, clipping rules, and examples.
{cmd:projection(auto)} uses regional Albers projections with U.S. insets for dated
Census packs; imported packs default to Equal Earth in one panel. Explicit CRS
selection uses one panel and should suit the mapped region. Legacy packs have
fixed projections. Rendering never downloads grids or permits ballpark
transformations. It selects one available operation and records its exact
pipeline; higher-accuracy operations requiring grids are reported. Optional
grids are installed through Stata and used only with explicit {cmd:grids()}.
The shared PROJ grid cache cannot silently alter an export.

{phang2}{cmd:mapmaker projection recommend, geography(world_ne_country_110m) purpose(thematic)}{p_end}
{phang2}{cmd:mapmaker projection compare, geography(world_ne_country_110m) choices(equalearth robinson winkeltripel) graticule distortion saving("options.pdf")}{p_end}
{phang2}{cmd:mapmaker projection preflight equalearth, crs(EPSG:27700) region(-6 50 2 58)}{p_end}
{phang2}{cmd:mapmaker projection grids, installed}{p_end}
{phang2}{cmd:mapmaker projection install uk_os_OSTN15_NTv2_OSGBtoETRS.tif}{p_end}
{phang2}{cmd:mapmaker projection cache}{p_end}
{phang2}{cmd:mapmaker projection cache limit, limit(32)}{p_end}
{phang2}{cmd:mapmaker projection cache purge}{p_end}

{pstd}
Recommend purposes: thematic, reference, distance, local, globe, web.
Preflight and recommend accept {cmd:saving(report.json)}. Compare exports 2-6
choices with the same boundaries/style to PDF/SVG/PNG. Outputs require
{cmd:replace} to overwrite. All commands accept {cmd:datadir()}.

{pstd}
Orthographic maps clip to the visible hemisphere, polar presets to their
hemisphere, and LAEA/equidistant exclude 0.1 degrees around the antipode.
Source projected edges are sampled at most every 25 km and geographic edges
at 0.5 degrees. These are cartographic views, not analytic GIS intersections.
Clipped/excluded IDs, resolved centers, CRSs, operations, grid hashes, versions,
and layout settings are embedded in output metadata. Boundary caching defaults
to 64 MiB and contains no research values; limit(0) disables it.

{phang2}{cmd:mapmaker geography import, using("districts.zip") name(my_districts) idfield(GEOID)}{p_end}
{phang2}{cmd:mapmaker income, geography(my_districts) id(district_id) projection("EPSG:5070") saving("districts.pdf")}{p_end}

{pstd}
Import polygon GeoJSON, a .shp with .shx/.dbf/.prj sidecars, or a ZIP containing one shapefile.
Use {cmd:crs("EPSG:...")} when source CRS metadata is missing. Custom IDs must
be unique strings of at most 244 UTF-8 bytes. Import accepts 2D polygons and does
not silently repair topology. Geographic polygons are split at the date line.
Older spherical commuting-zone sources preserve their supplied projection under auto.
New non-state packs draw region borders; separate state-outline overlays are
currently provided by legacy packs and state packs.

{title:Output}

{pstd}
PDF and SVG preserve sharp boundaries at any scale. {cmd:rasterize} saves polygon
fills as images within those files while keeping text and lines as vectors.
PDF embeds fonts; SVG draws text as paths. PNG uses the requested DPI.
Mapmaker saves external files, which Stata's Graph Editor cannot edit.
Text appears as typed; Mapmaker does not interpret TeX commands.

{pstd}
{cmd:formatstr()} accepts Stata numeric formats and cannot be combined with
{cmd:legdecimals()} or {cmd:legpercent}. Distinct cutoffs that round to the same
label cause an error; increase the display precision. If the legend does not
fit, increase the figure size or shorten its labels.

{title:Stored results}

{pstd}
Run {cmd:return list} after a map to inspect these results:

{synoptset 22}{...}
{synopt:{cmd:r(N)}}matched selected areas, including missing values{p_end}
{synopt:{cmd:r(N_missing)}}matched areas with missing mapped values{p_end}
{synopt:{cmd:r(N_unmatched)}}selected IDs dropped by unmatched(drop){p_end}
{synopt:{cmd:r(bins)}}number of bins, including empty bins{p_end}
{synopt:{cmd:r(counts)}}row matrix of nonmissing observations per bin{p_end}
{synopt:{cmd:r(cutoffs)}}row matrix of cutoffs, when present{p_end}
{synopt:{cmd:r(output)}}output file path{p_end}
{synopt:{cmd:r(geography)}}geography type, including cd, puma20, or custom{p_end}
{synopt:{cmd:r(pack)}}boundary identifier, such as county-legacy{p_end}
{synopt:{cmd:r(pack_revision)}}boundary revision{p_end}
{synopt:{cmd:r(vintage)}}boundary vintage{p_end}
{synopt:{cmd:r(projection)}}requested projection (auto by default){p_end}
{synopt:{cmd:r(version)}}Mapmaker version{p_end}

{pstd}
The output file also records engine and boundary versions, a geometry hash,
cutoffs, labels, and bin counts in its metadata.

{title:Examples}

{pstd}
After adding the bundle to adopath, run these commands from your project directory:

{phang2}{cmd:mapmaker income, geography(county) id(fips) saving("income.pdf") replace}{p_end}
{phang2}{cmd:mapmaker geography install us_06_tract_2020_500k}{p_end}
{phang2}{cmd:mapmaker poverty, geography(us_06_tract_2020_500k) id(geoid) zoomtoregion cutvalues(.1 .2 .3) legpercent saving("california.svg") replace}{p_end}

{pstd}
The tract example assumes California observations and poverty measured as a share
between 0 and 1. The bundled examples/quickstart.do uses synthetic data and restores
the caller's dataset.
Run {cmd:mapmaker doctor} to list installation paths and available boundary files.
See the repository's {cmd:readme.md} for installation and examples with synthetic data.

{title:Developer runtime overrides}

{pstd}
Normal bundle users do not need runtime options. For source development,
{cmd:python(filename)} selects a Python interpreter and {cmd:engine(filename)}
selects another packaged executable. Use at most one. A source checkout can use
its .venv automatically when no bundle is present. These options do not change
Stata's Python settings. Source setup is documented in doc/mapmaker-v2-design.md.
