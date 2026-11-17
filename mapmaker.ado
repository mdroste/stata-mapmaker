*! mapmaker 2.0.0a1 16nov2026
program define mapmaker, rclass
    version 16
    quietly findfile mapmaker_mata.mata
    quietly do `"`r(fn)'"'
    quietly findfile mapmaker_figure.mata
    quietly do `"`r(fn)'"'
    gettoken subcommand remainder : 0, parse(" ,")
    gettoken subaction : remainder, parse(" ,")
    if inlist("`subcommand'", "geography", "projection", "style", "scale", "reproduce", "crosswalk") & ///
        (`"`remainder'"' == "" | inlist("`subaction'", "browse", "search", "describe", "install", "remove", "defaults", "import", "refresh") | ///
         inlist("`subaction'", ",", "ids", "attributes", "membership", "preview", "diagnose", "verify") | ///
         inlist("`subaction'", "recommend", "preflight", "compare", "grids", "cache") | ///
         inlist("`subaction'", "export", "restore", "repair", "updates", "inventory", "apply")) {
        _mapmaker_library `0'
        return add
        exit
    }
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
        di as text "Run mapmaker geography browse, installed for bundled and user-installed packs."
        exit
    }
    preserve
    capture noisily _mapmaker_run `0'
    local rc = _rc
    if !`rc' return add
    restore
    exit `rc'
end
