version 16
clear all
set more off
adopath ++ "."
local library `"`c(pwd)'/.cache/expanded-integration/library"'
input str6 fips double value
"1001" 1
"01001" 2
"01001" 3
"BAD" 4
end
quietly datasignature
local original `r(datasignature)'
mapmaker geography browse, country(US) state(06) level(tract) datadir(`"`library'"')
mapmaker geography browse, provider(geoBoundaries) limit(3) offset(2) datadir(`"`library'"')
mapmaker geography describe nhgis_historical_boundaries, datadir(`"`library'"')
mapmaker geography attributes world_ne_country_110m, frame(world_names) datadir(`"`library'"')
frame world_names: assert _N == 177
frame world_names: confirm string variable mm_id
capture noisily mapmaker geography attributes world_ne_country_110m, frame(world_names) datadir(`"`library'"')
assert _rc == 110
mapmaker geography ids us_county_2020_500k, frame(county_ids) datadir(`"`library'"')
frame county_ids: assert _N == 3234
mapmaker geography membership us_ers_cz_2020, frame(cz_membership) datadir(`"`library'"')
frame cz_membership: assert _N == 3222
mapmaker geography diagnose us_county_2020_500k, id(fips) frame(join_checks) datadir(`"`library'"')
frame join_checks: assert _N == 3
frame join_checks: assert suggested_id == "01001" if mm_id == "1001"
frame join_checks: assert duplicate == "1" if mm_id == "01001"
mapmaker geography verify us_ers_cz_2020, datadir(`"`library'"')
mapmaker geography preview world_ne_country_110m, saving("tests/output/expansion/stata-world.pdf") replace datadir(`"`library'"')
quietly datasignature
assert "`r(datasignature)'" == "`original'"
capture noisily mapmaker geography remove expansion_import, datadir(`"`library'"')
mapmaker geography import, using("tests/output/expansion/import_fixture.geojson") name(expansion_import) idfield(code) datadir(`"`library'"')
mapmaker geography attributes expansion_import, frame(imported_names) datadir(`"`library'"')
frame imported_names: assert _N == 1
frame imported_names: assert strlen(mm_id) > 32
frame imported_names: generate double mapped_value = 1
frame imported_names: mapmaker mapped_value, geography(expansion_import) id(mm_id) cutvalues(.5) ///
    saving("tests/output/expansion/stata-long-id.svg") replace nodisplay datadir(`"`library'"')
mapmaker geography remove expansion_import, datadir(`"`library'"')
quietly datasignature
assert "`r(datasignature)'" == "`original'"
display "MAPMAKER_EXPANDED_TESTS_PASSED"
