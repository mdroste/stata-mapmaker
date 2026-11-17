foreach f in _mm_route _mm_array _mm_numbers _mm_capture_scale _mm_categories _mm_read_scales _mm_load_scale _mm_panel_init _mm_panel_select _mm_axis_save _mm_panel_add _mm_figure_request {
    capture mata: mata drop `f'()
}
capture mata: mata drop _MM_keys _MM_panels _MM_current _MM_axis _MM_cuts _MM_axis_cuts _MM_saved _MM_unmatched _MM_catkeys _MM_catlabels
mata:
_MM_keys = _MM_panels = _MM_catkeys = _MM_catlabels = J(0,1,"")
_MM_current = _MM_axis = _MM_cuts = _MM_axis_cuts = ""
_MM_saved = J(0,12,"")
_MM_unmatched = J(0,1,0)
void _mm_route()
{
    string scalar s,ch,options
    real scalar i,quoted,depth,comma,weighted
    s=st_local("original"); options=" "; quoted=depth=comma=weighted=0
    for(i=1;i<=strlen(s);i++) {
        ch=substr(s,i,1)
        if(ch==char(34)) { 
            quoted=!quoted
            continue
        }
        if(quoted) continue
        if(!comma & ch=="[") weighted=1
        if(ch=="(") depth++
        if(ch==")") {
            depth--; options=options+" "
        }
        if(depth) continue
        if(ch==",") comma=1
        else if(comma & ch!=")") options=options+ch
    }
    st_local("optionnames",strlower(options)+" ")
    st_local("weighted",strofreal(weighted))
}
string scalar _mm_array(string vector words)
{
    real scalar i
    string scalar out
    out = "["
    for (i=1; i<=length(words); i++) out=out+(i>1 ? "," : "")+_mm_json(words[i])
    return(out+"]")
}
string scalar _mm_numbers(string scalar s)
{
    string rowvector v
    string scalar out
    real scalar i
    v=tokens(s); out="["
    for(i=1;i<=cols(v);i++) out=out+(i>1 ? "," : "")+_mm_number(v[i])
    return(out+"]")
}
void _mm_capture_scale()
{
    external string scalar _MM_current, _MM_cuts
    string colvector labels
    real scalar i,n
    n=strtoreal(st_local("nbins")); labels=J(n,1,"")
    for(i=1;i<=n;i++) labels[i]=st_local("label"+strofreal(i))
    _MM_cuts=st_local("cuts")
    _MM_current="{"+_mm_json("mode")+":"+_mm_json(st_local("mode"))+","+_mm_json("interval")+":"+_mm_json("upper-inclusive")+","+
        _mm_json("cutoffs")+":"+_mm_numbers(_MM_cuts)+","+_mm_json("limits")+":"+_mm_numbers(st_local("limits"))+","+
        _mm_json("midpoint")+":"+_mm_number(st_local("midpoint"))+","+_mm_json("labels")+":"+_mm_array(labels)+","+
        _mm_json("units")+":"+_mm_json(st_local("units"))+"}"
}
void _mm_categories(string scalar ref, string scalar apply, string scalar bin, string scalar order, real scalar saved)
{
    external string scalar _MM_current
    external string colvector _MM_catkeys, _MM_catlabels
    string colvector all, display, keys, labels
    real colvector index, selected, values
    real scalar i
    all=st_sdata(.,"mm_category"); display=st_sdata(.,"mm_display")
    if(saved) {
        keys=_MM_catkeys; labels=_MM_catlabels
    }
    else {
        index=selectindex((st_data(.,ref):==1):&(all:!=""))
        keys=uniqrows(sort(all[index],1))
        if(order!="") keys=tokens(order,"|")'
        keys=select(keys,keys:!="|")
        if(rows(keys)==0 & st_local("emptyok")!="") {
            _MM_current="{"+_mm_json("mode")+":"+_mm_json("empty")+","+_mm_json("labels")+":["+_mm_json("No reference data")+"]}"
            return
        }
        if(rows(keys)<1 | rows(keys)>32 | rows(uniqrows(sort(keys,1)))!=rows(keys)) _error(198)
        labels=keys
        for(i=1;i<=rows(keys);i++) {
            index=selectindex(all:==keys[i])
            if(rows(index)) labels[i]=display[index[1]]
        }
    }
    values=st_data(.,bin); selected=st_data(.,apply)
    for(i=1;i<=rows(keys);i++) values[selectindex((all:==keys[i]):&selected)]=J(sum((all:==keys[i]):&selected),1,i)
    if(sum((all:!=""):&selected:&(values:>=.))) {
        errprintf("A category is absent from the supplied order/reference scale.\n"); _error(459)
    }
    st_store(.,bin,values)
    _MM_current="{"+_mm_json("mode")+":"+_mm_json("categorical")+","+_mm_json("interval")+":"+_mm_json("upper-inclusive")+","+
        _mm_json("labels")+":"+_mm_array(labels)+","+_mm_json("category_keys")+":"+_mm_array(keys)+","+
        _mm_json("units")+":"+_mm_json(st_local("units"))+"}"
}
void _mm_read_scales()
{
    external string matrix _MM_saved
    real colvector index
    _MM_saved=st_sdata(.,("panel","kind","mode","cutoffs","cutoffs2","limits","midpoint","nbins","category","code","label","units"))
    index=selectindex((_MM_saved[,2]:=="config"):&(_MM_saved[,3]:!="empty"))
    st_local("classification",rows(index) ? _MM_saved[index[1],3] : "quantile")
    if(_MM_saved[1,1]=="*") st_local("scale","shared")
    else st_local("scale","panel")
}
void _mm_load_scale(string scalar key, real scalar axis)
{
    external string matrix _MM_saved
    external string colvector _MM_catkeys, _MM_catlabels
    real colvector index, li
    real scalar r,i
    index=selectindex(((_MM_saved[,1]:==key):|(_MM_saved[,1]:=="*")):&(_MM_saved[,2]:=="config"))
    if(rows(index)!=1) {
        errprintf("Saved scale has no unique entry for this panel.\n"); _error(459)
    }
    r=index[1]
    st_local("mode",_MM_saved[r,3]); st_local("cuts",_MM_saved[r,axis==1 ? 4 : 5])
    st_local("limits",_MM_saved[r,6]); st_local("midpoint",_MM_saved[r,7]); st_local("nbins",_MM_saved[r,8]); st_local("units",_MM_saved[r,12])
    li=selectindex((_MM_saved[,1]:==_MM_saved[r,1]):&(_MM_saved[,2]:=="label"))
    _MM_catkeys=_MM_saved[li,9]; _MM_catlabels=_MM_saved[li,11]
    for(i=1;i<=rows(li);i++) st_local("label"+strofreal(i),_MM_saved[li[i],11])
}
void _mm_panel_init()
{
    external string colvector _MM_keys, _MM_panels
    external real colvector _MM_unmatched
    string colvector all
    real scalar i
    all=st_sdata(.,"mm_panel"); _MM_keys=uniqrows(sort(all,1))
    if(st_local("panelnumeric")=="1") _MM_keys=_MM_keys[order(strtoreal(_MM_keys),1)]
    if(st_local("panelorder")!="") {
        _MM_keys=tokens(st_local("panelorder"),"|")'; _MM_keys=select(_MM_keys,_MM_keys:!="|")
        for(i=1;i<=rows(all);i++) if(!sum(_MM_keys:==all[i])) {
            errprintf("panelorder() omits an observed panel.\n"); _error(459)
        }
    }
    if(rows(_MM_keys)>36 | rows(uniqrows(sort(_MM_keys,1)))!=rows(_MM_keys)) _error(198)
    _MM_panels=J(0,1,""); _MM_unmatched=J(rows(_MM_keys),1,0)
    for(i=1;i<=rows(_MM_keys);i++) _MM_unmatched[i]=sum((all:==_MM_keys[i]):&(st_data(.,"_merge"):==1))
    st_local("npanels",strofreal(rows(_MM_keys)))
}
void _mm_panel_select(real scalar i, string scalar ref, string scalar apply)
{
    external string colvector _MM_keys
    string colvector all
    real colvector selected, reference
    all=st_sdata(.,"mm_panel"); selected=all:==_MM_keys[i]
    reference=st_local("scale")=="panel" ? selected : J(rows(all),1,1)
    if(st_local("baseline")!="") reference=all:==st_local("baseline")
    st_store(.,ref,reference); st_store(.,apply,selected); st_local("panelkey",_MM_keys[i])
}
void _mm_axis_save()
{
    external string scalar _MM_current, _MM_axis, _MM_cuts, _MM_axis_cuts
    _MM_axis=_MM_current; _MM_axis_cuts=_MM_cuts
}
void _mm_panel_add(real scalar i)
{
    external string colvector _MM_keys, _MM_panels
    external real colvector _MM_unmatched
    external string scalar _MM_current, _MM_axis, _MM_cuts, _MM_axis_cuts
    string scalar scale
    string colvector labels
    real scalar nx,ny,j,k
    scale=_MM_axis
    if(st_local("bivariate")!="") {
        nx=cols(tokens(_MM_axis_cuts))+1; ny=cols(tokens(_MM_cuts))+1; labels=J(nx*ny,1,"")
        for(j=1;j<=ny;j++) for(k=1;k<=nx;k++) labels[(j-1)*nx+k]="X"+strofreal(k)+" / Y"+strofreal(j)
        scale="{"+_mm_json("mode")+":"+_mm_json("bivariate")+","+_mm_json("interval")+":"+_mm_json("upper-inclusive")+","+
            _mm_json("cutoffs")+":"+_mm_numbers(_MM_axis_cuts)+","+_mm_json("cutoffs2")+":"+_mm_numbers(_MM_cuts)+","+
            _mm_json("labels")+":"+_mm_array(labels)+","+_mm_json("units")+":"+_mm_json(st_local("units"))+"}"
        if(strpos(_MM_axis,_mm_json("mode")+":"+_mm_json("empty"))) scale=_MM_axis
        if(strpos(_MM_current,_mm_json("mode")+":"+_mm_json("empty"))) scale=_MM_current
    }
    _MM_panels=_MM_panels\("{"+_mm_json("key")+":"+_mm_json(_MM_keys[i])+","+_mm_json("label")+":"+_mm_json(_MM_keys[i])+","+
        _mm_json("unmatched")+":"+strofreal(_MM_unmatched[i])+","+_mm_json("scale")+":"+scale+"}")
    if(strpos(scale,_mm_json("mode")+":"+_mm_json("empty"))) st_store(selectindex(st_sdata(.,"mm_panel"):==_MM_keys[i]),"mm_bin",J(sum(st_sdata(.,"mm_panel"):==_MM_keys[i]),1,.))
}
void _mm_figure_request()
{
    external string colvector _MM_panels
    string scalar text
    string rowvector keys, locals
    real scalar i,fh
    text="{"+_mm_json("schema")+":2,"+_mm_json("operation")+":"+_mm_json("figure")
    keys=tokens("output pack data response status geography vintage title note legendtitle projection layout root datadir center region insets grids report scale baseline scalesave stylesave style manifest units xlegend ylegend points pointcrs flows maptype outline tiles cartobase results weight_semantics legendposition")
    for(i=1;i<=cols(keys);i++) text=text+","+_mm_json(keys[i])+":"+_mm_json(st_local(keys[i]))
    keys=("palette","missinglabel"); locals=("colorscheme","labelmissing")
    for(i=1;i<=cols(keys);i++) text=text+","+_mm_json(keys[i])+":"+_mm_json(st_local(locals[i]))
    keys=tokens("width height dpi reverse columns symbolmax flowtop flowmin labellimit iterations")
    locals=tokens("xsize ysize dpi reverse columns symbolmax flowtop flowmin labellimit iterations")
    for(i=1;i<=cols(keys);i++) text=text+","+_mm_json(keys[i])+":"+_mm_number(st_local(locals[i]))
    keys=tokens("replace zoom context nolegend noborders hatch rasterize graticule distortion scalebar northarrow allowvintagemismatch")
    locals=tokens("replace zoomtoregion context nolegend noborders hatchmissing rasterize graticule distortion scalebar northarrow allowvintagemismatch")
    for(i=1;i<=cols(keys);i++) text=text+","+_mm_json(keys[i])+":"+(st_local(locals[i])!="" ? "true" : "false")
    text=text+","+_mm_json("uncertainty")+":"+(st_local("uncertainty")=="1" ? "true" : "false")
    text=text+","+_mm_json("states")+":"+(st_local("nostates")=="" ? "true" : "false")
    text=text+","+_mm_json("colors")+":"+_mm_array(tokens(subinstr(st_local("colors"),","," ")))+","+_mm_json("panels")+":["
    for(i=1;i<=rows(_MM_panels);i++) text=text+(i>1 ? "," : "")+_MM_panels[i]
    fh=fopen(st_local("request"),"w"); fput(fh,text+"]}"); fclose(fh)
}
end
