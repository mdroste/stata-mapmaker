program define _mapmaker_legacy_run, rclass
    version 16
    syntax varname(numeric) [if] [in], GEOgraphy(string) ///
        [GEOVar(varname) ID(varname) VINTage(string) REVision(string) DATADIR(string) ///
        PROJection(string) LAYOUT(string) CENTER(string) REGION(string) ///
        INSETS(string) GRIDS(string) GRATICULE DISTORTION ///
        SAVEGraph(string) SAVing(string) REPLACE ///
        NQuantiles(integer 0) CUTValues(numlist ascending) ///
        COLORSCheme(string) COLORS(string) REVColors INVERTColors ///
        ZOOMtoregion CONTEXT NOLEGend NODISPlay ///
        TITLE(string) NOTE(string) LEGENDTitle(string) LABELMissing(string) ///
        LEGDecimals(integer -1) FORMATstr(string) LEGPERcent ///
        XSIZE(real 10) YSIZE(real 6) DPI(integer 300) ///
        NOBORDers NOSTATES MESHStates HATCHMissing RASTERize ///
        UNMATCHED(string) ENGINE(string) PYTHON(string)]

    if inlist(lower("`geography'"), "county", "state", "cz", "tract") local geography = lower("`geography'")
    if "`projection'" == "" local projection auto
    if "`layout'" == "" local layout auto
    if "`geovar'" != "" & "`id'" != "" {
        di as err "Specify geovar() or id(), once."
        exit 198
    }
    if "`id'" != "" local geovar `id'
    if "`geovar'" == "" {
        if !inlist("`geography'", "county", "state", "cz", "tract") {
            di as err "Specify id(varname) when selecting a named geography pack."
            exit 198
        }
        local geovar `geography'
    }
    confirm variable `geovar'
    if "`geovar'" == "`varlist'" {
        di as err "The geographic ID and mapped value must be different variables."
        exit 198
    }
    if `"`saving'"' != "" & `"`savegraph'"' != "" {
        di as err "Specify saving() or savegraph(), once."
        exit 198
    }
    if `"`saving'"' != "" local savegraph `"`saving'"'
    if `"`savegraph'"' == "" local savegraph "mapmaker.pdf"
    local output `"`savegraph'"'
    if !regexm(`"`output'"', "^(/|[A-Za-z]:|\\)") local output `"`c(pwd)'/`output'"'
    if "`replace'" == "" confirm new file `"`output'"'
    if "`unmatched'" == "" local unmatched error
    if !inlist("`unmatched'", "error", "drop") {
        di as err "unmatched() must be error or drop"
        exit 198
    }
    if `nquantiles' != 0 & `"`cutvalues'"' != "" {
        di as err "Choose nquantiles() or cutvalues()."
        exit 198
    }
    if `nquantiles' == 0 local nquantiles 5
    if `nquantiles' < 2 | `nquantiles' > 32 {
        di as err "nquantiles() must be between 2 and 32"
        exit 198
    }
    if `legdecimals' < -1 | `legdecimals' > 10 {
        di as err "legdecimals() must be between 0 and 10"
        exit 198
    }
    if `"`formatstr'"' != "" & (`legdecimals' != -1 | "`legpercent'" != "") {
        di as err "formatstr() cannot be combined with legdecimals() or legpercent"
        exit 198
    }
    if `"`formatstr'"' == "" {
        if `legdecimals' == -1 local formatstr "%9.3g"
        else local formatstr "%20.`legdecimals'f"
    }
    capture local fmtcheck : display `formatstr' 1
    if _rc {
        di as err "formatstr() must be a Stata numeric display format"
        exit 198
    }
    if "`colorscheme'" == "" local colorscheme viridis
    if `"`labelmissing'"' == "" local labelmissing "No data"
    quietly findfile mapmaker.ado
    local adofile `"`r(fn)'"'
    mata: st_local("root", substr(st_local("adofile"), 1, strlen(st_local("adofile"))-12))
    quietly _mapmaker_library geography resolve `geography', vintage(`"`vintage'"') ///
        revision(`"`revision'"') datadir(`"`datadir'"') engine(`"`engine'"') python(`"`python'"')
    local pack `"`r(path)'"'
    local geography "`r(geography)'"
    local vintage "`r(vintage)'"
    local width "`r(width)'"
    local id_kind "`r(id_kind)'"
    local pack_id "`r(pack_id)'"
    local pack_revision "`r(revision)'"
    marksample touse, novarlist
    quietly keep if `touse'
    if _N == 0 error 2000
    tempvar normalized value
    capture confirm numeric variable `geovar'
    if !_rc {
        if "`id_kind'" == "string" {
            di as err "This pack uses string IDs; supply a string id() variable."
            exit 459
        }
        local storage : type `geovar'
        if `width' > 7 & "`storage'" == "float" {
            di as err "Long geographic IDs stored as float may be rounded; reimport them as strings or doubles."
            exit 459
        }
        quietly count if missing(`geovar') | `geovar' < 0 | `geovar' != floor(`geovar')
        if r(N) {
            di as err "Geographic IDs must be nonmissing, nonnegative integers."
            exit 459
        }
        quietly gen str244 `normalized' = strtrim(string(`geovar', "%21.0f"))
    }
    else {
        quietly gen str244 `normalized' = strtrim(`geovar')
        quietly count if strlen(strtrim(`geovar')) > 244
        if r(N) {
            di as err "Geographic IDs are too long."
            exit 459
        }
    }
    if "`id_kind'" == "digits" quietly count if !regexm(`normalized', "^[0-9]+$")
    else quietly count if `normalized' == ""
    if r(N) {
        di as err "Geographic IDs must contain digits and cannot be missing."
        exit 459
    }
    if `width' {
        quietly count if strlen(`normalized') > `width'
        if r(N) {
            di as err "Geographic IDs exceed the expected `width' digits."
            exit 459
        }
        quietly replace `normalized' = substr("00000000000", 1, `width' - strlen(`normalized')) + `normalized'
    }
    else if "`id_kind'" == "digits" quietly replace `normalized' = strtrim(string(real(`normalized'), "%21.0f"))
    capture isid `normalized'
    if _rc {
        di as err "Duplicate geographic IDs after normalization; aggregate to one row per region."
        exit 459
    }
    quietly gen double `value' = `varlist'
    quietly keep `normalized' `value'
    rename `normalized' mm_id
    rename `value' mm_value
    tempfile selected data request response status
    quietly save `selected'
    quietly import delimited using `"`pack'/ids.csv"', varnames(1) stringcols(_all) encoding("utf-8") clear
    quietly merge 1:1 mm_id using `selected', keep(2 3)
    quietly count if _merge == 2
    local N_unmatched = r(N)
    if `N_unmatched' & "`unmatched'" == "error" {
        di as err "`N_unmatched' selected geographic IDs are absent from this pack."
        quietly keep if _merge == 2
        list mm_id in 1/`=min(_N, 5)', noobs clean
        exit 459
    }
    quietly keep if _merge == 3
    local N_matched = _N
    quietly count if missing(mm_value)
    local N_missing = r(N)
    if `N_matched' == `N_missing' error 2000
    local cuts `cutvalues'
    if `"`cutvalues'"' == "" {
        quietly summarize mm_value, meanonly
        if r(min) == r(max) {
            local constant = r(min)
            local nbins 1
            quietly gen byte mm_bin = 1 if !missing(mm_value)
            di as text "The selected values are constant; using one color."
        }
        else {
            quietly xtile mm_bin = mm_value, nq(`nquantiles')
            quietly _pctile mm_value, nq(`nquantiles')
            local nbins `nquantiles'
            forvalues j=1/`=`nbins'-1' {
                local point : display %24.17g r(r`j')
                local cuts `cuts' `point'
            }
        }
    }
    else {
        local last .
        local nbins 1
        quietly gen byte mm_bin = 1 if !missing(mm_value)
        foreach point of numlist `cutvalues' {
            if `last' < . & `point' <= `last' {
                di as err "cutvalues() must be strictly increasing"
                exit 198
            }
            quietly replace mm_bin = mm_bin + (mm_value > `point') if !missing(mm_value)
            local last `point'
            local ++nbins
        }
    }
    if `nbins' > 32 {
        di as err "At most 32 bins are supported"
        exit 198
    }
    tempname cutmatrix counts
    matrix `counts' = J(1, `nbins', 0)
    local nc : word count `cuts'
    if `nc' {
        matrix `cutmatrix' = J(1, `nc', .)
        forvalues j=1/`nc' {
            local point : word `j' of `cuts'
            matrix `cutmatrix'[1, `j'] = `point'
            local shown = `point' * cond("`legpercent'" != "", 100, 1)
            local boundary`j' = strtrim(string(`shown', "`formatstr'"))
            if "`legpercent'" != "" local boundary`j' "`boundary`j''%"
            if `j' > 1 {
                local k = `j'-1
                local previous : word `k' of `cuts'
                if `point' != `previous' & "`boundary`j''" == "`boundary`k''" {
                    di as err "Legend rounding hides distinct cutoffs; increase legdecimals() or use formatstr()."
                    exit 198
                }
            }
        }
    }
    forvalues j=1/`nbins' {
        quietly count if mm_bin == `j'
        matrix `counts'[1, `j'] = r(N)
        if r(N) == 0 di as text "Bin `j' is empty (ties or supplied cutoffs)."
        local k = `j'-1
        if `nbins' == 1 {
            local shown = `constant' * cond("`legpercent'" != "", 100, 1)
            local label`j' = strtrim(string(`shown', "`formatstr'"))
            if "`legpercent'" != "" local label`j' "`label`j''%"
        }
        else if `j' == 1 local label`j' "≤ `boundary1'"
        else if `j' == `nbins' local label`j' "> `boundary`nc''"
        else local label`j' "(`boundary`k'', `boundary`j'']"
    }
    quietly keep mm_id mm_bin
    quietly export delimited using `data', replace
    local reverse = ("`revcolors'`invertcolors'" != "")
    tempfile report
    mata: _mm_request()
    _mapmaker_launch, root(`"`root'"') request(`"`request'"') engine(`"`engine'"') python(`"`python'"')
    capture confirm file `status'
    if _rc {
        di as err "Renderer did not return a status. Run mapmaker doctor to check the runtime."
        exit 603
    }
    tempname result
    file open `result' using `status', read text
    file read `result' first
    file read `result' message
    file close `result'
    if "`first'" != "MAPMAKER_OK_V1" {
        di as err `"`message'"'
        exit 459
    }
    confirm file `"`output'"'
    capture confirm file `"`report'"'
    if !_rc {
        file open `result' using `"`report'"', read text
        file read `result' line
        while r(eof) == 0 {
            di as text `"`line'"'
            file read `result' line
        }
        file close `result'
    }
    di as text "Mapmaker: `N_matched' matched regions; `N_missing' missing values; `N_unmatched' unmatched."
    di as text "Boundaries: `pack_id', revision `pack_revision', vintage `vintage'."
    if "`vintage'" == "legacy" di as text "Legacy boundary source vintage is unverified."
    di as text `"Saved `output'"'
    if "`nodisplay'" == "" capture view browse `"`output'"'
    return scalar N = `N_matched'
    return scalar N_missing = `N_missing'
    return scalar N_unmatched = `N_unmatched'
    return scalar bins = `nbins'
    return matrix counts = `counts'
    if `nc' return matrix cutoffs = `cutmatrix'
    return local output `"`output'"'
    return local geography "`geography'"
    return local pack "`pack_id'"
    return local pack_revision "`pack_revision'"
    return local vintage "`vintage'"
    return local projection "`projection'"
    return local version "2.0.0a1"
end

