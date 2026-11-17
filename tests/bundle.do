* Run after building the platform bundle; uses no python() or engine() override.
version 16
clear all
set more off
local root `"`c(pwd)'"'
local target windows-amd64
args target_override
if "`target_override'" != "" local target `target_override'
local bundle `"`root'/dist/mapmaker-`target'"'
adopath ++ `"`bundle'"'
capture mkdir tests/output
capture mkdir tests/output/bundle
* Leave the source directory so Stata cannot resolve source ado files via '.'.
cd `"`root'/tests/output/bundle"'
quietly findfile mapmaker.ado
assert strpos(`"`r(fn)'"', "dist") > 0
mapmaker_setup
mapmaker geography browse, installed
mapmaker projection browse
input str2 state double value
"01" 1
"02" 2
"04" 3
"05" 4
"06" 5
end
mapmaker value, geography(state) id(state) nquantiles(3) ///
    saving("stata-bundled.pdf") replace nodisplay
assert r(N) == 5
confirm file stata-bundled.pdf
* Exercise the exact quickstart shipped to users and its no-overwrite behavior.
quietly datasignature
local original `r(datasignature)'
capture erase mapmaker-example.pdf
do `"`bundle'/examples/quickstart.do"'
confirm file mapmaker-example.pdf
quietly datasignature
assert "`r(datasignature)'" == "`original'"
capture noisily do `"`bundle'/examples/quickstart.do"'
assert _rc == 602
quietly datasignature
assert "`r(datasignature)'" == "`original'"
cd `"`root'"'
display "MAPMAKER_STATA_BUNDLE_TEST_PASSED"
