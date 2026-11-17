# Geography library

Mapmaker's optional catalog covers the P1–P3 geography families in the roadmap.
The normal installation still includes the original U.S. county, state, and
commuting-zone packs. Additional boundaries download only when explicitly
installed. No Python setup is needed in the prepackaged distribution.

## Find a boundary definition

```stata
mapmaker geography browse
mapmaker geography browse, installed
mapmaker geography browse, country(US) level(tract) state(06)
mapmaker geography browse, provider(geoBoundaries) limit(20) offset(20)
mapmaker geography browse, level(cd) decade(1990)
mapmaker geography search "school"
mapmaker geography describe us_ers_cz_2020
```

Browsing is offline and shows 50 matches by default, with installed packs first.
Use `limit()`, `offset()`, or `all` for longer lists. `state()` uses two-digit U.S.
FIPS codes. `country()` uses the provider's catalog country code: US, CA, AU, GB,
EU, WORLD, or a three-letter ISO code for geoBoundaries. A description shows the
source, license, checksum, download bytes, feature count, ID examples, and source
fields. An installation's exact disk usage is shown once it exists.

The catalog distinguishes a boundary definition, source-file edition, and pack
revision. For example, a Census 2013 file can contain **2010-defined** tracts or
PUMAs. A Congress number identifies a congressional plan; a decade is only a
search filter. Do not substitute a different edition merely because its IDs match.

## Included optional families

| Family | Implemented scope | Notes |
| --- | --- | --- |
| States and counties | Census 2013, 2020, 2024, 2025 snapshots, plus legacy defaults | Retains county equivalents and Connecticut's change to planning regions |
| Tracts and PUMAs | State files for 2010 definitions (2013 snapshot; Maine PUMAs use 2014) and 2020 definitions, wherever the provider supplies them | `puma10` and `puma20` are distinct levels; full GEOIDs include the state |
| Metro/micro, combined areas, metropolitan divisions | CBSA, CSA, and metropolitan-division snapshots for 2020, 2024, 2025 | CBSA includes metro and micro types; attributes retain the distinction. Division GEOID includes its CBSA prefix |
| Congressional districts | Modern Census snapshots and UCLA's Congress-by-Congress collection, Congresses 1–119 | UCLA uses its own plan/district IDs, not four-digit Census GEOIDs |
| Places and county subdivisions | 2020 generalized state files | Place attributes distinguish incorporated places from census-designated places |
| School and legislative districts | Elementary, secondary, unified; upper and lower legislative chambers | Separate state packs; alphanumeric legislative identifiers are retained as strings |
| ZCTAs | 2020 national generalized ZCTAs | Approximate ZIP areas, not USPS postal polygons or a complete list of ZIP codes |
| Tribal/Native areas | 2020 AIANNH and Alaska Native Regional Corporations | Provider area types and overlaps retained; these are not an exclusive state hierarchy |
| Block groups and voting districts | 2020 state files where published | Voting district IDs can contain letters and punctuation |
| Census blocks | **Advanced pilot:** DC and the five Rhode Island counties, 2020 | County-only installed packs; source download is statewide and its full size is disclosed |
| Commuting zones | ERS 1990, 2000, final 2020; Penn State 2010, 2020 | Five distinct definitions with exact county-membership tables; see below |
| World countries and coastlines | Natural Earth 110m, 50m, 10m | Countries use NE_ID; ISO alternatives remain attributes. Coastlines are line packs |
| Europe | NUTS 1–3, editions 2010, 2013, 2016, 2021, 2024, at 1:10 million | NUTS_ID and country attributes retained; GISCO-specific use provisions apply |
| Canada | 2021 provinces, census divisions by province, CMA/CA province parts, tracts by province | Official cartographic service, generalized by 0.001 degrees; UID/DGUID retained |
| Australia | ASGS 2021 and 2026 states, SA2, SA3, SA4, LGAs | GDA2020 sources; provider nonspatial codes are reported separately from mapped polygons |
| United Kingdom | December 2024 local authorities and July 2024 Westminster constituencies | UK coverage, generalized coastline-clipped ONS boundaries; official codes retained |
| Other countries | gbOpen ADM1 and ADM2 across the provider's available country catalog | 379 country/level packs in the audited snapshot; each retains its own year, original source and license |
| Environmental regions | EPA Level III/IV ecoregions; USGS HUC2/HUC4 and HUC8 partitioned by HUC2 | Checksum-pinned source snapshots; EPA parts are dissolved by region code and retain their supplied Albers projection under auto; watersheds use documented service generalization |
| Historical NHGIS boundaries | Discoverable manual-import recipe | Download under the provider's terms; Mapmaker does not mirror restricted files |

Sources and usage details: [Census cartographic boundaries](https://www.census.gov/geographies/mapping-files/time-series/geo/carto-boundary-file.html),
[TIGER/Line](https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html),
[UCLA congressional boundaries](https://cdmaps.polisci.ucla.edu/),
[Natural Earth terms](https://www.naturalearthdata.com/about/terms-of-use/),
[Natural Earth boundary policy](https://www.naturalearthdata.com/about/disputed-boundaries-policy/),
[GISCO](https://gisco-services.ec.europa.eu/distribution/v2/nuts/),
[Statistics Canada](https://geo.statcan.gc.ca/geo_wa/rest/services/2021/Cartographic_boundary_files/MapServer),
[ABS](https://www.abs.gov.au/statistics/standards/australian-statistical-geography-standard-asgs/edition-4-july-2026-june-2031/access-and-downloads/digital-boundary-files),
[ONS licensing](https://www.ons.gov.uk/methodology/geography/licences),
[geoBoundaries API](https://www.geoboundaries.org/api.html),
[EPA](https://www.epa.gov/eco-research/level-iii-and-iv-ecoregions-continental-united-states),
[USGS WBD](https://www.usgs.gov/national-hydrography/access-national-hydrography-products),
and [NHGIS use terms](https://www.nhgis.org/citation-and-use-nhgis-data).

## Install, inspect, and draw

```stata
mapmaker geography install world_ne_country_110m
mapmaker geography attributes world_ne_country_110m, frame(world_names)
mapmaker geography preview world_ne_country_110m, saving("world-preview.pdf")
mapmaker geography verify world_ne_country_110m

mapmaker geography install us_06_tract_2020_500k
mapmaker geography ids us_06_tract_2020_500k, saving("tract-ids.csv")
mapmaker geography diagnose us_06_tract_2020_500k, id(geoid) frame(join_checks)
mapmaker poverty, geography(us_06_tract_2020_500k) id(geoid) ///
    saving("poverty.pdf")
```

`ids`, `attributes`, and `membership` expose CSV tables. Use `frame(new_name)` to
load one into a new Stata frame, or `saving("file.csv")` to export it. Existing
frames are never overwritten; existing files require `replace`. The active
dataset is preserved. `r(path)` identifies the table or verified pack, and
`r(frame)` identifies a newly created frame. Attributes use provider column names;
Stata may normalize long/invalid variable names on import. All exported ID columns
are strings, including leading zeroes.

`diagnose` reports exact matches, missing/unmatched IDs, duplicate occurrences,
and possible whitespace/leading-zero corrections. Suggestions never modify data.
A matching ID alone cannot establish boundary-vintage compatibility. IDs can
contain up to 244 UTF-8 bytes; source identifiers are not truncated to fit.

`preview` creates a PNG, SVG, or PDF without using the active dataset. Its
`projection()` option uses the same renderer as a normal map. `verify` checks
geometry, IDs, attributes, and membership hashes. Maps retain source attribution
and license metadata; follow the provider's display/citation requirements when
publishing a figure. Natural Earth uses de facto boundaries; its ISO fields are
not a universal one-to-one country crosswalk.

## Commuting-zone definitions

```stata
mapmaker geography browse, level(cz)
mapmaker geography install us_ers_cz_2020
mapmaker geography membership us_ers_cz_2020, frame(county_to_cz)
mapmaker geography attributes us_ers_cz_2020, frame(cz_names)
```

ERS 2020 is the **final January 9, 2026 release**, with 598 zones and 3,222 member
counties/equivalents. It is not the Penn State 2020 definition (593 zones), and it
is not the preliminary ERS release. [ERS definitions and downloads](https://ers.usda.gov/data-products/commuting-zones-and-labor-market-areas)

The final ERS table includes Connecticut planning-region IDs. Its Mapmaker pack
therefore explicitly depends on the **2024** Census county boundaries, which
match every member ID. Installation dissolves these counties by the exact table;
it never silently substitutes old Connecticut counties. The manifest records the
dependency geometry hash, excluded nonmember territories, and any explicitly
authorized validity repairs. The county dependency remains installed and is shown
in the inventory; it may be removed separately after the derived pack is built.

ERS 1990/2000 and Penn State 2010/2020 polygons come from the
[Penn State Labor-sheds collection](https://sites.psu.edu/psucz/data/). The first
three use a provider-defined spherical datum, so `projection(auto)` preserves
their original Lambert azimuthal projection in one panel. Mapmaker does not
invent a transformation to WGS84. The 2020 sources support the normal regional
layout. County membership is normalized from original provider tables, with both
original and normalized checksums recorded. Zone IDs are decimal strings without
leading zeroes; county FIPS are padded to five digits.

The existing `geography(cz)` alias still selects `cz-legacy` for compatibility.
It does not acquire a verified year merely because documented alternatives now
exist. Use an explicit pack ID to choose one of the new definitions.

## Local and restricted-source import

```stata
mapmaker geography import, using("my-boundaries.geojson") ///
    name(my_regions) idfield(region_code) vintage(2020)
mapmaker geography import, using("nhgis-boundaries.zip") ///
    name(my_historical_counties) idfield(GISJOIN) vintage(1940)
```

Polygon GeoJSON (WGS84/CRS84) and shapefiles are supported. A shapefile ZIP must
contain exactly one layer for a user import; retain `.shp`, `.shx`, `.dbf`, and
`.prj` sidecars. Missing CRS requires an explicit `crs()` override. Older
non-WGS84 GeoJSON also requires an explicit override. Source-specific exceptions
such as PolygonZ-to-XY handling are reviewed catalog recipes, not silent defaults
for arbitrary imports.

Geographic polygons and line packs are split at the date line. This supports the
world catalog with the standard Equal Earth/Robinson views. Arbitrary projection
centers, horizon clipping, and polar encircling polygons still need further
projection work; a failed transformation does not trigger a datum-grid download.

Geographic relationship tables and statistical allocation are distinct from
mapping. Membership tables are available for inspection, but Mapmaker does not
automatically convert counts, rates, or medians between changing boundaries.
General Census/NHGIS crosswalk allocation, GeoPackage import, general overlays,
UK small-area expansion, GISCO LAU/FUA, additional annual LGA releases, and wider
block-pilot coverage remain follow-on work.

## Maintainer verification

`tools/expand_catalog.py` discovers actual provider links, downloads sources into
`.cache`, audits identifiers/counts, and adds checksums and sizes to the catalog.
It supports `census`, `international`, `geoboundaries`, `historical`, `environment`,
and `blocks`. `tools/prepare_commuting.py` normalizes the small membership resources
included in the bundle. Historical XLS parsing is a build dependency only.

`tools/check_expansion.py` compiles cached sources offline in temporary libraries,
verifies the resulting packs, renders representative families, and reports measured
installed bytes and errors. It does not retain every compiled pack. Its
`--pending` option checks new sources and previous failures after a completed run.
`tests/expanded.do` exercises table frames, diagnostics, previews, and local
GeoJSON import in Stata. Download snapshots are fixed by SHA-256: provider changes
require catalog review and a new revision, not silent replacement.
