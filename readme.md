
mapmaker
=================================

[Overview](#overview)
| [Motivation](#motivation)
| [Installation](#installation)
| [Usage](#usage)
| [Benchmarks](#benchmarks)
| [To-Do](#todo)
| [Acknowledgements](#acknowledgements)
| [License](#license)

Pretty choropleth maps in Stata (with Python and D3JS)

`version 0.5 09jul2019`


Overview
---------------------------------

mapmaker is a program for producing choropleth maps in Stata. It uses a combination of Python, PhantomJS, and D3JS to render D3-style choropleth maps and take a snapshot.



Demonstration
---------------------------------


Prerequisites
---------------------------------

Mapmaker requires Stata 16 and a Python installation (2.7 or 3.x).


Installation
---------------------------------




1. The following commands will install mapmaker on your machine, if you have internet access

```stata
net install mapmaker, from("https://raw.githubusercontent.com/mdroste/stata-mapmaker/master/")
mapmaker_setup
```

2. A ZIP containing the program can be downloaded and manually placed on the user's adopath from Github. The files in 'src' should be in a subfolder called 'mapmaker' in your personal directory, while mapmaker.ado can be located anywhere on your adopath.


Usage
---------------------------------

Complete internal documentation is provided with the installation and can be accessed by typing:
```stata
help mapmaker
````

The basic syntax and usage of mapmaker somewhat similar to the popular program maptile; however, there are important differences between these two programs in how they handle zooming and subsetting. For more information, refer to the internal documentation.

This repository includes a do-file, examples.do, that demonstrates how to produce maps at a few different geographic levels.


Benchmarks
---------------------------------

![binscatter2 benchmark](benchmarks/benchmarks.png "binscatter2 benchmark")


  
Todo
---------------------------------

Longer term, more ambitious stuff:
- [ ] Modular system for importing / adding new geographic templates


Acknowledgements
---------------------------------

As stated previously, mapmaker is a Stata wrapper for a set of scripts to produce D3JS maps written by the inimitable Jimmy Narang.

This program benefited from about two years of internal testing with Opportunity Insights.


License
---------------------------------

mapmaker is [MIT-licensed](https://github.com/mdroste/stata-mapmaker/blob/master/LICENSE).
