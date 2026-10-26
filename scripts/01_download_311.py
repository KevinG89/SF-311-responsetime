# Download the SF 311 cases opened in 2020-2025 from DataSF, one month at a time.
# Run from the repo root: python scripts/01_download_311.py
# Each month is saved as data/raw/sf311/YYYY/YYYY-MM.parquet. Months that are already
# saved are skipped, so if the script stops you can just run it again.

import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

URL = "https://data.sf.gov/resource/vw6y-z8j6.json"
PAGE_SIZE = 50000
FIELDS = ["service_request_id", "requested_datetime", "closed_date", "updated_datetime",
          "status_description", "status_notes", "agency_responsible", "service_name",
          "service_subtype", "service_details", "source", "supervisor_district",
          "analysis_neighborhood", "lat", "long"]
MANIFEST = "data/raw/sf311/_manifest.csv"


def download_month(start, end):
    """Download every request opened from start up to (not including) end."""
    where = f"requested_datetime >= '{start}T00:00:00' AND requested_datetime < '{end}T00:00:00'"

    # how many rows the API has for this month, to check the download
    response = requests.get(URL, params={"$select": "count(*) AS n", "$where": where}, timeout=300)
    assert response.ok, f"request failed with code {response.status_code}"
    expected = int(response.json()[0]["n"])

    # the API gives at most PAGE_SIZE rows at a time, so we ask page by page
    pages = []
    offset = 0
    while True:
        params = {"$select": ",".join(FIELDS), "$where": where, "$order": "service_request_id",
                  "$limit": PAGE_SIZE, "$offset": offset}
        response = requests.get(URL, params=params, timeout=300)
        assert response.ok, f"request failed with code {response.status_code}"
        payload = response.json()
        pages.append(pd.DataFrame(payload, columns=FIELDS))
        if len(payload) < PAGE_SIZE:
            break
        offset += PAGE_SIZE

    df = pd.concat(pages, ignore_index=True)
    # keep every column as text; missing values stay missing
    df = df.astype(str)
    return df, expected


for year in range(2020, 2026):
    Path(f"data/raw/sf311/{year}").mkdir(parents=True, exist_ok=True)
    for month in range(1, 13):
        label = f"{year}-{month:02d}"
        path = f"data/raw/sf311/{year}/{label}.parquet"
        if os.path.exists(path):
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

        # save when each month was downloaded (03_clean_data.py uses this time)
        if os.path.exists(MANIFEST):
            manifest = pd.read_csv(MANIFEST)
        else:
            manifest = pd.DataFrame()
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        row = pd.DataFrame([{"month": label, "rows": len(df), "expected_rows": expected,
                             "downloaded_at_utc": now}])
        manifest = pd.concat([manifest, row], ignore_index=True)
        manifest.to_csv(MANIFEST, index=False)
        print(label, ":", len(df), "rows")
