version 16
clear all
set more off
local root `"`c(pwd)'"'
local bundle `"`root'/dist/mapmaker-windows-amd64"'
local library `"`root'/.cache/projection-integration/library"'
adopath ++ `"`bundle'"'
cd `"`root'/tests/output/projections"'
quietly findfile mapmaker.ado
assert strpos(`"`r(fn)'"', "dist") > 0
input str2 state double value
"01" 1
"02" 2
"06" 3
end
quietly datasignature
local signature `r(datasignature)'
mapmaker value, geography(state) id(state) layout(conus) ///
    cutvalues(1.5) saving("bundled-legacy-conus.pdf") replace nodisplay
mapmaker projection compare, geography(world_ne_country_110m) ///
    choices(equalearth orthographic interrupted-goode) center(-96 40) graticule ///
    saving("bundled-stata-comparison.pdf") replace datadir(`"`library'"')
mapmaker projection preflight equalearth, crs(EPSG:27700) region(-6 50 2 58) ///
    grids(uk_os_OSTN15_NTv2_OSGBtoETRS.tif) saving("bundled-grid-preflight.json") ///
    replace datadir(`"`library'"')
mapmaker projection verify uk_os_OSTN15_NTv2_OSGBtoETRS.tif, datadir(`"`library'"')
capture noisily mapmaker geography preview world_ne_country_110m, projection(equalearth) center(0 0) ///
    saving("invalid-center.pdf") replace datadir(`"`library'"')
assert _rc == 459
quietly datasignature
assert "`r(datasignature)'" == "`signature'"
cd `"`root'"'
display "MAPMAKER_PROJECTION_BUNDLE_TESTS_PASSED"
