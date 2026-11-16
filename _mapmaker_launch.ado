program define _mapmaker_launch
    version 16
    syntax, ROOT(string) REQUEST(string) [ENGINE(string) PYTHON(string)]
    if `"`engine'"' != "" & `"`python'"' != "" {
        di as err "Specify engine() or python(), once."
        exit 198
    }
    if `"`engine'"' == "" & `"`python'"' == "" {
        local engine `"`root'/runtime/mapmaker-render/mapmaker-render"'
        if "`c(os)'" == "Windows" local engine `"`engine'.exe"'
    }
    if `"`python'"' != "" {
        confirm file `"`python'"'
        local script `"`root'/python/mapmaker_cli.py"'
    }
    else {
        capture confirm file `"`engine'"'
        if _rc {
            di as err "Bundled renderer is not installed."
            di as err "Build it with tools/build_bundle.py, or explicitly select python() for development."
            exit 601
        }
    }
    mata: _mm_command()
    shell `command'
end
