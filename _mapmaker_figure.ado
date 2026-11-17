program define _mapmaker_figure, rclass
    version 16
    syntax varname [if] [in] [aw fw pw], GEOgraphy(string) [ID(varname) GEOVar(varname) ///
        VINTage(string) REVision(string) DATADIR(string) BY(varname) SCALE(string) ///
        COLUMNS(integer 0) BASELINE(string) PANELORDER(string) CLASSification(string) ///
        NQuantiles(integer 5) CUTValues(numlist ascending) MIDPOINT(real 0) LIMITS(numlist min=2 max=2) ///
        CATEGORIES(string) BIVARIATE(varname numeric) NQUANTILES2(integer 3) CUTVALUES2(numlist ascending) ///
        SCALEUSE(string) SCALESAVE(string) STYLE(string) STYLESAVE(string) MANIFEST(string) ///
        SIZE(varname numeric) MAPTYPE(string) SYMBOLMAX(real 500) POINTS(string) POINTCRS(string) ///
        FLOWS(string) FLOWTOP(integer 50) FLOWMIN(real 0) LABELS(varname) LABELDX(varname numeric) LABELDY(varname numeric) ///
        LABELLIMIT(integer 50) HIGHLIGHT(varname numeric) OUTLINE(string) ALLOWVINTAGEMISMATCH ///
        UNCERTAIN(varname numeric) CILOWER(varname numeric) CIUPPER(varname numeric) REFERENCE(real 0) ///
        PROJection(string) LAYOUT(string) CENTER(string) REGION(string) INSETS(string) GRIDS(string) ///
        GRATICULE DISTORTION SCALEBAR NORTHARROW TILES(string) CARTOBASE(string) ITERATIONS(integer 500) ///
        SAVEGraph(string) SAVing(string) REPLACE COLORSCheme(string) COLORS(string) REVColors INVERTColors ///
        ZOOMtoregion CONTEXT NOLEGend NODISPlay TITLE(string) NOTE(string) LEGENDTitle(string) ///
        LABELMissing(string) UNITS(string) XLEGEND(string) YLEGEND(string) LEGENDPOSITION(string) ///
        XSIZE(real 0) YSIZE(real 0) DPI(integer 0) NOBORDers NOSTATES MESHStates HATCHMissing RASTERize ///
        UNMATCHED(string) RESULTS(name) ENGINE(string) PYTHON(string)]
    if "`id'" != "" & "`geovar'" != "" error 198
    if "`id'" == "" local id `geovar'
    if "`id'" == "" local id `geography'
    confirm variable `id'
    if "`id'" == "`varlist'" error 198
    if "`saving'" != "" & "`savegraph'" != "" error 198
    if "`saving'" != "" local savegraph `"`saving'"'
    if "`savegraph'" == "" local savegraph mapmaker.pdf
    local output `"`savegraph'"'
    if "`replace'" == "" confirm new file `"`output'"'
    if "`results'" != "" {
        capture frame `results': count
        if !_rc error 110
    }
    local resultframe `results'
    tempfile scaletable
    if "`scaleuse'" != "" {
        quietly _mapmaker_library scale resolve, using(`"`scaleuse'"') saving(`"`scaletable'"') engine(`"`engine'"') python(`"`python'"')
        tempname sf
        frame create `sf'
        frame `sf': import delimited using `scaletable', varnames(1) stringcols(_all) encoding("utf-8") clear
        frame `sf': mata: _mm_read_scales()
        frame drop `sf'
        local saved saved
        if "`classification'" == "bivariate" & "`bivariate'" == "" error 198
    }
    if "`scale'" == "" local scale shared
    if !inlist("`scale'", "shared", "panel") error 198
    if "`baseline'" != "" & "`scale'" == "panel" {
        di as err "baseline() requires scale(shared)."
        exit 198
    }
    if "`classification'" == "" local classification quantile
    if "`cutvalues'" != "" & "`classification'" == "quantile" local classification custom
    if "`bivariate'" != "" local classification bivariate
    if !inlist("`classification'", "quantile", "custom", "diverging", "continuous", "categorical", "bivariate") error 198
    if "`classification'" == "bivariate" & "`bivariate'" == "" error 198
    if "`classification'" == "bivariate" & `nquantiles' == 5 local nquantiles 3
    if `nquantiles' < 2 | `nquantiles' > 32 | `nquantiles2' < 2 | `nquantiles2' > 4 error 198
    if "`classification'" == "bivariate" & `nquantiles' > 4 error 198
    if "`classification'" != "categorical" confirm numeric variable `varlist'
    if "`classification'" == "custom" & "`cutvalues'`scaleuse'" == "" error 198
    if "`uncertain'" != "" & "`cilower'`ciupper'" != "" error 198
    if ("`cilower'" == "") != ("`ciupper'" == "") error 198
    if "`unmatched'" == "" local unmatched error
    if !inlist("`unmatched'", "error", "drop") error 198
    if "`projection'" == "" local projection auto
    if "`layout'" == "" local layout auto
    if "`maptype'" != "" & !inlist("`maptype'", "choropleth", "symbol") error 198
    if (inlist("`layout'", "cartogram", "dorling") | "`maptype'" == "symbol") & "`size'" == "" error 198
    local uncertainty = ("`uncertain'`cilower'" != "")
    foreach cutoption in cutvalues cutvalues2 {
        local previous .
        foreach point of local `cutoption' {
            if `previous' < . & `point' <= `previous' {
                di as err "User-supplied cutoffs must be strictly increasing."
                exit 198
            }
            local previous `point'
        }
    }
    marksample touse, novarlist
    quietly keep if `touse'
    if !_N error 2000
    foreach textvar in `varlist' `by' `labels' {
        capture confirm string variable `textvar'
        if !_rc {
            quietly count if strlen(`textvar')>244
            if r(N) {
                di as err "Panel keys, categories, and labels must fit within 244 UTF-8 bytes."
                exit 459
            }
        }
    }
    tempvar value value2 category display panel label w s u h dx dy
    if "`classification'" == "categorical" {
        capture confirm numeric variable `varlist'
        if !_rc {
            quietly gen str244 `category' = cond(missing(`varlist'),"",strtrim(string(`varlist',"%24.17g")))
            local vl : value label `varlist'
            if "`vl'" != "" quietly decode `varlist', gen(`display')
            else quietly gen str244 `display' = `category'
        }
        else {
            quietly gen str244 `category' = `varlist'
            quietly gen str244 `display' = `varlist'
        }
        quietly gen double `value' = .
    }
    else {
        quietly gen double `value' = `varlist'
        quietly gen str244 `category' = ""
        quietly gen str244 `display' = ""
    }
    quietly gen str244 `panel' = "Map"
    if "`by'" != "" {
        quietly count if missing(`by')
        if r(N) {
            di as err "Panel IDs cannot be missing."
            exit 459
        }
        capture confirm numeric variable `by'
        if !_rc {
            local panelnumeric 1
            quietly replace `panel' = strtrim(string(`by',"%24.17g"))
        }
        else quietly replace `panel' = `by'
    }
    quietly gen str244 `label' = ""
    if "`labels'" != "" {
        capture confirm string variable `labels'
        if !_rc quietly replace `label' = `labels'
        else quietly replace `label' = strtrim(string(`labels'))
    }
    quietly gen double `value2' = .
    if "`bivariate'" != "" quietly replace `value2' = `bivariate'
    quietly gen double `w' = 1
    if "`weight'" != "" {
        quietly replace `w' `exp'
        quietly count if missing(`w') | `w' <= 0 | ("`weight'" == "fweight" & `w' != floor(`w'))
        if r(N) {
            di as err "Classification weights must be positive and nonmissing (integer for fweights)."
            exit 459
        }
    }
    local weight_semantics "pooled observations, each row equally weighted"
    if "`weight'" != "" local weight_semantics "`weight': `exp'"
    foreach v in s u h dx dy {
        quietly gen double ``v'' = .
    }
    if "`size'" != "" quietly replace `s' = `size'
    if "`uncertain'" != "" quietly replace `u' = `uncertain'
    if "`highlight'" != "" quietly replace `h' = `highlight'
    if "`labeldx'" != "" quietly replace `dx' = `labeldx'
    if "`labeldy'" != "" quietly replace `dy' = `labeldy'
    if "`cilower'" != "" {
        quietly count if `cilower' > `ciupper' & !missing(`cilower', `ciupper')
        if r(N) error 459
        quietly replace `u' = (`cilower' <= `reference' & `ciupper' >= `reference') if !missing(`cilower', `ciupper')
    }
    quietly findfile mapmaker.ado
    local adofile `"`r(fn)'"'
    mata: st_local("root", substr(st_local("adofile"), 1, strlen(st_local("adofile"))-12))
    quietly _mapmaker_library geography resolve `geography', vintage(`"`vintage'"') revision(`"`revision'"') ///
        datadir(`"`datadir'"') engine(`"`engine'"') python(`"`python'"')
    local pack `"`r(path)'"'
    local geography `r(geography)'
    local vintage `r(vintage)'
    local pack_id `r(pack_id)'
    local pack_revision `r(revision)'
    tempvar normalized
    _mapmaker_normalize `id', gen(`normalized') width(`r(width)') kind(`r(id_kind)')
    quietly keep `normalized' `value' `value2' `category' `display' `panel' `label' `w' `s' `u' `h' `dx' `dy'
    rename (`normalized' `value' `value2' `category' `display' `panel' `label' `w' `s' `u' `h' `dx' `dy') ///
        (mm_id mm_value mm_value2 mm_category mm_display mm_panel mm_label mm_weight mm_size mm_uncertain mm_highlight mm_dx mm_dy)
    capture isid mm_id mm_panel
    if _rc {
        di as err "IDs must be unique within each panel; aggregate before mapping."
        exit 459
    }
    tempfile ids data request response status report results
    tempname idframe
    frame create `idframe'
    frame `idframe': import delimited using `"`pack'/ids.csv"', varnames(1) stringcols(_all) encoding("utf-8") clear
    frame `idframe': save `ids'
    frame drop `idframe'
    quietly merge m:1 mm_id using `ids', keep(1 3)
    quietly count if _merge == 1
    local N_unmatched = r(N)
    if `N_unmatched' & "`unmatched'" == "error" {
        di as err "`N_unmatched' selected IDs are absent from this pack; inspect geography diagnose."
        exit 459
    }
    mata: _mm_panel_init()
    quietly keep if _merge == 3
    if !_N error 2000
    local N_matched = _N
    quietly gen byte mm_bin = .
    quietly gen byte mm_bin2 = .
    tempvar ref apply
    quietly gen byte `ref' = 0
    quietly gen byte `apply' = 0
    local wt
    local emptyok
    if "`scale'" == "panel" local emptyok emptyok
    if "`weight'" != "" local wt weightvar(mm_weight) weighttype(`weight')
    forvalues i=1/`npanels' {
        mata: _mm_panel_select(`i', st_local("ref"), st_local("apply"))
        _mapmaker_classify, mode(`classification') ref(`ref') apply(`apply') bin(mm_bin) nq(`nquantiles') ///
            cuts(`"`cutvalues'"') midpoint(`midpoint') limits(`"`limits'"') categories(`"`categories'"') units(`"`units'"') ///
            `wt' `saved' `emptyok' panelkey(`"`panelkey'"')
        mata: _mm_axis_save()
        if "`bivariate'" != "" {
            _mapmaker_classify, mode(bivariate) ref(`ref') apply(`apply') bin(mm_bin2) nq(`nquantiles2') ///
                cuts(`"`cutvalues2'"') `wt' `saved' `emptyok' panelkey(`"`panelkey'"') axis(2) units(`"`units'"')
        }
        mata: _mm_panel_add(`i')
    }
    if "`bivariate'" != "" quietly replace mm_bin = . if missing(mm_bin2)
    quietly count if missing(mm_bin)
    local N_missing = r(N)
    quietly keep mm_id mm_panel mm_bin mm_bin2 mm_value mm_size mm_uncertain mm_highlight mm_label mm_dx mm_dy
    if "`classification'" != "continuous" drop mm_value
    quietly export delimited using `data', replace
    local reverse = ("`revcolors'`invertcolors'" != "")
    mata: _mm_figure_request()
    _mapmaker_launch, root(`"`root'"') request(`"`request'"') engine(`"`engine'"') python(`"`python'"')
    _mapmaker_status, status(`"`status'"') report(`"`report'"')
    tempname countframe counts
    if "`resultframe'" != "" local countframe `resultframe'
    frame create `countframe'
    frame `countframe': import delimited using `results', varnames(1) encoding("utf-8") clear
    frame `countframe': mkmat matched missing absent unmatched excluded visible, matrix(`counts')
    return matrix panel_counts = `counts'
    if "`resultframe'" != "" {
        return local frame `resultframe'
    }
    else frame drop `countframe'
    return scalar N = `N_matched'
    return scalar N_missing = `N_missing'
    return scalar N_unmatched = `N_unmatched'
    return scalar panels = `npanels'
    return local output `"`output'"'
    return local pack `pack_id'
    return local pack_revision `pack_revision'
    return local vintage `vintage'
    return local scale `scale'
    if "`nodisplay'" == "" capture view browse `"`output'"'
end
