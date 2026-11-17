version 16
clear all
set more off
adopath ++ "."
local library `"`c(pwd)'/.cache/expanded-integration/library"'
capture mkdir "tests/output/projections"
input str5 identifier double value
"01001" 1
"01003" 2
end
quietly datasignature
local signature `r(datasignature)'
mapmaker projection browse
mapmaker projection describe canada-lambert
mapmaker projection preflight equalearth, crs(EPSG:27700) region(-6 50 2 58)
mapmaker projection grids, search(uk_os) limit(2)
mapmaker projection recommend, geography(world_ne_country_110m) purpose(thematic) datadir(`"`library'"')
mapmaker projection compare, geography(world_ne_country_110m) choices(equalearth robinson winkeltripel) ///
    graticule distortion saving("tests/output/projections/stata-comparison.pdf") replace datadir(`"`library'"')
mapmaker geography preview world_ne_country_110m, projection(orthographic) center(-96 40) ///
    graticule saving("tests/output/projections/stata-globe.png") replace datadir(`"`library'"')
mapmaker value, geography(us_county_2020_500k) id(identifier) layout(conus) ///
    saving("tests/output/projections/stata-conus.pdf") cutvalues(1.5) replace nodisplay datadir(`"`library'"')
mapmaker geography preview us_county_2020_500k, region(alaska hawaii) layout(us-insets) ///
    insets("alaska .03 .2 .6 .6 Alaska (scaled); hawaii .68 .2 .25 .25 Hawaii") ///
    saving("tests/output/projections/stata-insets.svg") replace datadir(`"`library'"')
mapmaker projection cache, datadir(`"`library'"')
capture noisily mapmaker projection compare, geography(world_ne_country_110m) choices(equalearth robinson) ///
    saving("tests/output/projections/stata-comparison.pdf") datadir(`"`library'"')
assert _rc == 459
capture noisily mapmaker geography preview world_ne_country_110m, projection(auto-utm) ///
    saving("tests/output/projections/invalid.pdf") replace datadir(`"`library'"')
assert _rc == 459
quietly datasignature
assert "`r(datasignature)'" == "`signature'"
display "MAPMAKER_PROJECTION_TESTS_PASSED"
