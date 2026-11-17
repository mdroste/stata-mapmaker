# Research-feature validation

Validated on the development Windows x64 machine with Stata 19, November 16, 2026.
The command declares Stata 16 compatibility; a separate Stata 16 machine and public
release signing/clean-machine tests remain P0 release work.

- **68 Python regression tests pass**, covering existing geography/projection work
  and the new typed figure, style/scale, layer, layout, archive, and crosswalk logic.
- **Original Stata suite passes** with the legacy rendering path and its original
  classification/formatting behavior.
- **Research Stata suite passes against source and the packaged runtime**: shared
  and panel scales, absent/missing panels, weighted baseline percentiles, exact scale
  reuse, continuous/categorical/diverging/bivariate maps, symbols, labels,
  uncertainty, tile/Dorling layouts, styles, manifests, and offline archives.
- **Edge/allocation Stata suite passes in both runtimes**: empty saved scales,
  missing values, invalid cutoffs, explicit numerator/denominator allocation,
  conservation reports, and caller data preservation. Numeric crosswalk output is
  imported as doubles to preserve rate precision.
- **Bundled examples pass without Python/engine overrides** and preserve the
  dataset on both success and overwrite refusal. The original bundled quickstart,
  default packs, CRS search, shapefile/GeoJSON import, seam handling, tables, and
  CZ dissolve smoke checks also pass.

The real-geography fixture uses 3,234 Census 2020 counties, two synthetic panels
(6,468 observations), matching state outlines, symbols, points, aggregate flows,
uncertainty, labels, and local north/scale decorations. Source and frozen PNG
pixels match exactly. All three frozen output formats pass geometry, panel-count,
layer, scale, and omitted-volume assertions. Warm-cache development-machine timings:

| Format | Frozen elapsed | Output size |
| --- | ---: | ---: |
| PNG, 100 DPI | 24.1 seconds | 0.48 MB |
| PDF | 25.6 seconds | 23.15 MB |
| SVG | 24.9 seconds | 67.43 MB |

These are deliberately dense figures with thousands of symbols and detailed
polygons. Vector export size is separate from installer size. Select a smaller
extent, omit unnecessary layers, or use PNG/rasterized fills when file size matters.
Timings are measurements on this machine, not performance guarantees.

The Windows ZIP is approximately **58.6 MB** and the extracted bundle **127.1 MB**.
This increment adds no binary dependencies. Styles, scales, and manifests are JSON;
additional geographies and selected grids remain optional downloads.

Reproduce the checks from a development checkout with `python -m unittest discover
-s tests -q`, `tests/stata.do`, `tests/features.do`, `tests/features_edges.do`, and
`tools/check_features.py`. Pass `bundled` to the two feature do-files to test the
extracted Windows bundle, and `--bundle dist/mapmaker-windows-amd64` to the capacity
check. Test data are synthetic. Runtime users need only the packaged bundle.
