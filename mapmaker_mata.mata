capture mata: mata drop _mm_json()
capture mata: mata drop _mm_number()
capture mata: mata drop _mm_request()
capture mata: mata drop _mm_quote()
capture mata: mata drop _mm_command()
mata:
string scalar _mm_json(string scalar s)
{
    real scalar i, n
    string scalar out, ch
    out = char(34)
    for (i=1; i<=strlen(s); i++) {
        ch = substr(s,i,1)
        n = ascii(ch)
        if (n==34 | n==92) out = out + char(92) + ch
        else if (n<32) out = out + char(92) + "u00" +
            substr("0123456789abcdef",floor(n/16)+1,1) +
            substr("0123456789abcdef",mod(n,16)+1,1)
        else out = out + ch
    }
    return(out + char(34))
}
string scalar _mm_number(string scalar s)
{
    s = strtrim(s)
    if (substr(s,1,1)==".") s = "0"+s
    if (substr(s,1,2)=="-.") s = "-0"+substr(s,2,.)
    return(s)
}
void _mm_request()
{
    real scalar fh, i, n
    string scalar text
    string rowvector keys, locals, words
    text = "{" + char(34) + "schema" + char(34) + ":1"
    keys = ("output","pack","data","response","status","geography","vintage","palette","title","note","legendtitle","missinglabel")
    locals = ("output","pack","data","response","status","geography","vintage","colorscheme","title","note","legendtitle","labelmissing")
    for(i=1; i<=cols(keys); i++) text = text + "," + _mm_json(keys[i]) + ":" + _mm_json(st_local(locals[i]))
    keys = ("nbins","width","height","dpi","reverse")
    locals = ("nbins","xsize","ysize","dpi","reverse")
    for(i=1; i<=cols(keys); i++) text = text + "," + _mm_json(keys[i]) + ":" + _mm_number(st_local(locals[i]))
    keys = ("replace","zoom","context","nolegend","noborders","hatch","rasterize")
    locals = ("replace","zoomtoregion","context","nolegend","noborders","hatchmissing","rasterize")
    for(i=1; i<=cols(keys); i++) text = text + "," + _mm_json(keys[i]) + ":" + (st_local(locals[i])!="" ? "true" : "false")
    text = text + "," + _mm_json("states") + ":" + (st_local("nostates")=="" ? "true" : "false")
    text = text + "," + _mm_json("labels") + ":["
    n = strtoreal(st_local("nbins"))
    for(i=1; i<=n; i++) text = text + (i>1 ? "," : "") + _mm_json(st_local("label"+strofreal(i)))
    text = text + "]," + _mm_json("cutoffs") + ":["
    words = tokens(st_local("cuts"))
    for(i=1; i<=cols(words); i++) text = text + (i>1 ? "," : "") + _mm_number(words[i])
    text = text + "]," + _mm_json("colors") + ":["
    words = tokens(subinstr(st_local("colors"), ",", " "))
    for(i=1; i<=cols(words); i++) text = text + (i>1 ? "," : "") + _mm_json(words[i])
    text = text + "]}"
    fh = fopen(st_local("request"), "w")
    fput(fh, text)
    fclose(fh)
}
string scalar _mm_quote(string scalar s)
{
    if (st_global("c(os)")=="Windows") {
        if (strpos(s,char(34)) | strpos(s,"%") | strpos(s,"!") | strpos(s,char(10)) | strpos(s,char(13))) {
            errprintf("Unsupported shell characters in executable or temporary path\n")
            _error(198)
        }
        return(char(34)+s+char(34))
    }
    return(char(39)+subinstr(s,char(39),char(39)+char(34)+char(39)+char(34)+char(39))+char(39))
}
void _mm_command()
{
    string scalar command
    if (st_local("python")!="") command = _mm_quote(st_local("python")) + " " + _mm_quote(st_local("script"))
    else command = _mm_quote(st_local("engine"))
    command = command + " --request " + _mm_quote(st_local("request"))
    st_local("command", command)
}
end
