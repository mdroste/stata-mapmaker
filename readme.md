
mapmaker
=================================

[Overview](#overview)
| [Installation](#installation)
| [Usage](#usage)
| [Screenshots](#screenshots)
| [To-Do](#todo)
| [Acknowledgements](#acknowledgements)
| [License](#license)

Pretty choropleth maps in Stata (with Python and D3JS)

`version 0.10 10jul2019`


Overview
---------------------------------

mapaker is a program for producing publication-quality choropleth maps in Stata. It is especially useful when visualizing data at fine geographic levels: for instance, United States census tracts.


Mapmaker is able to produce high-quality maps by creating them outside of Stata's graphical engine. In particular, mapmaker writes the data to be mapped out to a csv and calls to a Python script using Stata 16's new Python integration. This Python script modifies a template choropleth map rendered in D3JS, calls a headless browser (PhantomJS) to render the map, and takes a screenshot. 


Coming soon. You could probably figure out how to install it from here and it works, but there's some hitches I'd like to fix first.