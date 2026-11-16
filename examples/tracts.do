version 16
clear all
set more off
local root `"`c(pwd)'"'
adopath ++ `"`root'"'
local python `"`root'/.venv/bin/python"'
if "`c(os)'" == "Windows" local python `"`root'/.venv/Scripts/python.exe"'
capture mkdir tests/output
import delimited assets/tract-legacy/ids.csv, stringcols(_all) clear
* Keep Los Angeles County. Synthetic data make this example distributable.
keep if substr(mm_id,1,5)=="06037"
gen double example_value=mod(_n*37,100)/100
replace example_value=. if mod(_n,37)==0
timer clear 1
timer on 1
foreach extension in png pdf svg {
    mapmaker example_value, geo(tract) id(mm_id) zoom nq(5) ///
        title("Los Angeles County: census tracts") legendtitle("Synthetic share") ///
        note("Synthetic data; provisional legacy tract boundaries") legpercent ///
        saving("tests/output/la-tracts.`extension'") dpi(150) python(`"`python'"') replace nodisplay
}
timer off 1
timer list 1
display "MAPMAKER_TRACTS_PASSED"
