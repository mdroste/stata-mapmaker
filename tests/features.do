version 16
clear all
set more off
adopath ++ .
capture log close
log using tests/features.log, text replace
capture mkdir tests/output
capture mkdir tests/output/features
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
set obs 12
gen str2 state = string(mod(_n-1,6)+1,"%02.0f")
replace state = "08" if state == "03"
gen year = cond(_n<=6,2010,2020)
gen double value = _n-6
gen double population = _n*10
gen double other = 13-_n
gen byte flag = mod(_n,2)
gen str8 label = "State "+state
gen str8 category = cond(value<0,"Low",cond(value==0,"Zero","High"))
gen double lower = value-2
gen double upper = value+2
local common geography(state) by(year) replace nodisplay `runtime'
mapmaker value, `common' panelorder("2010|2020|2030") results(counts) ///
    scalesave("`out'/shared.scale.json") manifest("`out'/shared.manifest.json") saving("`out'/shared.png")
assert r(panels)==3
assert r(N)==12
frame counts: assert matched==0 & absent==6 if panel==2030
assert _N==12
mapmaker value, `common' scaleuse("`out'/shared.scale.json") saving("`out'/reused.pdf")
mapmaker value [aw=population], `common' baseline(2010) manifest("`out'/weighted.json") saving("`out'/weighted.svg")
mapmaker value, `common' scale(panel) saving("`out'/panel.png")
mapmaker value, `common' classification(diverging) midpoint(0) saving("`out'/diverging.png")
mapmaker value, `common' classification(continuous) limits(-3 3) units("Points") ///
    scalesave("`out'/continuous.scale.json") saving("`out'/continuous.png")
mapmaker value, `common' scaleuse("`out'/continuous.scale.json") saving("`out'/continuous-reused.pdf")
mapmaker category, `common' classification(categorical) categories("Low|Zero|High") ///
    scalesave("`out'/category.scale.json") saving("`out'/category.png")
mapmaker category, `common' classification(categorical) scaleuse("`out'/category.scale.json") saving("`out'/category-reused.svg")
mapmaker value, `common' bivariate(other) nquantiles(3) nquantiles2(2) ///
    scalesave("`out'/bivariate.scale.json") saving("`out'/bivariate.png")
mapmaker value, `common' bivariate(other) scaleuse("`out'/bivariate.scale.json") saving("`out'/bivariate-reused.pdf")
mapmaker value, `common' size(population) labels(label) highlight(flag) uncertain(flag) ///
    manifest("`out'/symbols.json") saving("`out'/symbols.png")
mapmaker value, `common' cilower(lower) ciupper(upper) reference(0) hatchmissing saving("`out'/intervals.png")
mapmaker value, `common' layout(tile) labels(state) saving("`out'/tile.png")
mapmaker value, `common' layout(cartogram) size(population) cartobase(2010) labels(state) ///
    manifest("`out'/cartogram.json") saving("`out'/cartogram.png")
mapmaker value, `common' style(grayscale) stylesave("`out'/style.json") saving("`out'/grayscale.png")
mapmaker value, `common' style("`out'/style.json") saving("`out'/styled.pdf")
mapmaker value, `common' style(presentation) saving("`out'/presentation.png")
mapmaker style browse, `runtime'
mapmaker reproduce verify, using("`out'/shared.manifest.json") `runtime'
mapmaker geography export state, saving("`out'/state.zip") replace `runtime'
mapmaker geography restore, using("`out'/state.zip") `runtime'
capture noisily mapmaker value, geography(state) scale(shared) `runtime'
assert _rc==459
assert _N==12
assert value==_n-6
display "FEATURES_OK"
log close
