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
        capture confirm file `"`engine'"'
        if _rc {
            local candidate `"`root'/.venv/bin/python"'
            if "`c(os)'" == "Windows" local candidate `"`root'/.venv/Scripts/python.exe"'
            capture confirm file `"`candidate'"'
            if !_rc {
                local python `"`candidate'"'
                local engine ""
            }
        }
    }
    if `"`python'"' != "" {
        confirm file `"`python'"'
        local script `"`root'/python/mapmaker_cli.py"'
    }
    else {
        capture confirm file `"`engine'"'
        if _rc {
            di as err "Mapmaker's packaged runtime was not found."
            di as err "Extract the full bundle for your operating system, then add its folder to adopath."
            di as err "Keep runtime/, assets/, and catalog/ alongside mapmaker.ado. See readme.md."
            exit 601
        }
    }
    mata: _mm_command()
    shell `command'
end
