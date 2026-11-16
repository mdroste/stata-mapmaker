{smcl}
{* *! version 2.0.0a1 16nov2026}{...}
{title:mapmaker — Choropleth maps with direct PDF, SVG, and PNG output}

{pstd}
Working alpha. The source version requires an explicitly selected Python
environment. Self-contained binary releases are not yet available.

{title:Syntax}

{p 8 12 2}
{cmd:mapmaker} {varname} {ifin}{cmd:, geography(}{it:county|state|cz|tract}{cmd:)}
[{it:options}]

{synoptset 28 tabbed}{...}
{synopthdr:option}
{synoptline}
{synopt:{opt geovar(varname)}}geographic ID; defaults to the geography name{p_end}
{synopt:{opt id(varname)}}alias for geovar(){p_end}
{synopt:{opt vintage(string)}}only {cmd:legacy} is currently available{p_end}
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
{synopt:{opt xsize(#)} {opt ysize(#)}}figure dimensions in inches; default 10 by 6{p_end}
{synopt:{opt dpi(#)}}PNG/rasterized-layer resolution; default 300{p_end}
{synopt:{opt nodisplay}}suppress external file preview{p_end}
{synopt:{opt unmatched(error|drop)}}unmatched selected IDs; default error{p_end}
{synopt:{opt python(filename)}}explicit developer Python; leaves Stata Python settings unchanged{p_end}
{synopt:{opt engine(filename)}}explicit frozen rendering executable{p_end}
{synoptline}

{title:Data and classification}

{pstd}
Supply one observation per geographic ID. Duplicate IDs, missing IDs, and IDs
absent from the geographic pack produce errors. {cmd:unmatched(drop)} explicitly
drops unmatched IDs before calculating bins. Aggregation is the caller's responsibility.
String and numeric FIPS are accepted and padded to the expected width. Tract
IDs stored as {cmd:float} are rejected because their precision is insufficient;
reimport the source as strings or doubles.

{pstd}
{cmd:if}/{cmd:in} select the classification sample. Quantiles use Stata's
{cmd:xtile}/{cmd:_pctile}. Cutoff intervals are upper-inclusive: values equal to a
cutoff stay in the lower bin. Ties may create empty bins, which are reported and
retained. A constant sample uses one color. An all-missing sample produces an error.
System and extended missing values are excluded from quantiles and rendered as
missing. Zero remains a valid value.

{pstd}
Zoom changes the displayed extent, without further changing the sample or bins.
Zoom shows selected regions; {cmd:context} additionally fills neighboring regions
outside the sample in the missing-data style. The normal extent
includes all features in the pack, with separate geographic inset panels where
available. The caller's data and sort order are restored on both success and failure.

{title:Geography}

{pstd}
This alpha uses legacy assets from the original project. Source vintage is
unverified. The compiler records source hashes, projection parameters, and
excluded/degenerate IDs in each pack's manifest. It uses spherical Albers
projections prepared at build time. No arbitrary projection or shapefile import
is currently offered. New Census vintages require separately verified packs.

{title:Output}

{pstd}
PDF and SVG use vector geometry unless {cmd:rasterize} is requested. PDF embeds
subset fonts; SVG converts text to paths for portable appearance. PNG uses the
requested DPI. Exported graphics are external files and cannot be edited with
Stata's Graph Editor. Text is literal; a TeX installation is unnecessary.

{pstd}
{cmd:formatstr()} accepts Stata numeric formats and cannot be combined with
{cmd:legdecimals()} or {cmd:legpercent}. Distinct cutoffs that round to the same
label cause an error, requiring more display precision. Legends that do not fit
cause an error requiring a larger figure or shorter labels.

{title:Stored results}

{pstd}
{cmd:r(N)}, {cmd:r(N_missing)}, {cmd:r(N_unmatched)}, {cmd:r(bins)},
{cmd:r(counts)}, {cmd:r(cutoffs)} when cutoffs exist, {cmd:r(output)},
{cmd:r(geography)}, {cmd:r(pack)}, {cmd:r(pack_revision)}, and {cmd:r(version)}.
Engine/pack versions, geometry hash, cutoffs, and bin counts are embedded in the
exported file's metadata. The renderer receives IDs and bin assignments, without
the remaining source dataset or unneeded raw values.

{title:Examples}

{phang2}{cmd:mapmaker income, geo(county) id(fips) saving("income.pdf") replace}{p_end}
{phang2}{cmd:mapmaker poverty if state==6, geo(tract) id(geoid) zoom cutvalues(.1 .2 .3) legpercent saving("california.svg") replace}{p_end}

{pstd}
These examples assume a bundled renderer. In the development checkout append
{cmd:python("/path/to/.venv/bin/python")} (Windows: {cmd:.venv\Scripts\python.exe}).
Run {cmd:mapmaker doctor} to report runtime/pack paths. See {cmd:readme.md} for
installation, synthetic examples, tests, and current platform limitations.
