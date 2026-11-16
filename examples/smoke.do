version 16
clear all
set more off
* Run from the repository root. python() is explicitly for development.
local root `"`c(pwd)'"'
adopath ++ `"`root'"'
local python `"`root'/.venv/bin/python"'
if "`c(os)'" == "Windows" local python `"`root'/.venv/Scripts/python.exe"'
capture mkdir tests/output
import delimited assets/county-legacy/ids.csv, stringcols(_all) clear
gen double example_value = 10 + mod(real(mm_id)*17, 91)
replace example_value = .a if mod(_n,41)==0
mapmaker example_value, geo(county) id(mm_id) nq(5) ///
    title("Mapmaker: county example") note("Synthetic data; provisional legacy boundaries") ///
    legendtitle("Example value") saving("tests/output/counties.pdf") ///
    python(`"`python'"') replace nodisplay
return list
mapmaker example_value, geo(county) id(mm_id) nq(5) ///
    title("Mapmaker: county example") note("Synthetic data; provisional legacy boundaries") ///
    legendtitle("Example value") saving("tests/output/counties.png") dpi(150) ///
    python(`"`python'"') replace nodisplay
mapmaker example_value if substr(mm_id,1,2)=="06", geo(county) id(mm_id) ///
    cutvalues(25 50 75) zoom title("California") saving("tests/output/california.svg") ///
    python(`"`python'"') replace nodisplay
display "MAPMAKER_SMOKE_PASSED"
