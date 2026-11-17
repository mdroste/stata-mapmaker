* Run from a complete Mapmaker installation. No Python setup is required.
* The install command downloads the small optional world geography once.
version 16
set more off
mapmaker geography install world_ne_country_110m
mapmaker projection recommend, geography(world_ne_country_110m) purpose(thematic)
mapmaker projection compare, geography(world_ne_country_110m) ///
    choices(equalearth robinson winkeltripel) graticule distortion ///
    saving("projection-options.pdf") replace
mapmaker geography preview world_ne_country_110m, ///
    projection(equalearth-pacific) graticule saving("pacific.pdf") replace
mapmaker geography preview world_ne_country_110m, ///
    projection(orthographic) center(-96 40) graticule saving("globe.png") replace
mapmaker geography preview world_ne_country_110m, ///
    projection(interrupted-goode) graticule saving("interrupted.pdf") replace
mapmaker geography preview world_ne_country_110m, ///
    projection(arctic-equalarea) region(-180 55 180 90) ///
    graticule saving("arctic.pdf") replace
mapmaker projection preflight equalearth, crs(EPSG:27700) region(-6 50 2 58)
mapmaker projection cache
