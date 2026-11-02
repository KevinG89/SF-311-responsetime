# Settings used by the whole project: file paths and the numbers our analysis depends on.
# Every other file imports these, so a change here changes it everywhere.

from pathlib import Path

# ---------- folders ----------
ROOT = Path(__file__).resolve().parents[2]  # the repo folder (src/utils/config.py -> up 2)
RAW = ROOT / "data/raw"                     # downloads, never edited
SF311_RAW = RAW / "sf311"                   # one parquet file per month
NHGIS_RAW = RAW / "nhgis"                   # ACS table + tract shapefile
REFERENCE = ROOT / "data/reference"         # our cleaning rules (category_map, status_rules)
PROCESSED = ROOT / "data/processed"         # cleaned and joined data
LOGS = ROOT / "logs"                        # row counts for each cleaning step
VISUALIZATIONS = ROOT / "visualizations"    # charts and maps (.png)
TABLES = ROOT / "outputs/tables"            # tables behind the charts

# processed files
REQUESTS_CLEAN = PROCESSED / "requests_clean.parquet"
REQUESTS_REMOVED = PROCESSED / "requests_removed.parquet"
ACS_TRACTS = PROCESSED / "acs_tracts_sf.parquet"
REQUESTS_WITH_TRACTS = PROCESSED / "requests_with_tracts.parquet"
REQUESTS_UNASSIGNED = PROCESSED / "requests_unassigned.parquet"
SF_TRACTS = PROCESSED / "sf_tracts.parquet"

# ---------- 311 download (DataSF, no API key needed) ----------
SF311_URL = "https://data.sf.gov/resource/vw6y-z8j6.json"
PAGE_SIZE = 50000  # the most rows the API returns at once
SF311_FIELDS = ["service_request_id", "requested_datetime", "closed_date", "updated_datetime",
                "status_description", "status_notes", "agency_responsible", "service_name",
                "service_subtype", "service_details", "source", "supervisor_district",
                "analysis_neighborhood", "lat", "long"]
YEARS = range(2020, 2026)  # requests opened 2020-2025
N_YEARS = len(YEARS)

# ---------- ACS download (IPUMS NHGIS, needs an API key) ----------
NHGIS_URL = "https://api.ipums.org/extracts/"
NHGIS_DATASET = "2020_2024_ACS5a"
NHGIS_TABLES = ["B19013", "B01003"]  # median household income, total population
NHGIS_SHAPEFILE = "us_tract_2024_tl2024"
# NHGIS column codes (see the codebook that comes with the download)
NHGIS_COLUMNS = {"pop": "AUO6E001", "pop_moe": "AUO6M001",
                 "income": "AURUE001", "income_moe": "AURUM001"}

# ---------- cleaning ----------
MIN_LAT, MAX_LAT = 37.70, 37.84      # San Francisco bounding box
MIN_LON, MAX_LON = -122.52, -122.35
MAX_CV = 0.30                        # income estimates less precise than this are unreliable
TOP_CODE = 250001                    # ACS writes "250,000+" as 250001

# ---------- spatial ----------
CRS = "EPSG:2227"  # NAD83 / California zone 3, in feet

# ---------- charts ----------
MIN_POP = 500  # per-resident rates jump around in tracts with very few residents
QUARTILES = ["Q1 (lowest)", "Q2", "Q3", "Q4 (highest)"]
QUARTILE_COLORS = dict(zip(QUARTILES, ["#e08a3c", "#d9c2a7", "#8fb0d6", "#1f4e79"]))
SOURCE = ("Source: DataSF 311 Cases (opened 2020-2025, cleaned); "
          "ACS 2020-2024 5-year estimates (IPUMS NHGIS).")
