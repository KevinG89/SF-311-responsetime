# Functions for the analysis: income quartiles, 311 requests per resident and response time.

import pandas as pd

from src.utils import config


def income_quartiles(acs, tract_ids):
    """Split tracts into four equal groups by median household income.

    Uses only tracts that are in the boundary file, have at least MIN_POP residents and a
    reliable income estimate. Quartiles are ranks, so the 250,001 top code just lands in Q4.
    """
    usable = (acs["GEOID"].isin(tract_ids) & acs["income_reliable"]
              & (acs["pop"] >= config.MIN_POP))
    groups = acs.loc[usable, ["GEOID", "income", "pop"]].copy()
    groups["income_group"] = pd.qcut(groups["income"], 4, labels=config.QUARTILES)
    return groups


def rate_by_tract(requests, tracts):
    """Requests per resident per year for each tract in `tracts` (needs GEOID and pop columns).

    Tracts with no requests get 0.
    """
    counts = requests["GEOID"].value_counts()
    tracts = tracts.copy()
    tracts["requests"] = tracts["GEOID"].map(counts).fillna(0)
    tracts["rate"] = tracts["requests"] / config.N_YEARS / tracts["pop"]
    return tracts


def requests_by_type(requests):
    """Number of cleaned requests of each type, 2020-2025 (largest first)."""
    counts = requests["request_type"].value_counts().rename("requests").to_frame()
    counts["pct"] = 100 * counts["requests"] / counts["requests"].sum()
    return counts


def response_time_by_income(requests, groups):
    """Median and mean days from request to closed, for the requests in each income quartile.

    Each request gets the income group of its tract (merge on GEOID). Requests still open at the
    download have no closing time, so the medians use closed requests; the share still open is shown too.
    """
    merged = requests.merge(groups[["GEOID", "income_group"]], on="GEOID", how="inner")
    by_group = merged.groupby("income_group", observed=True)
    table = pd.DataFrame({
        "requests": by_group.size(),
        "median_days": by_group["days_to_close"].median(),
        "mean_days": by_group["days_to_close"].mean(),
        "pct_still_open": 100 * by_group["is_open"].mean(),
    })
    return table.reindex(config.QUARTILES)


def requests_by_year(requests, groups):
    """Total number of requests in each income quartile, for every year (not per resident).

    Rows: years. Columns: the four income quartiles.
    """
    merged = requests.merge(groups[["GEOID", "income_group"]], on="GEOID", how="inner")
    table = pd.crosstab(merged["year"], merged["income_group"])
    return table[config.QUARTILES]
