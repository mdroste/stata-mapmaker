{smcl}
{* *! version 0.10  10jul2019}{...}
{vieweralsosee "mapmaker" "help mapmaker"}{...}
{viewerjumpto "Syntax" "mapmaker##syntax"}{...}
{viewerjumpto "Description" "mapmaker##description"}{...}
{viewerjumpto "Options" "mapmaker##options"}{...}
{viewerjumpto "Examples" "mapmaker##examples"}{...}
{title:Title}

{pstd}
{hi:mapmaker} {hline 2} Publication-quality choropleth maps in Stata, rendered with D3JS


{marker syntax}{title:Syntax}

{p 8 15 2}
{cmd:mapmaker}
{varname} {ifin}{cmd:,}
 {cmdab:geo:graphy(}{it:{help mapmaker##usegeo:geoname}}{cmd:)} [{it:options}]


{synoptset 35 tabbed}{...}
{synopthdr :options}
{synoptline}
{syntab :Main}
{synopt :{cmdab:geo:graphy(template)}}geographic template to map (state, county, cz, or zip) {p_end}
{synopt :{cmdab:geov:ar(variable)}}geographic identifier variable corresponding to template {p_end}
{synopt :{opt zoom:toregion}}zoom in map on nonmissing obs. (after applying if/in conditions){p_end}

{syntab :Bins}
{synopt :{opt nq:uantiles(#)}}number of bins, defined as quantiles; default is {bf:10}{p_end}
{synopt :{opth cutv:alues(numlist)}}use values of {it:numlist} to determine number of bins and bin sizes{p_end}

{syntab :Map Style}
{synopt :{opt colorscheme(string)}}color scheme (color brewer scheme), see usage notes below{p_end}
{synopt :{opt revcolors}}reverse color order{p_end}

{syntab :Legend}
{synopt :{opt nolegend}}do not display a legend{p_end}
{synopt :{opt legmissing(string)}}label for missing data{p_end}
{synopt :{opt legendwidth(#)}}legend width in pixels{p_end}
{synopt :{opt legendheight(#)}}legend height in pixels{p_end}
{synopt :{opt legdecimals(#)}}number of decimals to display (default 2){p_end}
{synopt :{cmdab:formatstr(string)}}numerical format to display in legend{p_end}

{syntab :Output}
{synopt :{opt savegraph(filename)}}save map to file; format automatically detected from file extension.{p_end}
{synopt :{opt nodisplay}}do not display map{p_end}
{synoptline}


{marker description}{...}
{title:Description}

{pstd}
{cmd:mapmaker} generates publication-quality choropleth maps using a combination of Stata, Python, D3JS, and PhantomScript.

{pstd}
{cmd:mapmaker} includes geographic templates for several geographies of interest in the United States: states, commuting zones, counties, five-digit ZIP codes (poorly), and census tracts.

{pstd}
{cmd:mapmaker} requires Python 3.x and Stata 16.


{marker options}{...}
{title:Options}

{dlgtab:Main}

{phang}{opt geo:graphy(geoname)} specifies the name of the geography template that maptile will use to create the map. Valid options are state, cz, county, and zip. 

{phang}{opt geov:ar(var)} specifies the name of the geographic identifier variable in your dataset. By default, this is assumed to be the same as the geography template.


{dlgtab:Bins}

{phang}{opt nq:uantiles(#)} specifies the number of equal-sized color bins to be created (default: 10). Valid options are 2-10. The bins created match the results of {bf:{help xtile}}.
This option cannot be combined with {opt cutvalues()}.

{pmore}
It is possible that fewer bins are created than specified; for example, if the variable being mapped takes fewer unique values than the number of bins requested.
For more information, see the technical note on non-unique quantiles in the {manlink D pctile} manual.

{phang}{opth cutv:alues(numlist)} specifies a list of values that are used to define the boundaries for the color bins. The list must be in ascending order with no repeated values, for instance: cutvalues(0.01 0.05 0.1 0.2). This option cannot be combined with {opt nquantiles()}.

{dlgtab:Map Style}

{phang}{opt colorscheme} chooses a scheme (using the ColorBrewer javascript library) for coloring the bins. The default color scheme is "RdYlGn", ranging from dark red for the lowest values to dark green for the highest values.

	Here are some valid color schemes supporting 10 bins (case sensitive):
	
		colorscheme("RdYlGn")  - red to yellow to green (default)
		colorscheme("YlGn")    - yellow to green
		colorscheme("YlOrRd") - yellow to orange to red
		colorscheme("YlOrBr")  - yellow to orange to brown
		colorscheme("Purples") - shades of purple
		colorscheme("Blues")   - shades of blue
		colorscheme("Greens")  - shades of green
		colorscheme("Oranges") - shades of orange
		colorscheme("Reds")    - shades of red
		colorscheme("Greys")   - shades of grey
		
	When the number of bins is 9 or fewer, any ColorBrewer scheme (google for more) will work. Only the above schemes will support 10 bins.
		
{phang}{opt rev:colors} inverts the color scale.


{dlgtab:Legend}

{phang}{opt legd:ecimals(#)} specifies the number of decimals to display in legend entries. Two decimals are shown by default.
This option cannot be combined with {opt legformat()}.

{phang}{cmdab:legf:ormat(}{it:{help format:%fmt}}{cmd:)} specifies a numerical format for the numbers in the legend. By default, the format varies automatically with the magnitude of the data.
This option cannot be combined with {opt legdecimals()}.

{phang}{opt legendw:idth(#)} specifies the legend width in pixels.

{phang}{opt legendh:eight(#)} specifies the legend height in pixels.


{dlgtab:Output}

{phang}{opt savegraph(filename)} saves the map to a file.
The format is automatically detected from the extension specified [ex: {bf:.png .eps}],
and either {cmd:graph save} or {cmd:graph export} is run.
If no file extension is specified, the PNG format ({bf:.png}) is assumed.
If no directory is specified, the current working directory is assumed.
If savegraph() is not specified at all, mapmaker writes to temp.png in the current working directory.

{pmore}
It is usually preferable to save maps in a bitmap format ({bf:.png} or {bf:.tiff}).
Many maps have an enormous file size when saved in a vector image format ({bf:.ps .eps .wmf .emf .pdf}).
This happens because maps can have very detailed information on the shapes of complicated borders and no details are lost when saving in a vector format.

{dlgtab:Advanced}

{phang}{opt zoom} shows only the subset of areas selected by the if {it:condition} on the map.

{pmore}
An {bf:if} or {bf:in} statement selects what data is {it:used}. Observations excluded are treated as if the data is missing. They will therefore show up in grey on the map, and will not be included when computing quantiles.

{pmore}
{opt zoom} selects what areas are {it:shown}, without affecting what data is used. Note that quantiles (bins) are computed using all non-missing observations, whether or not they are shown on the map.
To additionally exclude the hidden areas from being used when calculating quantiles, it is necessary to repeat the {it:condition} using both {bf:if} and {opt mapif()}.


{marker examples}{...}
{title:Examples}

{marker example_binning}{...}
{pstd}{bf:CZ-level map examples}

{pstd}Load some CZ-level data.{p_end}
{phang2}. {stata use "$dropbox/ado/mapmaker2/trunk/sampledata/cz_sampledata.dta", clear}{p_end}

{pstd}Full US map{p_end}
{phang2}. {stata mapmaker poor_share, geo(cz)}{p_end}

{pstd}Zoom in to a few states{p_end}
{phang2}. {stata mapmaker poor_share if inlist(statename,"New York", "Pennsylvania", "New Jersey", "Connecticut"), geo(cz)}{p_end}

{marker example_binning}{...}
{pstd}{bf:County-level map examples}

{pstd}Load some county-level data.{p_end}
{phang2}. {stata import delimited "$dropbox/ado/mapmaker2/trunk/sampledata/countydata.csv", clear}{p_end}
{phang2}. {stata rename id county_id}{p_end}
{phang2}. {stata merge 1:1 county_id using "$dropbox/ado/mapmaker2/trunk/sampledata/county_1990.dta", nogen}{p_end}

{pstd}County-level map, full United States{p_end}
{phang2}. {stata mapmaker rate, geo(county) geovar(county_id)}{p_end}

{pstd}County-level map, Washington state{p_end}
{phang2}. {stata mapmaker rate if stateabbrv=="WA", geo(county) geovar(county_id) zoom}{p_end}






Coming soon.
