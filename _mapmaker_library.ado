program define _mapmaker_library, rclass
    version 16
    gettoken category 0 : 0
    gettoken action 0 : 0, parse(" ,")
    if `"`action'"' == "" | `"`action'"' == "," {
        if `"`action'"' == "," local 0 `", `0'"'
        local action browse
    }
    syntax [anything(name=target)], [COUNtry(string) LEVEL(string) VINTage(string) ///
        INSTalled ALL SEARCH(string) REVision(string) DATADIR(string) ///
        ENGINE(string) PYTHON(string) USING(string) NAME(string) IDField(string) CRS(string) ///
        STATE(string) PROVIDER(string) DECADE(string) LIMIT(integer 50) OFFSET(integer 0) ///
        SAVING(string) FRAME(name) REPLACE ID(varname) PROJection(string) ///
        GEOgraphy(string) PURPOSE(string) CHOICES(string) CENTER(string) REGION(string) ///
        LAYOUT(string) INSETS(string) GRIDS(string) GRATICULE DISTORTION ///
        SOURCE(string) TARGETPACK(string) UNIVERSE(string) METHOD(string) ///
        VALUE(varname numeric) NUMERATOR(varname numeric) DENOMINATOR(varname numeric) AUDIT(string)]
    if "`frame'" != "" & !inlist("`action'", "ids", "attributes", "membership", "diagnose", "apply") {
        di as err "frame() is available for ids, attributes, membership, and diagnose"
        exit 198
    }
    if "`frame'" != "" {
        capture frame `frame': count
        if !_rc {
            di as err "Frame `frame' already exists; choose a new frame name"
            exit 110
        }
    }
    tempfile diagnostic_table diagnostic_data
    if "`category'" == "crosswalk" & "`action'" == "apply" {
        if "`id'" == "" | ("`value'" == "" & "`numerator'" == "") error 198
        if "`value'" != "" & "`numerator'`denominator'" != "" error 198
        if "`numerator'" != "" & "`denominator'" == "" error 198
        if "`saving'`frame'" == "" error 198
        if "`value'" != "" local numerator `value'
        if `"`saving'"' == "" local saving `"`diagnostic_table'"'
        tempname cf
        tempvar cw_id cw_n cw_d
        frame put `id' `numerator' `denominator', into(`cf')
        frame `cf': clonevar `cw_id' = `id'
        frame `cf': gen double `cw_n' = `numerator'
        if "`denominator'" != "" frame `cf': gen double `cw_d' = `denominator'
        else frame `cf': gen double `cw_d' = .
        frame `cf': keep `cw_id' `cw_n' `cw_d'
        frame `cf': rename (`cw_id' `cw_n' `cw_d') (mm_id numerator denominator)
        frame `cf': export delimited using `"`diagnostic_data'"', replace
        frame drop `cf'
        local data `"`diagnostic_data'"'
    }
    if "`action'" == "diagnose" {
        if "`id'" == "" {
            di as err "diagnose requires id(variable) and saving(filename.csv) or frame(name)"
            exit 198
        }
        if `"`saving'"' == "" & "`frame'" != "" local saving `"`diagnostic_table'"'
        tempname diagnostic_frame
        frame put `id', into(`diagnostic_frame')
        if "`id'" != "mm_id" frame `diagnostic_frame': rename `id' mm_id
        frame `diagnostic_frame': export delimited mm_id using `"`diagnostic_data'"', replace
        frame drop `diagnostic_frame'
        local data `"`diagnostic_data'"'
    }
    quietly findfile mapmaker.ado
    local adofile `"`r(fn)'"'
    mata: st_local("root", substr(st_local("adofile"), 1, strlen(st_local("adofile"))-12))
    tempfile request response status report resolved
    if "`revision'" == "" local revision 1
    mata: _mm_library_request()
    _mapmaker_launch, root(`"`root'"') request(`"`request'"') engine(`"`engine'"') python(`"`python'"')
    capture confirm file `status'
    if _rc {
        di as err "Mapmaker did not return a status. Run mapmaker doctor."
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
    if "`category'" == "geography" & inlist("`action'", "resolve", "ids", "attributes", "membership", "diagnose", "verify") {
        file open `result' using `resolved', read text
        foreach name in path geography vintage width id_kind pack_id revision {
            file read `result' value
            if "`name'" == "path" local table `"`value'"'
            return local `name' `"`value'"'
        }
        file close `result'
        if "`frame'" != "" {
            frame create `frame'
            capture frame `frame': import delimited using `"`table'"', varnames(1) stringcols(_all) clear
            if _rc {
                local import_rc = _rc
                frame drop `frame'
                exit `import_rc'
            }
            return local frame "`frame'"
            di as text "Geography table loaded into frame `frame'."
        }
    }
    else {
        file open `result' using `report', read text
        file read `result' line
        while r(eof) == 0 {
            di as text `"`line'"'
            file read `result' line
        }
        file close `result'
        if "`category'" == "crosswalk" & "`action'" == "apply" & "`frame'" != "" {
            frame create `frame'
            frame `frame': import delimited using `"`saving'"', varnames(1) stringcols(1) asdouble encoding("utf-8") clear
            return local frame `frame'
        }
    }
end
