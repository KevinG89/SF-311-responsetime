# SF 311 Requests and Response Times by Census Tract

CP101 (Introduction to Urban Data Analytics) final project, UC Berkeley, Fall 2026, Track B.

**Team**

- Shangrui Guo: data download and cleaning
- Ryan Su: spatial join (requests → census tracts) and the request map
- Junhao Luo: income quartiles, midterm charts, code structure

**Research questions**

- **Midterm:** Do people in San Francisco's lower-income census tracts file more or fewer 311 requests per
  resident than people in higher-income tracts, and did that gap change from 2020 to 2025? Are their
  requests closed faster or slower (a first look at response time)?
- **Final (in progress):** Do 311 requests in lower-income tracts take longer to close than requests in
  higher-income tracts, also when we compare requests of the same type?

Note: 311 counts measure how often people *report* problems, not how many problems there are.

## How to run

All commands are run in a terminal **from the repo folder** (the folder with this README).

### 1. Get the code

```bash
git clone https://github.com/KevinG89/SF-311-responsetime.git
cd SF-311-responsetime
```

### 2. Make a Python 3.12 environment

We use [uv](https://docs.astral.sh/uv/), which installs Python 3.12 for this project even if your computer
has a different version (no admin password needed):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh    # install uv (once per computer)
source $HOME/.local/bin/env                        # let this terminal find uv
uv venv --python 3.12                              # make the .venv folder with Python 3.12
source .venv/bin/activate                          # use it (the prompt now starts with "(SF-311-responsetime)" or "(.venv)")
uv pip install -r requirements.txt                 # install the packages
python --version                                   # should print Python 3.12.x
```

Every time you open a new terminal, run `source .venv/bin/activate` again.

Other ways: if `python3.12 --version` already works, `python3.12 -m venv .venv` and
`pip install -r requirements.txt`; with conda, `conda env create -f environment.yml` and `conda activate sf311`.
On Windows, activate with `.venv\Scripts\activate`.

### 3. Get an IPUMS API key (for the census data)

1. Make a free account at https://account.ipums.org/api_keys and create a key.
2. Sign in at https://www.nhgis.org once and accept the NHGIS terms.
3. In the terminal (one line, then Enter; this lasts until you close the terminal):

   ```bash
   export IPUMS_API_KEY="your key"
   ```

   If you skip this, the program asks for the key when it needs it. Never put the key in a file in the repo.
   The DataSF (311) download needs no key.

### 4. Run everything

```bash
python -m src.main
```

This runs the four steps below in order. The first run takes about 20–30 minutes, mostly the downloads.
Keep the computer awake (on a Mac: plug it in, or run `caffeinate -i` in a second terminal).

**If it stops** (sleep, lost Wi-Fi, an error): run `python -m src.main` again. 311 months that are already
downloaded and NHGIS files that are already there are skipped.

**If a teammate gave you data files**, put them in the folder shown in the table below and start at a later step:

```bash
python -m src.main --start clean     # you have data/raw/ (the downloads)
python -m src.main --start join      # you have the cleaned files in data/processed/
python -m src.main --start charts    # you have the joined files in data/processed/
```

## Pipeline: which step is where

`src/main.py` calls these functions in order. To work on one step, open its file.

| Step | File | Functions | Reads | Writes |
|---|---|---|---|---|
| 1. Download | `src/data/load_data.py` | `download_311()`, `download_month()`, `download_nhgis()` | DataSF API, IPUMS NHGIS API | `data/raw/sf311/YYYY/YYYY-MM.parquet`, `data/raw/nhgis/` (ACS table + tract shapefile) |
| 2. Clean | `src/data/process_data.py` | `clean_requests()`, `clean_year()`, `removal_table()`, `clean_acs()` | `data/raw/`, `data/reference/*.csv` | `data/processed/requests_clean.parquet`, `requests_removed.parquet`, `acs_tracts_sf.parquet`, `logs/cleaning_log*.csv`, `logs/acs_cleaning_log.csv` |
| 3. Spatial join | `src/data/process_data.py`, `src/data/load_data.py`, `src/visualization/plot_results.py` | `spatial_join()`, `assign_tracts()`, `load_tracts()`, `plot_request_map()` | `requests_clean.parquet`, tract shapefile | `data/processed/requests_with_tracts.parquet`, `sf_tracts.parquet`, `requests_unassigned.parquet`, `logs/spatial_join_log.csv`, `outputs/tables/requests_by_tract.csv`, `visualizations/requests_by_tract.png` |
| 4. Analysis and charts | `src/analysis/compute_metrics.py`, `src/visualization/plot_results.py` | `income_quartiles()`, `rate_by_tract()`, `requests_by_type()`, `response_time_by_income()`, `requests_by_year()`, `plot_requests_by_type()`, `plot_response_time_by_income()`, `plot_requests_by_year()` | `requests_clean.parquet`, `requests_with_tracts.parquet`, `sf_tracts.parquet`, `acs_tracts_sf.parquet` | `visualizations/chart1–3_*.png`, `visualizations/chart_captions.md`, `outputs/tables/chart*.csv` |

Settings used by every step (file paths, years, the San Francisco bounding box, the income reliability cutoff,
the 500-resident minimum, chart colors) are in `src/utils/config.py`. Change them there, not in the step files.

## Progress

- [x] Download the data: `src/data/load_data.py` (S)
- [x] Clean the data: `src/data/process_data.py` (S)
- [x] Spatial join, requests → tracts: `src/data/process_data.py` (R)
- [x] Income quartiles, requests per resident and response time: `src/analysis/compute_metrics.py` (J)
- [x] Midterm charts: `src/visualization/plot_results.py` (J)
- [ ] Response time analysis (after the midterm)
- [ ] Website: `docs/` (S, R)

## Folders

- `src/main.py`: runs the whole project, step by step
- `src/data/load_data.py`: downloads the data and reads files
- `src/data/process_data.py`: cleaning and the spatial join
- `src/analysis/compute_metrics.py`: income quartiles, requests per resident and response time
- `src/visualization/plot_results.py`: the map and the charts
- `src/utils/config.py`: file paths and settings; `src/utils/helpers.py`: small helpers
- `notebooks/`: exploration (start the file name with your initials)
- `data/raw/`, `data/processed/`: downloaded and cleaned data (too big for GitHub, so not in the repo)
- `data/reference/`: our cleaning rules, `category_map.csv` and `status_rules.csv`
- `logs/`: how many rows each cleaning rule removed
- `visualizations/`: the map and charts (`chart_captions.md` has a caption for each chart)
- `outputs/tables/`: the numbers behind the map and charts
- `docs/`: GitHub Pages website

## Data

- **311 Cases** (`vw6y-z8j6`) from the [DataSF](https://data.sf.gov/d/vw6y-z8j6) API, public domain (PDDL).
  We use the requests opened 2020–2025, about 4.4 million. One row = one request.
- **ACS 2020–2024 5-year estimates** from the [IPUMS NHGIS](https://www.nhgis.org/) API (dataset
  `2020_2024_ACS5a`): B19013 median household income and B01003 total population for the 244 census
  tracts in San Francisco. One row = one tract.
- **Census tract boundaries 2024** from IPUMS NHGIS (`us_tract_2024_tl2024`), for the spatial join.
  One row = one tract polygon.

## Data cleaning

- In June 2024 the 311 system renamed a lot of categories (for example `Graffiti` became
  `Graffiti Public` and `Graffiti Private`, and abandoned vehicles moved under `Parking Enforcement`).
  `data/reference/category_map.csv` maps the old and new names to one request type and marks the
  10 types we study.
- We removed test records, other request types, requests closed as duplicates, transferred, administrative
  closures or not actionable (the patterns are in `data/reference/status_rules.csv`), impossible dates,
  and requests without coordinates (`(0, 0)` means "no location"). The counts are in `logs/cleaning_log.csv`.
- ACS: codes like `-666666666` became missing values, `250001` is the top code ("250,000+"), and income
  estimates with a coefficient of variation above 0.30 are marked as unreliable.
- Problem: in 2022 and 2023 a lot of phone requests have no coordinates, so phone requests are
  under-represented in those years (`logs/cleaning_log_by_channel.csv`).

## Analysis (midterm)

- Each request gets the census tract it falls in (spatial join, `gpd.sjoin`, in EPSG:2227).
- Tracts are split into four equal income groups (quartiles) by median household income. We only use tracts
  with a reliable income estimate and at least 500 residents.
- Chart 1: number of cleaned requests of each type, 2020-2025.
- Chart 2: response time = days from `requested_datetime` to `closed_date`. Each request gets the income group of
  its tract, and the chart shows the median request in each group (the mean is pulled up by a few requests that
  stay open for months).
- Chart 3: total number of requests per year in each income group (counts, not per resident).

## Notes

- Waiting time (for the final) = days from `requested_datetime` (opened) to `closed_date`, in San Francisco time.
- The spatial work uses EPSG:2227 (California zone 3, feet).
- We only show results for whole tracts or bigger areas.

## Citation

- NHGIS: use the citation in the codebook that comes with the download (`data/raw/nhgis/`).
- DataSF, 311 Cases (`vw6y-z8j6`), https://data.sf.gov/d/vw6y-z8j6
