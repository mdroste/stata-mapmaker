version 16
clear all
set more off
adopath ++ .
capture log close
log using tests/features_edges.log, text replace
local out tests/output/features
local runtime python(".venv/Scripts/python.exe")
args bundled
if "`bundled'" != "" {
    local root `"`c(pwd)'"'
    adopath ++ `"`root'/dist/mapmaker-windows-amd64"'
    capture mkdir tests/output/features-bundled
    cd tests/output/features-bundled
    local out .
    local runtime
    quietly findfile mapmaker.ado
    assert strpos(`"`r(fn)'"', "dist")>0
}
input str2 state int year double(value weight numerator denominator)
"01" 2 -2 1 100 200
"02" 2 0 2 40 40
"04" 2 4 3 10 20
"01" 10 . 1 1 2
"02" 10 .a 2 1 2
"04" 10 . 3 1 2
end
local common geography(state) by(year) replace nodisplay `runtime'
mapmaker value, `common' scale(panel) panelorder("2|10|20") scalesave("`out'/empty.scale.json") saving("`out'/empty.png")
assert r(N_missing)==3
assert r(panels)==3
matrix counts=r(panel_counts)
assert counts[2,2]==3 & counts[3,3]==3
mapmaker value, `common' scaleuse("`out'/empty.scale.json") panelorder("2|10|20") saving("`out'/empty-reused.pdf")
mapmaker value, `common' classification(continuous) saving("`out'/missing.png")
capture noisily mapmaker value, `common' cutvalues(1 1) saving("`out'/bad.png")
assert _rc!=0
assert _N==6
preserve
keep if year==2
tempname f
file open `f' using "`out'/weights.csv", write text replace
file write `f' "source,target,weight" _n "01,02,.25" _n "01,04,.5" _n "02,04,1" _n
file close `f'
mapmaker crosswalk import, using("`out'/weights.csv") saving("`out'/crosswalk.json") ///
    source(state-legacy@1) targetpack(state-legacy@1) universe(population) method("Fixture fractions") replace `runtime'
mapmaker crosswalk apply, using("`out'/crosswalk.json") id(state) numerator(numerator) denominator(denominator) ///
    frame(allocated) audit("`out'/allocation.json") replace `runtime'
assert _N==3
frame allocated: assert abs(value-90/140)<1e-10 if mm_id=="04"
frame allocated: assert missing_sources==0
mapmaker crosswalk describe, using("`out'/crosswalk.json") `runtime'
restore
display "FEATURE_EDGES_OK"
log close
