* Run from a writable project directory after adding the extracted bundle to adopath.
* Synthetic data; original dataset restored even when an export fails.
version 16
preserve
capture program drop _mm_research_example
program define _mm_research_example
    clear
    set obs 6
    gen str2 state = word("06 48 36 12 17 53",_n)
    gen str2 abbrev = word("CA TX NY FL IL WA",_n)
    gen double effect = real(word("-2 1 3 -1 0 2",_n))
    gen double population = real(word("39 30 20 22 13 8",_n))
    expand 2
    bysort state: gen year = cond(_n==1,2010,2020)
    replace effect = effect+1 if year==2020
    gen byte uncertain = state=="17" | state=="53"
    mapmaker effect, geography(state) by(year) classification(diverging) midpoint(0) ///
        labels(abbrev) uncertain(uncertain) title("Synthetic effects across years") ///
        scalesave("example-scale.json") manifest("example-manifest.json") ///
        saving("example-panels.pdf") nodisplay
    mapmaker effect, geography(state) by(year) scaleuse("example-scale.json") ///
        layout(cartogram) size(population) cartobase(2010) labels(abbrev) ///
        title("Same scale; circle areas represent baseline population") ///
        saving("example-cartogram.pdf") nodisplay
    mapmaker effect, geography(state) by(year) scaleuse("example-scale.json") ///
        style(grayscale) layout(tile) labels(abbrev) saving("example-tiles.pdf") nodisplay
    mapmaker reproduce verify, using("example-manifest.json")
end
capture noisily _mm_research_example
local rc = _rc
restore
capture program drop _mm_research_example
if `rc' exit `rc'
display "Research examples saved: example-panels.pdf, example-cartogram.pdf, example-tiles.pdf"
