version 16
clear all
set more off
local root `"`c(pwd)'"'
adopath ++ `"`root'"'
local python `"`root'/.venv/bin/python"'
if "`c(os)'" == "Windows" local python `"`root'/.venv/Scripts/python.exe"'
capture mkdir tests/output
input str2 state double value
"1" 1
"02" 2
"04" 3
"05" 4
"06" 5
"08" .a
end
sort value
local originalcwd `"`c(pwd)'"'
local originalframe `"`c(frame)'"'
quietly datasignature
local original `r(datasignature)'
mapmaker value, geo(state) nq(4) saving("tests/output/test.pdf") ///
    python(`"`python'"') replace nodisplay
assert r(N)==6 & r(N_missing)==1 & r(bins)==4
matrix C=r(counts)
matrix Q=r(cutoffs)
assert C[1,1]==2 & C[1,2]==1 & C[1,3]==1 & C[1,4]==1
assert Q[1,1]==2 & Q[1,2]==3 & Q[1,3]==4
quietly datasignature
assert "`r(datasignature)'"=="`original'"
assert `"`c(pwd)'"'==`"`originalcwd'"'
assert `"`c(frame)'"'==`"`originalframe'"'
mapmaker value in 1/4, geo(state) cutvalues(2 3) zoom ///
    saving("tests/output/test-cut.png") python(`"`python'"') replace nodisplay
matrix C=r(counts)
assert r(N)==4 & C[1,1]==2 & C[1,2]==1 & C[1,3]==1
capture noisily mapmaker value, geo(state) cutvalues(2 2) python(`"`python'"') nodisplay
local badcuts = _rc
assert `badcuts' > 0
capture noisily mapmaker value, geo(state) nq(4) colorscheme(invalid) ///
    saving("tests/output/test.pdf") python(`"`python'"') replace nodisplay
assert _rc==459
quietly datasignature
assert "`r(datasignature)'"=="`original'"
replace state="01" in 2
quietly datasignature
local duplicate `r(datasignature)'
capture noisily mapmaker value, geo(state) python(`"`python'"') nodisplay
assert _rc==459
quietly datasignature
assert "`r(datasignature)'"=="`duplicate'"
replace state="99" in 2
capture noisily mapmaker value, geo(state) python(`"`python'"') nodisplay
assert _rc==459
mapmaker value, geo(state) unmatched(drop) cutvalues(2 3) ///
    saving("tests/output/unmatched.svg") python(`"`python'"') replace nodisplay
assert r(N_unmatched)==1 & r(N)==5
replace value=7
mapmaker value, geo(state) unmatched(drop) saving("tests/output/constant.pdf") ///
    python(`"`python'"') replace nodisplay
assert r(bins)==1
replace state="02" in 2
replace value=(_n-3)/10
local multiline = "Line one" + char(10) + "Line two"
mapmaker value, geo(state) cutvalues(-.1 0 .1) legpercent ///
    note(`"`multiline'"') title("Café") saving("tests/output/fractions.svg") ///
    python(`"`python'"') replace nodisplay
matrix C=r(counts)
matrix Q=r(cutoffs)
assert C[1,1]==2 & C[1,2]==1 & C[1,3]==1 & C[1,4]==2
assert abs(Q[1,1]+.1)<1e-12 & Q[1,2]==0 & abs(Q[1,3]-.1)<1e-12
replace value=.
capture noisily mapmaker value, geo(state) unmatched(drop) python(`"`python'"') nodisplay
assert _rc==2000
clear
set obs 1
gen float tract=1001020100
gen value=1
capture noisily mapmaker value, geo(tract) python(`"`python'"') nodisplay
assert _rc==459
display "MAPMAKER_STATA_TESTS_PASSED"
