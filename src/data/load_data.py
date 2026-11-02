# Functions that download the raw data and read data files.
#   download_311()    311 requests opened 2020-2025 from DataSF (no key needed)
#   download_nhgis()  ACS income/population + tract boundaries from IPUMS NHGIS (needs a key)
#   load_...()        read the raw and processed files

import getpass
import os
import time
import zipfile
from datetime import datetime, timezone

import geopandas as gpd
import pandas as pd
import requests

from src.utils import config


# ---------- 311 requests (DataSF) ----------

def download_month(start, end):
    """Download every request opened from start up to (not including) end."""
    where = f"requested_datetime >= '{start}T00:00:00' AND requested_datetime < '{end}T00:00:00'"

    # how many rows the API has for this month, to check the download
    response = requests.get(config.SF311_URL, params={"$select": "count(*) AS n", "$where": where},
                            timeout=300)
    assert response.ok, f"request failed with code {response.status_code}"
    expected = int(response.json()[0]["n"])

    # the API gives at most PAGE_SIZE rows at a time, so we ask page by page
    pages = []
    offset = 0
    while True:
        params = {"$select": ",".join(config.SF311_FIELDS), "$where": where,
                  "$order": "service_request_id", "$limit": config.PAGE_SIZE, "$offset": offset}
        response = requests.get(config.SF311_URL, params=params, timeout=300)
        assert response.ok, f"request failed with code {response.status_code}"
        payload = response.json()
        pages.append(pd.DataFrame(payload, columns=config.SF311_FIELDS))
        if len(payload) < config.PAGE_SIZE:
            break
        offset += config.PAGE_SIZE

    df = pd.concat(pages, ignore_index=True)
    # keep every column as text; missing values stay missing
    df = df.astype(str)
    return df, expected


def download_311():
    """Download the 311 requests one month at a time to data/raw/sf311/YYYY/YYYY-MM.parquet.

    Months that are already saved are skipped, so if it stops you can just run it again.
    """
    manifest_path = config.SF311_RAW / "_manifest.csv"
    for year in config.YEARS:
        (config.SF311_RAW / str(year)).mkdir(parents=True, exist_ok=True)
        for month in range(1, 13):
            label = f"{year}-{month:02d}"
            path = config.SF311_RAW / str(year) / f"{label}.parquet"
            if path.exists():
                print(label, "already downloaded")
                continue

            start = f"{year}-{month:02d}-01"
            if month == 12:
                end = f"{year + 1}-01-01"
            else:
                end = f"{year}-{month + 1:02d}-01"

            df, expected = download_month(start, end)
            if len(df) != expected or df["service_request_id"].duplicated().any():
                # the data changed while we were downloading, so don't save it and try again next run
                print(label, ": got", len(df), "rows but the API has", expected, "- run it again")
                continue
            df.to_parquet(path, index=False)

            # save when each month was downloaded (the cleaning step uses this time)
            if manifest_path.exists():
                manifest = pd.read_csv(manifest_path)
            else:
                manifest = pd.DataFrame()
            now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            row = pd.DataFrame([{"month": label, "rows": len(df), "expected_rows": expected,
                                 "downloaded_at_utc": now}])
            manifest = pd.concat([manifest, row], ignore_index=True)
            manifest.to_csv(manifest_path, index=False)
            print(label, ":", len(df), "rows")


# ---------- ACS and tract boundaries (IPUMS NHGIS) ----------

def download_nhgis():
    """Download the ACS tract table and the 2024 tract shapefile from NHGIS to data/raw/nhgis/.

    Needs an IPUMS API key: set IPUMS_API_KEY in the terminal, or type it when asked.
    Skipped if both files are already there.
    """
    out_dir = config.NHGIS_RAW
    out_dir.mkdir(parents=True, exist_ok=True)
    if list(out_dir.rglob("*_tract.csv")) and list(out_dir.rglob("*.shp")):
        print("NHGIS files already downloaded")
        return

    api_key = os.environ.get("IPUMS_API_KEY")
    if api_key is None:
        # a masked prompt: what you type is not shown and not saved
        api_key = getpass.getpass("IPUMS API key: ")
    params = {"collection": "nhgis", "version": "2"}
    headers = {"Authorization": api_key}

    # 1. ask NHGIS for median household income and population for every California tract,
    #    plus the 2024 tract boundaries
    extract = {
        "datasets": {config.NHGIS_DATASET: {"dataTables": config.NHGIS_TABLES,
                                            "geogLevels": ["tract"]}},
        "geographicExtents": ["060"],
        "shapefiles": [config.NHGIS_SHAPEFILE],
        "dataFormat": "csv_no_header",
        "breakdownAndDataTypeLayout": "single_file",
        "description": "CP101 SF 311 project",
    }
    response = requests.post(config.NHGIS_URL, params=params, headers=headers, json=extract,
                             timeout=120)
    assert response.ok, f"request failed with code {response.status_code}: {response.text}"
    number = response.json()["number"]
    print("submitted extract", number)

    # 2. wait until NHGIS has made the files (usually a few minutes)
    while True:
        response = requests.get(config.NHGIS_URL + str(number), params=params, headers=headers,
                                timeout=120)
        assert response.ok, f"request failed with code {response.status_code}"
        info = response.json()
        print("status:", info["status"])
        if info["status"] == "completed":
            break
        assert info["status"] not in ["failed", "canceled"], f"extract {number} {info['status']}"
        time.sleep(15)

    # 3. download the table and the shapefile zips and unzip them
    for kind in ["tableData", "gisData"]:
        url = info["downloadLinks"][kind]["url"]
        zip_path = out_dir / url.split("/")[-1]
        response = requests.get(url, headers=headers, timeout=600)
        assert response.ok, f"download failed with code {response.status_code}"
        with open(zip_path, "wb") as f:
            f.write(response.content)
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(out_dir)
        print("saved", zip_path.name)

    # 4. NHGIS puts the shapefile in a zip inside its zip, so unzip that one too
    for inner_zip in out_dir.glob("*/*.zip"):
        with zipfile.ZipFile(inner_zip) as z:
            z.extractall(inner_zip.parent)
        print("unzipped", inner_zip.name)


# ---------- reading files ----------

def load_raw_311(year):
    """All raw 311 requests opened in one year (every column is text)."""
    return pd.read_parquet(config.SF311_RAW / str(year))


def load_download_time():
    """When the 311 data was downloaded, in San Francisco time like the 311 timestamps."""
    manifest = pd.read_csv(config.SF311_RAW / "_manifest.csv")
    snapshot = pd.to_datetime(manifest["downloaded_at_utc"], utc=True).max()
    return snapshot.tz_convert("America/Los_Angeles").tz_localize(None)


def load_reference():
    """Our cleaning rules: category_map.csv and status_rules.csv."""
    category_map = pd.read_csv(config.REFERENCE / "category_map.csv")
    status_rules = pd.read_csv(config.REFERENCE / "status_rules.csv")
    return category_map, status_rules


def load_raw_acs():
    """The NHGIS tract table (if there are several, use the last one)."""
    csv_path = sorted(config.NHGIS_RAW.glob("**/*_tract.csv"))[-1]
    # every column as text, so codes like "06" and "075" keep their leading zeros
    return pd.read_csv(csv_path, dtype=str)


def find_tract_shapefile():
    """Path of the one tract shapefile in data/raw/nhgis."""
    candidates = sorted(config.NHGIS_RAW.rglob("*.shp"))
    assert len(candidates) == 1, (
        f"expected one tract shapefile in data/raw/nhgis, found {len(candidates)}")
    return candidates[0]


def load_tracts(path):
    """San Francisco census tract polygons (GEOID, geometry) in EPSG:2227."""
    tracts = gpd.read_file(path)
    if tracts.crs is None:
        raise ValueError("Boundary CRS is missing. Include the shapefile's .prj file.")
    # NHGIS/TIGER releases may use either spelling for the Census identifier.
    geoid = next((c for c in ["GEOID", "GEOID20", "GEOID24"] if c in tracts), None)
    if geoid is None:
        raise ValueError(f"No GEOID field found. Boundary columns: {list(tracts.columns)}")
    tracts["GEOID"] = tracts[geoid].astype("string").str.zfill(11)
    tracts = tracts.loc[tracts["GEOID"].str.startswith("06075"), ["GEOID", "geometry"]].copy()
    if tracts.empty or not tracts["GEOID"].str.fullmatch(r"\d{11}").all():
        raise ValueError("Expected 11-digit San Francisco tract GEOIDs starting with 06075.")
    if not tracts["GEOID"].is_unique:
        raise ValueError("Duplicate tract GEOIDs: inspect boundaries before joining.")
    if (tracts.geometry.isna() | tracts.geometry.is_empty | ~tracts.geometry.is_valid).any():
        raise ValueError("Missing, empty, or invalid tract geometry: inspect boundaries first.")
    if not tracts.geom_type.isin(["Polygon", "MultiPolygon"]).all():
        raise ValueError("Census tract boundaries must be polygons.")
    return tracts.to_crs(config.CRS).reset_index(drop=True)


def load_requests_with_tracts():
    """Cleaned requests that the spatial join put in a tract (only the columns the charts use)."""
    requests_df = pd.read_parquet(config.REQUESTS_WITH_TRACTS,
                                  columns=["service_request_id", "request_type", "year", "GEOID",
                                           "is_open", "days_to_close"])
    requests_df = requests_df.loc[requests_df["GEOID"].notna()].copy()
    requests_df["GEOID"] = requests_df["GEOID"].astype(str)
    return requests_df


def load_clean_requests(columns):
    """Some columns of all cleaned requests (data/processed/requests_clean.parquet)."""
    return pd.read_parquet(config.REQUESTS_CLEAN, columns=columns)


def load_acs():
    """Cleaned ACS income and population for each San Francisco tract."""
    return pd.read_parquet(config.ACS_TRACTS)


def load_sf_tracts():
    """San Francisco tract polygons with their request counts (made by the spatial join)."""
    return gpd.read_parquet(config.SF_TRACTS)
