program define _mapmaker_classify
    version 16
    syntax, MODE(string) REF(varname) APPLY(varname) BIN(name) [NQ(integer 5) CUTS(string) ///
        MIDPOINT(real 0) LIMITS(string) CATEGORIES(string) UNITS(string) ///
        WEIGHTVAR(varname) WEIGHTTYPE(string) SAVED PANELKEY(string) AXIS(integer 1) EMPTYOK]
    local value mm_value
    if `axis' == 2 local value mm_value2
    local wt
    if "`weightvar'" != "" local wt [`weighttype'=`weightvar']
    local cuts2
    if "`saved'" != "" {
        mata: _mm_load_scale(st_local("panelkey"), strtoreal(st_local("axis")))
    }
    if "`mode'" == "categorical" {
        mata: _mm_categories(st_local("ref"), st_local("apply"), st_local("bin"), st_local("categories"), st_local("saved")!="")
        exit
    }
    quietly count if `ref' & !missing(`value')
    if r(N) == 0 & "`saved'" == "" {
        if "`emptyok'" != "" {
            local mode empty
            local nbins 1
            local cuts
            local limits
            local label1 "No reference data"
            mata: _mm_capture_scale()
            exit
        }
        di as err "No nonmissing reference values for this scale. Use shared scales or supply scaleuse()."
        exit 2000
    }
    if "`mode'" == "empty" {
        quietly count if `apply' & !missing(`value')
        if r(N) {
            di as err "An empty saved panel scale cannot classify new values."
            exit 459
        }
        mata: _mm_capture_scale()
        exit
    }
    if "`saved'" == "" {
        quietly summarize `value' if `ref', meanonly
        local vmin = r(min)
        local vmax = r(max)
        if "`mode'" == "continuous" {
            if "`limits'" == "" {
                if `vmin' == `vmax' {
                    local vmin = `vmin' - max(abs(`vmin')*.01, .5)
                    local vmax = `vmax' + max(abs(`vmax')*.01, .5)
                }
                local limits `vmin' `vmax'
            }
            local nbins 1
            local label1 Value
        }
        else {
            if "`cuts'" == "" {
                if "`mode'" == "diverging" {
                    local radius = max(abs(`vmin'-`midpoint'),abs(`vmax'-`midpoint'))
                    if `radius' == 0 local radius 1
                    forvalues j=1/`=`nq'-1' {
                        local point : display %24.17g (`midpoint'-`radius'+2*`radius'*`j'/`nq')
                        local cuts `cuts' `point'
                    }
                }
                else if `vmin' != `vmax' | "`mode'" == "bivariate" {
                    quietly _pctile `value' if `ref' `wt', nq(`nq')
                    forvalues j=1/`=`nq'-1' {
                        local point : display %24.17g r(r`j')
                        local cuts `cuts' `point'
                    }
                }
            }
            local nc : word count `cuts'
            local nbins = `nc'+1
            forvalues j=1/`nbins' {
                local k = `j'-1
                local a
                if `k' > 0 local a : word `k' of `cuts'
                local b : word `j' of `cuts'
                if `nbins' == 1 local label`j' "`vmin'"
                else if `j' == 1 local label`j' "<= `b'"
                else if `j' == `nbins' local label`j' "> `a'"
                else local label`j' "(`a', `b']"
            }
        }
    }
    quietly replace `bin' = 1 if `apply' & !missing(`value')
    if "`mode'" != "continuous" {
        foreach point of local cuts {
            quietly replace `bin' = `bin' + (`value' > `point') if `apply' & !missing(`value')
        }
    }
    mata: _mm_capture_scale()
end
