
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


Requirements
---------------------------------

Mapmaker requires Stata 16 and Python installed on your computer/server.


Installation
---------------------------------

There are two options for installing mapmaker.


1. The most recent version can be installed from Github with the following Stata commands:

```stata
net install mapmaker, from("https://raw.githubusercontent.com/mdroste/stata-mapmaker/master/stata_install")
mapmaker_setup
```

2. A ZIP containing the program can be downloaded and manually placed on the user's adopath. The contents of stata_install/src.zip must be located in the folder mapmaker on the user's "personal" directory, which can be located by typing the following command in the Stata console: 
```stata
di "`c(sysdir_personal'" 

This project will be submitted to the SSC repository very soon.


Usage
---------------------------------

Complete internal documentation is provided with the installation and can be accessed by typing:
```stata
help mapmaker
````

Basic usage of mapmaker is quite similar to the popular Stata package maptile. A very basic map command takes the form:
```stata
mapmaker variable_to_map, geo(geographic_template_to_use)
````
This repository includes a do-file, mapmaker_examples.do, that provides a number of examples for producing maps with the included geographic templates.



Screenshots
---------------------------------

Coming soon.

  
Todo
---------------------------------

I can think of a few things that would be nice to have:
[ ] - Modular system for loading/installing geographies
[ ] - Fix handling of missing data when using 'zoom' option
[ ] - Smarter cropping / placement of legend


Acknowledgements
---------------------------------

Mapmaker is essentially a Stata wrapper and extension of functionality from the illustrious Jimmy Narang's mapmaker suite, in the same way that maptile is a wrapper around the functionality provided by spmap. So Jimmy is owed a ton of credit for this work, which he did while working as a pre-doc at the Lab for Economic Applications and Policy at Harvard (now Opportunity Insights).

Mapmaker also relies on a few other awesome libraries to work; in particular D3, PhantomJS, jQuery, and colorbrewer.


License
---------------------------------

mapmaker is [MIT-licensed](https://github.com/mdroste/stata-mapmaker/blob/master/LICENSE).
