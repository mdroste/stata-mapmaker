*! mapmaker_setup 2.0.0a1 16nov2026
program define mapmaker_setup
    version 16
    syntax, [PYTHON(string) ENGINE(string) DATADIR(string)]
    mapmaker geography defaults, python(`"`python'"') engine(`"`engine'"') datadir(`"`datadir'"')
    di as text "Default states, counties and commuting zones are ready."
    di as text "Run mapmaker geography browse to find optional boundaries."
end
