* Run tools/build_catalog.py and tools/check_catalog.py before this integration test.
version 16
clear all
set more off
adopath ++ "."
local library `"`c(pwd)'/.cache/geography-smoke/library"'
input str4 district double value
"0601" 1
"0602" 2
"0603" 3
"0604" 4
end
quietly datasignature
local original `r(datasignature)'
mapmaker_setup
mapmaker geography browse, level(cd) datadir(`"`library'"')
mapmaker geography browse, installed datadir(`"`library'"')
mapmaker geography search "PUMA", datadir(`"`library'"')
mapmaker geography describe us_cd116_2020, datadir(`"`library'"')
mapmaker projection browse
mapmaker projection describe "EPSG:5070"
mapmaker geography refresh, using("catalog/geographies.json") datadir(`"`library'"')
quietly datasignature
assert "`r(datasignature)'" == "`original'"
mapmaker value, geography(us_cd116_2020) id(district) revision(1) ///
    datadir(`"`library'"') projection("EPSG:5070") zoom ///
    saving("tests/output/library/stata-districts.pdf") replace nodisplay
assert r(N) == 4
assert "`r(pack)'" == "us_cd116_2020"
assert "`r(pack_revision)'" == "1"
assert "`r(vintage)'" == "2020"
quietly datasignature
assert "`r(datasignature)'" == "`original'"
capture noisily mapmaker value, geography(us_cd116_2020) id(district) revision(99) ///
    datadir(`"`library'"') saving("tests/output/library/missing.png") nodisplay
assert _rc == 459
quietly datasignature
assert "`r(datasignature)'" == "`original'"
* Import a local ZIP, then remove only that imported revision.
capture noisily mapmaker geography remove test_import, datadir(`"`library'"')
mapmaker geography import, name(test_import) ///
    using(".cache/catalog-sources/cb_2020_us_cd116_500k.zip") idfield(GEOID) datadir(`"`library'"')
mapmaker value, geography(test_import) id(district) datadir(`"`library'"') ///
    projection("EPSG:5070") zoom saving("tests/output/library/stata-import.svg") replace nodisplay
assert r(N) == 4
mapmaker geography remove test_import, datadir(`"`library'"')
quietly datasignature
assert "`r(datasignature)'" == "`original'"
display "MAPMAKER_LIBRARY_TESTS_PASSED"
