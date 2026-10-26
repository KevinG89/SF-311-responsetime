# Clean the 311 requests and the ACS tract data.
# Run from the repo root after the two download scripts: python scripts/03_clean_data.py
# Writes the cleaned data to data/interim/ and the row counts to logs/.

from pathlib import Path

import numpy as np
import pandas as pd

YEARS = range(2020, 2026)
MIN_LAT, MAX_LAT = 37.70, 37.84
MIN_LON, MAX_LON = -122.52, -122.35
MAX_CV = 0.30

# "Mobile/Open311" was renamed "Mobile" in June 2024; small channels become "Other"
CHANNELS = {
    "Phone": "Phone",
    "Web": "Web",
    "Mobile/Open311": "Mobile",
    "Mobile": "Mobile",
    "Integrated Agency": "Integrated Agency",
}

# our cleaning rules, in the order we apply them
RULES = {
    "repeated_id": "The same service_request_id appears again (first copy kept)",
    "test_record": "Test records (source = 'Test')",
    "out_of_scope_type": "Not one of the in-scope request types (category_map.csv)",
    "closed_duplicate": "Closure note says: duplicate (status_rules.csv)",
    "closed_transferred": "Closure note says: transferred (status_rules.csv)",
    "closed_administrative": "Closure note says: administrative (status_rules.csv)",
    "closed_not_actionable": "Closure note says: not actionable (status_rules.csv)",
    "bad_dates": "Closed before it was opened, after the download, or 'Closed' with no date",
    "missing_location": "No coordinates, or the (0, 0) placeholder",
    "outside_san_francisco": "Coordinates outside the San Francisco bounding box",
}

OUTPUT_COLUMNS = [
    "service_request_id", "request_type", "opened", "closed", "year", "is_open",
    "days_to_close", "days_open_at_snapshot", "closed_date_only", "channel", "lat", "lon",
    "closure_note_category", "service_name", "service_subtype", "service_details", "source",
    "agency_responsible", "status_notes", "supervisor_district", "analysis_neighborhood",
]


# ---------- 311 requests ----------

category_map = pd.read_csv("data/reference/category_map.csv")
status_rules = pd.read_csv("data/reference/status_rules.csv")

# rows with a subtype match on name + subtype, rows with "*" match any subtype of that name
by_subtype = category_map.loc[category_map["service_subtype"] != "*",
                              ["service_name", "service_subtype", "request_type"]]
by_name = category_map.loc[category_map["service_subtype"] == "*", ["service_name", "request_type"]]
by_name = by_name.rename(columns={"request_type": "type_by_name"})
in_scope_types = category_map.loc[category_map["in_scope"], "request_type"].unique()

# time of the download, in San Francisco time like the 311 timestamps
manifest = pd.read_csv("data/raw/sf311/_manifest.csv")
snapshot = pd.to_datetime(manifest["downloaded_at_utc"], utc=True).max()
snapshot = snapshot.tz_convert("America/Los_Angeles").tz_localize(None)


def clean_year(df):
    """Clean one year of raw 311 requests and label the rule each removed request breaks."""
    # 1. fix the column types
    for col in ["service_name", "service_subtype", "service_details", "source",
                "status_notes", "status_description", "agency_responsible"]:
        df[col] = df[col].str.strip()

    df["opened"] = pd.to_datetime(df["requested_datetime"], format="ISO8601", errors="coerce")
    df["closed"] = pd.to_datetime(df["closed_date"], format="ISO8601", errors="coerce")
    # errors="coerce" turns a date it cannot read into NaT, so check that none failed
    assert df["opened"].notna().all()
    parse_failed = df["closed_date"].notna() & df["closed"].isna()
    assert parse_failed.sum() == 0

    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lon"] = pd.to_numeric(df["long"], errors="coerce")
    # (0, 0) is a placeholder for "no location" and isna() does not catch it
    no_location = (df["lat"] == 0) | (df["lon"] == 0)
    df.loc[no_location, "lat"] = np.nan
    df.loc[no_location, "lon"] = np.nan

    df["year"] = df["opened"].dt.year
    df["is_open"] = df["closed"].isna()
    df["days_to_close"] = (df["closed"] - df["opened"]).dt.total_seconds() / 86400
    df["days_open_at_snapshot"] = (snapshot - df["opened"]).dt.total_seconds() / 86400
    df.loc[~df["is_open"], "days_open_at_snapshot"] = np.nan
    df["closed_date_only"] = df["closed"] == df["closed"].dt.normalize()
    df["channel"] = df["source"].map(CHANNELS).fillna("Other")

    # 2. request type from category_map.csv
    n = len(df)
    df = df.merge(by_subtype, on=["service_name", "service_subtype"], how="left",
                  validate="many_to_one")
    df = df.merge(by_name, on="service_name", how="left", validate="many_to_one")
    assert len(df) == n
    df["request_type"] = df["request_type"].fillna(df["type_by_name"])
    assert df["request_type"].notna().all(), "a category is missing from category_map.csv"
    df["in_scope"] = df["request_type"].isin(in_scope_types)

    # 3. label the closure notes with status_rules.csv (the first rule that matches wins)
    notes = df["status_notes"].fillna("").str.lower().str.replace("_", " ", regex=False)
    notes = notes.str.split().str.join(" ")  # split and rejoin, so repeated spaces become one
    df["closure_note_category"] = None
    for reason, pattern, unless in zip(status_rules["reason"], status_rules["pattern"],
                                       status_rules["unless"]):
        match = df["closure_note_category"].isna() & notes.str.contains(pattern)
        if pd.notna(unless):
            match = match & ~notes.str.contains(unless)
        df.loc[match, "closure_note_category"] = reason

    # 4. which rules does each request break?
    note = df["closure_note_category"]
    bad_dates = ((df["closed"] < df["opened"]) | (df["closed"] > snapshot)
                 | ((df["status_description"] == "Closed") & df["closed"].isna()))
    inside_sf = df["lat"].between(MIN_LAT, MAX_LAT) & df["lon"].between(MIN_LON, MAX_LON)
    breaks = {
        "repeated_id": df["service_request_id"].duplicated(),
        "test_record": df["source"] == "Test",
        "out_of_scope_type": ~df["in_scope"],
        "closed_duplicate": note == "duplicate",
        "closed_transferred": note == "transferred",
        "closed_administrative": note == "administrative",
        "closed_not_actionable": note == "not_actionable",
        "bad_dates": bad_dates,
        "missing_location": df["lat"].isna() | df["lon"].isna(),
        "outside_san_francisco": ~inside_sf,
    }
    # a removed request gets the first rule it breaks; kept requests stay empty
    df["removed_reason"] = None
    for rule in RULES:
        df.loc[df["removed_reason"].isna() & breaks[rule], "removed_reason"] = rule
    return df


def removal_table(rows, column):
    """How many rows each rule removed, for every value of column (year, type or channel)."""
    table = pd.crosstab(rows[column], rows["removed_reason"])
    table = table.reindex(columns=list(RULES) + ["kept"], fill_value=0)
    table["raw"] = table.sum(axis=1)
    table["pct_kept"] = (100 * table["kept"] / table["raw"]).round(1)
    return table[["raw"] + list(RULES) + ["kept", "pct_kept"]]


clean_parts = []
removed_parts = []
n_raw = 0
for year in YEARS:
    df = pd.read_parquet(f"data/raw/sf311/{year}")
    n_raw += len(df)
    df = clean_year(df)
    kept = df["removed_reason"].isna()
    clean_parts.append(df.loc[kept, OUTPUT_COLUMNS])
    removed_parts.append(df.loc[~kept, OUTPUT_COLUMNS + ["removed_reason"]])
    print(year, ":", len(df), "raw ->", kept.sum(), "clean")

clean = pd.concat(clean_parts, ignore_index=True)
removed = pd.concat(removed_parts, ignore_index=True)

assert len(clean) + len(removed) == n_raw
assert clean["service_request_id"].is_unique
assert (clean["days_to_close"].dropna() >= 0).all()
assert (clean["is_open"] == clean["closed"].isna()).all()
assert clean["lat"].between(MIN_LAT, MAX_LAT).all()
assert clean["lon"].between(MIN_LON, MAX_LON).all()

clean.to_parquet("data/interim/requests_clean.parquet", index=False)
removed.to_parquet("data/interim/requests_removed.parquet", index=False)

# how many rows each rule removed
counts = removed["removed_reason"].value_counts()
log = pd.DataFrame({
    "rule": ["raw_rows"] + list(RULES.keys()),
    "description": ["Requests in the raw download"] + list(RULES.values()),
})
log["removed"] = log["rule"].map(counts).fillna(0).astype(int)
# rows left after each rule
remaining = []
left = n_raw
for n in log["removed"]:
    left = left - n
    remaining.append(left)
log["remaining"] = remaining
log["pct_of_raw_removed"] = (100 * log["removed"] / n_raw).round(2)
log.to_csv("logs/cleaning_log.csv", index=False)
print(log)

# the same counts by year, request type and channel ("kept" = passed every rule)
kept_rows = clean[["year", "request_type", "channel"]].copy()
kept_rows["removed_reason"] = "kept"
everything = pd.concat([kept_rows, removed[["year", "request_type", "channel", "removed_reason"]]],
                       ignore_index=True)
out_of_scope = ~everything["request_type"].isin(in_scope_types)
everything.loc[out_of_scope, "request_type"] = "(out-of-scope types)"
removal_table(everything, "year").to_csv("logs/cleaning_log_by_year.csv")
removal_table(everything, "request_type").to_csv("logs/cleaning_log_by_type.csv")
removal_table(everything, "channel").to_csv("logs/cleaning_log_by_channel.csv")


# ---------- ACS tracts ----------

# codes the Census writes instead of a number when there is no estimate
ANNOTATION_CODES = {
    -666666666: "estimate could not be computed (too few sample observations)",
    -999999999: "not displayed (too few sample cases)",
    -888888888: "not applicable or not available",
    -555555555: "estimate is controlled (no margin of error)",
    -333333333: "median is in an open-ended interval (no margin of error)",
    -222222222: "margin of error could not be computed",
}
TOP_CODE = 250001  # published as "250,000+"

# the tract table from the NHGIS download (if there are several, use the last one)
csv_path = sorted(Path("data/raw/nhgis").glob("**/*_tract.csv"))[-1]
# every column as text, so codes like "06" and "075" keep their leading zeros
raw = pd.read_csv(csv_path, dtype=str)
sf = raw.loc[(raw["STATEA"] == "06") & (raw["COUNTYA"] == "075")]
log = {"tracts_in_file": len(raw), "tracts_in_county_06075": len(sf)}

tracts = pd.DataFrame({"GEOID": sf["TL_GEO_ID"], "GISJOIN": sf["GISJOIN"],
                       "TRACTA": sf["TRACTA"], "NAME": sf["NAME_E"]})
# NHGIS column codes, see the codebook
nhgis_columns = {"pop": "AUO6E001", "pop_moe": "AUO6M001",
                 "income": "AURUE001", "income_moe": "AURUM001"}
for name, code in nhgis_columns.items():
    tracts[name] = pd.to_numeric(sf[code], errors="coerce")
    assert tracts[name].notna().sum() == sf[code].notna().sum()

tracts["income_topcoded"] = tracts["income"] == TOP_CODE
tracts["income_note"] = tracts["income"].map(ANNOTATION_CODES)
tracts["income_note"] = tracts["income_note"].fillna(tracts["income_moe"].map(ANNOTATION_CODES))
tracts.loc[tracts["income_topcoded"], "income_note"] = "top-coded: 250,000+ (no margin of error)"

# codes become NaN: not 0 (that would make up an income) and we keep the row
for col in ["pop", "pop_moe", "income", "income_moe"]:
    log[col + "_annotation_codes_to_nan"] = tracts[col].isin(ANNOTATION_CODES.keys()).sum()
    tracts[col] = tracts[col].replace(list(ANNOTATION_CODES.keys()), np.nan)

tracts["zero_population"] = tracts["pop"] == 0
tracts["income_cv"] = tracts["income_moe"] / 1.645 / tracts["income"]
# top-coded tracts have no margin of error, but they are clearly high income
tracts["income_reliable"] = tracts["income"].notna() & (
    (tracts["income_cv"] <= MAX_CV) | tracts["income_topcoded"])

log["zero_population_tracts"] = tracts["zero_population"].sum()
log["income_missing"] = tracts["income"].isna().sum()
log["income_topcoded_250001"] = tracts["income_topcoded"].sum()
log["income_cv_above_0.30"] = (tracts["income_cv"] > MAX_CV).sum()
log["income_reliable_tracts"] = tracts["income_reliable"].sum()

assert tracts["GEOID"].is_unique and tracts["GISJOIN"].is_unique
assert tracts["GEOID"].str.startswith("06075").all()
assert tracts["income"].dropna().between(0, TOP_CODE).all()

tracts.to_parquet("data/interim/acs_tracts_sf.parquet", index=False)
log = pd.DataFrame({"check": list(log.keys()), "count": list(log.values())})
log.to_csv("logs/acs_cleaning_log.csv", index=False)
print(log)
print(len(tracts), "tracts saved")
