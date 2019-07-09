#!/bin/bash
python3 map_maker_wrapper.py -df sampledata\czdata.csv
./bin/mac.phatomjs rasterize.js map_template czdata.png
