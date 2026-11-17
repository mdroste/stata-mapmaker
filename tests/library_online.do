* Explicit online integration test. Installs into a test-only directory, then removes it.
version 16
clear all
set more off
adopath ++ "."
local library `"`c(pwd)'/tests/output/online-library"'
mapmaker geography install us_cd111_2010, datadir(`"`library'"')
mapmaker geography browse, installed datadir(`"`library'"')
input str4 district double value
"0601" 1
"0602" 2
end
mapmaker value, geography(us_cd111_2010) id(district) datadir(`"`library'"') ///
    nquantiles(2) zoom saving("tests/output/online-districts.png") replace nodisplay
assert r(N) == 2
mapmaker geography remove us_cd111_2010, datadir(`"`library'"')
display "MAPMAKER_ONLINE_LIBRARY_TESTS_PASSED"
