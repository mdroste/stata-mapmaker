program define _mapmaker_status
    version 16
    syntax, STATUS(string) [REPORT(string)]
    confirm file `"`status'"'
    tempname f
    file open `f' using `"`status'"', read text
    file read `f' first
    file read `f' message
    file close `f'
    if "`first'" != "MAPMAKER_OK_V1" {
        di as err `"`message'"'
        exit 459
    }
    if "`report'" != "" {
        file open `f' using `"`report'"', read text
        file read `f' line
        while r(eof) == 0 {
            di as text `"`line'"'
            file read `f' line
        }
        file close `f'
    }
end
