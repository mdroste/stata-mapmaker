program define _mapmaker_run, rclass
    version 16
    local original `"`0'"'
    mata: _mm_route()
    * layout() alone can request a nongeographic figure, so parse that option safely.
    syntax varname [if] [in] [aw fw pw], GEOgraphy(string) [LAYOUT(string) *]
    if regexm(`"`optionnames'"', " (by|class|scale|columns|baseline|panelorder|midpoint|limits|categories|bivariate|size|labels|outline|highlight|style|manifest|points|flows|uncertain|cilower|ciupper|northarrow|scalebar|legendposition|results|tiles|cartobase|iterations|units|labellimit|xlegend|ylegend|maptype)[a-z]* ") | inlist("`layout'", "tile", "cartogram", "dorling") | `weighted' {
        _mapmaker_figure `original'
    }
    else _mapmaker_legacy_run `original'
    return add
end
