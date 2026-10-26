# Download ACS 2020-2024 tract data (income, population) and tract boundaries from IPUMS NHGIS.
# Run from the repo root: python scripts/02_download_nhgis.py
# Needs an IPUMS API key: set IPUMS_API_KEY in your terminal, or type it when the script asks.

import getpass
import os
import time
import zipfile
from pathlib import Path

import requests

api_key = os.environ.get("IPUMS_API_KEY")
if api_key is None:
    # a masked prompt: what you type is not shown and not saved
    api_key = getpass.getpass("IPUMS API key: ")

URL = "https://api.ipums.org/extracts/"
PARAMS = {"collection": "nhgis", "version": "2"}
HEADERS = {"Authorization": api_key}
OUT_DIR = Path("data/raw/nhgis")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# 1. ask NHGIS for median household income (B19013) and population (B01003)
#    for every California tract, plus the 2024 tract boundaries
extract = {
    "datasets": {"2020_2024_ACS5a": {"dataTables": ["B19013", "B01003"], "geogLevels": ["tract"]}},
    "geographicExtents": ["060"],
    "shapefiles": ["us_tract_2024_tl2024"],
    "dataFormat": "csv_no_header",
    "breakdownAndDataTypeLayout": "single_file",
    "description": "CP101 SF 311 project",
}
response = requests.post(URL, params=PARAMS, headers=HEADERS, json=extract, timeout=120)
assert response.ok, f"request failed with code {response.status_code}: {response.text}"
number = response.json()["number"]
print("submitted extract", number)

# 2. wait until NHGIS has made the files (usually a few minutes)
while True:
    response = requests.get(URL + str(number), params=PARAMS, headers=HEADERS, timeout=120)
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
    zip_path = OUT_DIR / url.split("/")[-1]
    response = requests.get(url, headers=HEADERS, timeout=600)
    assert response.ok, f"download failed with code {response.status_code}"
    with open(zip_path, "wb") as f:
        f.write(response.content)
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(OUT_DIR)
    print("saved", zip_path)
