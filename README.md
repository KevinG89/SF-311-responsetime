# SF 311 Response Times by Census Tract

CP101 (Introduction to Urban Data Analytics) final project, UC Berkeley, Fall 2026, Track B.
Team: Shangrui Guo (data), Junhao Luo (spatial analysis), Ryan Su (visualization).

**Research question:** Do 311 requests in San Francisco's lower-income census tracts take longer to close
than requests in higher-income tracts? And is the gap still there when we compare requests of the same type?

## How to run

1. Make the Python 3.12 environment:

   ```bash
   conda env create -f environment.yml
   conda activate sf311
   ```

   (Without conda: `pip install -r requirements.txt`.)

2. The NHGIS download needs an IPUMS API key (free at https://account.ipums.org/api_keys, and the
   account has to be registered for NHGIS). `02_download_nhgis.py` asks for the key when it starts,
   or you can set the `IPUMS_API_KEY` environment variable before running it.

3. Run the scripts from the repo root, in order:

   ```bash
   python scripts/01_download_311.py
   python scripts/02_download_nhgis.py
   python scripts/03_clean_data.py
   ```

   `01` downloads the 311 requests opened 2020–2025 (one file per month), `02` downloads ACS income
   and population for the census tracts plus the tract boundaries, and `03` cleans both. The cleaned data
   goes to `data/interim/` and the row counts for each cleaning step go to `logs/`.

## Progress

- [x] Download the data: `01_download_311.py`, `02_download_nhgis.py` (S)
- [x] Clean the data: `03_clean_data.py` (S, J, R)
- [ ] Spatial join, requests → tracts: `04_spatial_join.py` (S, J, R)
- [ ] Join income and make income quartiles: `05_attribute_join.py` (S, J, R)
- [ ] Analysis: `06_analyze.py` (S, J, R)
- [ ] Website: `docs/` (S, R)

## Folders

- `scripts/`: the scripts above, run in order
- `notebooks/`: exploration (start the file name with your initials)
- `data/raw/`, `data/interim/`, `data/processed/`: downloaded and cleaned data (too big for GitHub)
- `data/reference/`: our cleaning rules, `category_map.csv` and `status_rules.csv`
- `logs/`: how many rows each cleaning rule removed
- `outputs/`: figures and tables for the report
- `docs/`: GitHub Pages website

## Data

- **311 Cases** (`vw6y-z8j6`) from the [DataSF](https://data.sf.gov/d/vw6y-z8j6) API, public domain (PDDL).
  We use the requests opened 2020–2025, about 4.4 million.
- **ACS 2020–2024 5-year estimates** from the [IPUMS NHGIS](https://www.nhgis.org/) API (dataset
  `2020_2024_ACS5a`): B19013 median household income and B01003 total population for the 244 census
  tracts in San Francisco.
- **Census tract boundaries 2024** from IPUMS NHGIS (`us_tract_2024_tl2024`), for the spatial join.

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

## Notes

- Waiting time = days from `requested_datetime` (opened) to `closed_date`, in San Francisco time.
- The spatial work uses EPSG:2227 (California zone 3, feet).
- We only show results for whole tracts or bigger areas.

## Citation

- NHGIS: use the citation in the codebook that comes with the download (`data/raw/nhgis/`).
- DataSF, 311 Cases (`vw6y-z8j6`), https://data.sf.gov/d/vw6y-z8j6

## Use of AI tools

We used Claude (an AI assistant by Anthropic) to help write, debug and simplify the download and
cleaning scripts. We reviewed and tested all of the code.
