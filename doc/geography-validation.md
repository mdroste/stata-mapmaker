# Geography expansion validation

Development-machine validation, November 2026. This is not a signed release or a
clean-machine certification. The exact source versions, hashes, IDs, and source
URLs are in `catalog/geographies.json`.

- **1,275 catalog entries:** 1,269 provider downloads, one ERS-derived pack,
  four legacy entries, and one NHGIS manual-import recipe.
- **All 1,269 downloadable entries** were installed from their checksum-pinned
  cached sources in isolated temporary libraries and reloaded with integrity
  verification. Source identifiers and feature counts were audited before catalog
  inclusion. The consolidated local report is `.cache/geography-validation-final.json`.
- **54 representative preview exports** in the bulk audit, plus the five distinct
  CZ definitions, Stata world preview, and a separate block benchmark. PNG maps
  of ERS 2020 and Natural Earth world countries were visually inspected.
- The ERS final 2020 dissolve produced **598 zones from 3,222 counties**. All member
  IDs match the 2024 county dependency; the 2020 county dependency fails explicitly
  on Connecticut planning-region IDs.
- **33 Python tests** passed. These include holes, seam-split area conservation,
  polar edges, string IDs, attribute/membership integrity, partial provider
  responses, versioned partitions, county-dissolve area, wrong-vintage rejection,
  and nonhierarchical IDs' panel placement.
- `tests/expanded.do` passed in Stata 19: browsing, attributes/IDs/membership frames,
  diagnostics, verification, PDF preview, and GeoJSON import; the active dataset's
  signature was unchanged. Existing frames and files were protected.
- The frozen Windows runtime passed shapefile and GeoJSON imports, long IDs,
  date-line splitting, attribute exports, the ERS county dissolve, CRS search,
  and PNG/PDF/SVG output. `tests/bundle.do` passed from outside the source directory
  with no Python or engine override.
- Fresh downloads through the installer's HTTPS/redirect restrictions matched
  pinned checksums for Natural Earth, GISCO, geoBoundaries, ONS, Statistics Canada,
  UCLA, and USGS representative sources.

The Providence County block pilot has 13,417 polygons and occupied **4.43 MB**
installed. A fresh-process install, integrity check, and preview took approximately
**5.35 seconds** with **409 MB peak working set** on this development machine.
These are workload measurements, not minimum memory requirements or guarantees on
other computers. County-scoped blocks remain an advanced pilot; nationwide blocks
are not offered as a default download.

The 33,791-feature national ZCTA pack occupied **43.90 MB** installed. Its complete
check and preview took approximately **46.67 seconds** after caching the panel
transformer per source. Detailed packs remain optional.

Optional providers can change their downloads or become unavailable. A changed
source checksum deliberately fails installation until a new revision is reviewed.
The renderer does not silently substitute another vintage, datum transformation,
or boundary provider. The [geography guide](geographies.md) documents the remaining
coverage and projection limits.
