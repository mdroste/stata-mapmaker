"""Reviewed provider recipes for expand_catalog.py; never fetched at startup."""
import json
import re
from urllib.parse import urlencode

from expand_catalog import fetch


def entry(ident, level, vintage, country, provider, url, fields, **extra):
    return dict(pack_id=ident, revision="1", geography=level, vintage=str(vintage),
                country=country, provider=provider, title=ident.replace("_", " "),
                source_url=url, id_fields=fields, id_kind="string", id_width=0,
                layout="single", default=False, priority="P2", **extra)


def naturalearth():
    for scale in ["110m", "50m", "10m"]:
        for level, folder, stem in [("country", "cultural", "admin_0_countries"), ("coastline", "physical", "coastline")]:
            version = ("5.0.0-pre9" if scale == "10m" else "4.1.0") if level == "coastline" else "5.1.1"
            e = entry(f"world_ne_{level}_{scale}", level, version, "WORLD", "Natural Earth",
                f"https://naciscdn.org/naturalearth/{scale}/{folder}/ne_{scale}_{stem}.zip",
                ["NE_ID"] if level == "country" else ["_mm_source_row"],
                scale=scale, license="Public domain", license_url="https://www.naturalearthdata.com/about/terms-of-use/",
                source_page=f"https://www.naturalearthdata.com/downloads/{scale}-{folder}-vectors/",
                boundary_policy="Natural Earth de facto boundaries; provider ISO fields are attributes, not unique join keys.",
                geometry_type="polygon" if level == "country" else "line")
            e.update(title=f"World {level}: Natural Earth {scale}", priority="P1")
            if level == "coastline":
                e["id_method"] = "1-based source record number, stable only within this source checksum"
            yield e


def gisco():
    base = "https://gisco-services.ec.europa.eu/distribution/v2/nuts/"
    for year in [2010, 2013, 2016, 2021, 2024]:
        available = json.loads(fetch(base+f"nuts-{year}-files.json"))["geojson"]
        for level in [1, 2, 3]:
            filename = f"NUTS_RG_10M_{year}_4326_LEVL_{level}.geojson"
            if filename not in available:
                raise ValueError("GISCO file missing: " + filename)
            e = entry(f"eu_nuts{level}_{year}_10m", f"nuts{level}", year, "EU", "Eurostat GISCO", base+available[filename], ["NUTS_ID"],
                format="geojson", source_crs_override="EPSG:4326", scale="10m", coverage="Countries/regions included in this GISCO edition; see CNTR_CODE",
                license="GISCO specific download provisions", license_url="https://ec.europa.eu/eurostat/web/gisco/geodata/administrative-units",
                attribution=f"© EuroGeographics for the administrative boundaries; Eurostat GISCO NUTS {year}",
                source_page="https://ec.europa.eu/eurostat/web/gisco/geodata/statistical-units/territorial-units-statistics")
            e["title"] = f"Europe: NUTS {level}, {year} classification (1:10 million)"
            yield e


def geoboundaries():
    for level in ["ADM1", "ADM2"]:
        for row in json.loads(fetch(f"https://www.geoboundaries.org/api/current/gbOpen/ALL/{level}/")):
            iso, boundary = row["boundaryISO"], row["boundaryID"]
            url = row["simplifiedGeometryGeoJSON"]
            # The API returns a commit-specific file, never a mutable branch URL.
            if not re.search(r"/raw/[0-9a-f]{7,40}/releaseData/gbOpen/", url):
                raise ValueError("Expected a commit-pinned gbOpen URL")
            e = entry(f"gbopen_{iso.lower()}_{level.lower()}_{boundary.rsplit('-',1)[-1]}", level.lower(), row["boundaryYearRepresented"], iso,
                "geoBoundaries gbOpen", url, ["shapeID"], format="geojson", scale="provider simplified",
                coverage=row["boundaryName"], source_release=row["buildDate"], boundary_id=boundary,
                license=row["boundaryLicense"], license_url=row["licenseSource"],
                attribution="geoBoundaries (CC BY 4.0 compliant gbOpen); original source: " + row["boundarySource"],
                source_page=f"https://www.geoboundaries.org/api/current/gbOpen/{iso}/{level}/",
                definition_note="Country-specific source year and administrative definitions; ADM levels are not internationally equivalent.")
            e.update(title=f"{row['boundaryName']}: {level} ({row['boundaryYearRepresented']})", priority="P3")
            yield e


def australia():
    for year, edition, end in [(2021, 3, 2026), (2026, 4, 2031)]:
        page = f"https://www.abs.gov.au/statistics/standards/australian-statistical-geography-standard-asgs/edition-{edition}-july-{year}-june-{end}/access-and-downloads/digital-boundary-files"
        links = re.findall(r'href="([^"]+\.zip)"', fetch(page).decode())
        for level in ["STE", "SA2", "SA3", "SA4", "LGA"]:
            candidates = [u for u in links if u.rsplit('/',1)[-1] == f"{level}_{year}_AUST_SHP_GDA2020.zip" or
                          u.rsplit('/',1)[-1] == f"{level}_{year}_AUST_GDA2020_SHP.zip"]
            if not candidates:
                raise ValueError(f"Missing ABS {level} {year}")
            url = candidates[0]
            if url.startswith("/"):
                url = "https://www.abs.gov.au" + url
            e = entry(f"au_{level.lower()}_{year}", level.lower(), year, "AU", "Australian Bureau of Statistics", url,
                [f"{level}_CODE{str(year)[-2:]}"], scale="digital", source_page=page,
                license="CC BY 4.0", license_url="https://www.abs.gov.au/website-privacy-copyright-and-disclaimer/copyright",
                attribution=f"Australian Bureau of Statistics, ASGS Edition {edition}, {year}",
                definition_note="Includes provider nonspatial codes in attributes where supplied; empty geometries are reported separately.",
                skip_null_geometry=True)
            e["title"] = f"Australia: {level}, {year} (GDA2020)"
            yield e


def canada():
    base = "https://geo.statcan.gc.ca/geo_wa/rest/services/2021/Cartographic_boundary_files/MapServer/"
    for level, layer, field, label in [("province", 0, "PRUID", "Provinces and territories"),
                                    ("census_division", 4, "CDUID", "Census divisions"),
                                    ("cma", 6, "CMAPUID", "Census metropolitan areas/agglomerations (province parts)"),
                                    ("tract", 11, "CTUID", "Census tracts")]:
        expected = json.loads(fetch(base+str(layer)+"/query?where=1%3D1&returnCountOnly=true&f=json"))["count"]
        for province in (["10", "11", "12", "13", "24", "35", "46", "47", "48", "59", "60", "61", "62"] if expected > 6000 or level == "census_division" else [None]):
            where = f"PRUID='{province}'" if province else "1=1"
            count = json.loads(fetch(base+str(layer)+"/query?"+urlencode(dict(where=where,returnCountOnly="true",f="json"))))["count"]
            if not count:
                continue
            if count > 6000:
                raise ValueError("Statistics Canada partition exceeds server limit")
            url = base + str(layer) + "/query?" + urlencode(dict(where=where, outFields="*", orderByFields=field,
                outSR=4326, f="geojson", geometryPrecision=6, maxAllowableOffset=0.001))
            e = entry(f"ca_{province + '_' if province else ''}{level}_2021", level, 2021, "CA", "Statistics Canada", url, [field],
                format="geojson", expected_source_count=count,
                scale="cartographic; service generalization 0.001 degrees", license="Statistics Canada Open Licence", attribution="Statistics Canada, 2021 Census Boundary Files",
                license_url="https://www.statcan.gc.ca/en/reference/licence",
                source_page="https://www150.statcan.gc.ca/n1/pub/92-160-g/92-160-g2021002-eng.htm")
            e["title"] = f"Canada: {label} (2021 cartographic)" + (f", province {province}" if province else "")
            yield e


def uk():
    for level, service, field, label in [
        ("lad", "Local_Authority_Districts_December_2024_Boundaries_UK_BGC", "LAD24CD", "Local authorities, December 2024"),
        ("pcon", "Westminster_Parliamentary_Constituencies_July_2024_Boundaries_UK_BGC", "PCON24CD", "Westminster constituencies, July 2024")]:
        base = f"https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/{service}/FeatureServer/0"
        info = json.loads(fetch(base+"?f=json"))
        count = json.loads(fetch(base+"/query?where=1%3D1&returnCountOnly=true&f=json"))["count"]
        if count > info["maxRecordCount"]:
            raise ValueError("ONS source needs pagination")
        url = base + "/query?" + urlencode(dict(where="1=1", outFields="*", orderByFields=field, outSR=4326, f="geojson"))
        e = entry(f"uk_{level}_2024_bgc", level, 2024, "GB", "Office for National Statistics", url, [field],
            format="geojson", source_crs_override="EPSG:4326", expected_source_count=count, scale="BGC 20m", coverage="United Kingdom",
            source_page="https://geoportal.statistics.gov.uk/", license="Open Government Licence; ONS/OS conditions",
            license_url="https://www.ons.gov.uk/methodology/geography/licences",
            attribution="Contains OS data © Crown copyright and database right 2024; contains National Statistics data © Crown copyright and database right 2024")
        e["title"] = "UK: " + label
        yield e


def historical():
    for congress in range(1, 120):
        year = 1789 + (congress-1)*2
        e = entry(f"us_ucla_cd{congress:03}", "cd", year, "US", "Lewis, DeVine, Pitcher and Martis (UCLA)",
            f"https://github.com/JeffreyBLewis/congressional-district-boundaries/releases/download/latest-shapefiles/districts{congress:03}.zip",
            ["ID"], congress=congress, source_release="2.0.0; checksum-pinned distribution", scale="provider resolution", encoding="cp1252",
            license="MIT", license_url="https://raw.githubusercontent.com/JeffreyBLewis/congressional-district-boundaries/master/LICENSE",
            attribution="Lewis, DeVine, Pitcher and Martis (2013), Digital Boundary Definitions of United States Congressional Districts",
            source_page="https://cdmaps.polisci.ucla.edu/",
            definition_note="Join on provider ID (state + plan range + district), not modern 4-digit Census GEOID. Historical exceptions and -1 territories retained.")
        e.update(title=f"UCLA: {congress}th Congress ({year})", layout="us-insets")
        yield e


def psu():
    paths = [(1990, "ERS-1990-10nfrbj.zip", "LM_Code", None), (2000, "ERS-2000-v3z1p5.zip", "LM_Code", None),
             (2010, "ERS-2010-2fcqzlr.zip", "LM_Code", "ERS10.shp"),
             (2020, "CommutingZones2020_GIS_files-f4865585754afcad.zip", "CZ20", None)]
    for year, filename, field, member in paths:
        prefix = "https://sites.psu.edu/psucz/files/" + ("2024/01/" if year == 2020 else "2018/09/")
        series = "ers" if year in {1990, 2000} else "psu"
        e = entry(f"us_{series}_cz_{year}", "cz", year, "US", "Penn State Labor-sheds (ERS definitions for 1990/2000)", prefix+filename, [field],
            source_page="https://sites.psu.edu/psucz/data/", license="Provider research data; cite source and methodology",
            attribution="Penn State Labor-sheds for Regional Analysis; ERS source definitions where indicated",
            definition_note="Provider-prepared polygons. PSU 2020 differs from ERS 2020; vintage alone is not a unique definition.", scale="provider resolution")
        e.update(layout="us-insets", title=f"{series.upper()} commuting zones, {year}", priority="P1")
        if year < 2020:
            e.update(layout="single", recommended_projection="source",
                     definition_note="Provider-prepared polygons on an unnamed spherical datum. Auto preserves the supplied Lambert azimuthal projection in one panel; cross-datum reprojection is not assumed. Exact ERS/PSU membership is shipped separately.")
        if member:
            e["source_member"] = member
        yield e


def environment():
    for level in [3, 4]:
        e = entry(f"us_epa_ecoregion{level}", f"ecoregion{level}", "source-2026-11-16", "US", "U.S. EPA",
            f"https://dmap-prod-oms-edc.s3.us-east-1.amazonaws.com/ORD/Ecoregions/us/us_eco_l{level}.zip", [f"US_L{level}CODE"],
            license="U.S. EPA public data", source_page="https://www.epa.gov/eco-research/level-iii-and-iv-ecoregions-continental-united-states",
            scale="provider resolution", definition_note="Provider taxonomy; download snapshot is not the boundary reference year.")
        e.update(title=f"U.S. EPA Level {level} ecoregions", priority="P3")
        e.update(dissolve=True, repair="make_valid", recommended_projection="source",
                 aggregation="Union source parts by ecoregion code; retain only attributes constant within a region")
        yield e
    for level, layer in [(2, 1), (4, 2), (8, 4)]:
        base = f"https://hydro.nationalmap.gov/arcgis/rest/services/wbd/MapServer/{layer}"
        info = json.loads(fetch(base+"?f=json"))
        field = next(f["name"] for f in info["fields"] if f["name"].lower() == f"huc{level}")
        count = json.loads(fetch(base+"/query?where=1%3D1&returnCountOnly=true&f=json"))["count"]
        if count > info["maxRecordCount"]:
            # HUC8 is partitioned by HUC2 to keep files and requests bounded.
            regions = [f"{n:02}" for n in range(1, 23)]
        else:
            regions = [None]
        for region in regions:
            where = f"{field} LIKE '{region}%'" if region else "1=1"
            expected = json.loads(fetch(base+"/query?"+urlencode(dict(where=where, returnCountOnly="true", f="json"))))["count"]
            if not expected:
                continue
            if expected > info["maxRecordCount"]:
                raise ValueError("Watershed partition still exceeds server limit")
            url = base+"/query?"+urlencode(dict(where=where, outFields="*", orderByFields=field, outSR=4326, f="geojson", geometryPrecision=5, maxAllowableOffset=0.002))
            e = entry(f"us_wbd_huc{level}"+("_"+region if region else ""), f"huc{level}", "source-2026-11-16", "US", "USGS Watershed Boundary Dataset", url, [field],
                format="geojson", source_crs_override="EPSG:4326", expected_source_count=expected, scale="service generalization 0.002 degrees", source_page="https://www.usgs.gov/national-hydrography/access-national-hydrography-products",
                license="U.S. Geological Survey public data", definition_note="Checksum-pinned service snapshot; HUC taxonomy and source attributes retained.")
            e.update(title=f"USGS HUC{level}"+(f" in region {region}" if region else ""), priority="P3")
            yield e


def blocks():
    # Bounded advanced pilot: DC and the five Rhode Island counties. Each entry
    # records the larger state download and installs only its selected county.
    for state, counties in [("11", ["001"]), ("44", ["001", "003", "005", "007", "009"])]:
        for county in counties:
            e = entry(f"us_{state}{county}_block_2020", "block", 2020, "US", "U.S. Census Bureau",
                f"https://www2.census.gov/geo/tiger/TIGER2020/TABBLOCK20/tl_2020_{state}_tabblock20.zip", ["GEOID20"],
                filter={"COUNTYFP20": county}, state_fips=state, county_fips=state+county,
                license="U.S. Census Bureau public data", scale="TIGER detailed", source_page="https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html",
                definition_note="Advanced county-only pack. Downloads a state archive, retains only this county, and discards the archive after installation.")
            e.update(title=f"Census blocks: county {state}{county} (2020)", id_kind="digits", id_width=15,
                     layout="us-insets", priority="P3")
            yield e


def seeds_for(provider):
    functions = dict(naturalearth=naturalearth, gisco=gisco, geoboundaries=geoboundaries,
                     australia=australia, canada=canada, uk=uk, historical=historical, psu=psu, environment=environment, blocks=blocks)
    if provider == "international":
        for name in ["naturalearth", "gisco", "australia", "canada", "uk"]:
            yield from functions[name]()
    else:
        yield from functions[provider]()
