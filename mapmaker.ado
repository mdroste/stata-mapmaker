*! mapmaker 2.0.0a1 16nov2026
program define mapmaker, rclass
    version 16
    quietly findfile mapmaker_mata.mata
    quietly do `"`r(fn)'"'
    if strtrim(`"`0'"') == "doctor" {
        quietly findfile mapmaker.ado
        local adofile `"`r(fn)'"'
        mata: st_local("root", substr(st_local("adofile"), 1, strlen(st_local("adofile"))-12))
        di as text "Mapmaker 2.0.0a1: `c(os)' / `c(machine_type)'"
        di as text `"Command: `adofile'"'
        local executable `"`root'/runtime/mapmaker-render/mapmaker-render"'
        if "`c(os)'" == "Windows" local executable `"`executable'.exe"'
        capture confirm file `"`executable'"'
        if _rc di as text "Bundled renderer: not installed (development checkout)."
        else di as text `"Bundled renderer: `executable'"'
        foreach geo in county state cz tract {
            capture confirm file `"`root'/assets/`geo'-legacy/manifest.json"'
            if !_rc di as text "Pack: `geo'-legacy"
        }
        di as text "This reports installation paths. examples/smoke.do performs an export test."
        exit
    }
    preserve
    capture noisily _mapmaker_run `0'
    local rc = _rc
    if !`rc' return add
    restore
    exit `rc'
end
