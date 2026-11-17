* Run after adding the extracted Mapmaker bundle to adopath.
* Writes to your current directory and restores the data you have loaded.
version 16
preserve
clear
input str5 county_fips double example_value
"06001" 15
"06013" 30
"06041" 45
"06075" 60
"06081" 75
end
capture noisily mapmaker example_value, geography(county) id(county_fips) ///
    nquantiles(3) zoomtoregion title("California counties: example") ///
    legendtitle("Synthetic value") note("Synthetic data; legacy boundaries") ///
    saving("mapmaker-example.pdf") nodisplay
local rc = _rc
restore
if `rc' exit `rc'
display "Example saved as mapmaker-example.pdf in your current directory."
