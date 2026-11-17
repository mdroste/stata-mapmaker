program define _mapmaker_normalize
    version 16
    syntax varname, GENerate(name) WIDTH(integer) KIND(string)
    capture confirm numeric variable `varlist'
    if !_rc {
        local storage : type `varlist'
        if "`kind'" == "string" | (`width' > 7 & "`storage'" == "float") {
            di as err "Use string IDs for this pack (long float IDs may already be rounded)."
            exit 459
        }
        quietly count if missing(`varlist') | `varlist' < 0 | `varlist' != floor(`varlist')
        if r(N) error 459
        quietly gen str244 `generate' = strtrim(string(`varlist', "%21.0f"))
    }
    else {
        quietly count if strlen(strtrim(`varlist')) > 244
        if r(N) error 459
        quietly gen str244 `generate' = strtrim(`varlist')
    }
    if "`kind'" == "digits" quietly count if !regexm(`generate', "^[0-9]+$")
    else quietly count if `generate' == ""
    if r(N) {
        di as err "Invalid or missing geographic IDs."
        exit 459
    }
    if `width' {
        quietly count if strlen(`generate') > `width'
        if r(N) error 459
        quietly replace `generate' = substr("00000000000000000000",1,`width'-strlen(`generate')) + `generate'
    }
    else if "`kind'" == "digits" quietly replace `generate' = strtrim(string(real(`generate'), "%21.0f"))
end
