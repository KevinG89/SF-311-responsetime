# Run the whole project from start to finish. From the repo folder:
#
#   python -m src.main                 everything (downloads skip files already there)
#   python -m src.main --start clean   start at cleaning (raw data already downloaded)
#   python -m src.main --start join    start at the spatial join (cleaned data already there)
#   python -m src.main --start charts  only make the charts (joined data already there)
#
# The NHGIS download needs an IPUMS API key: run  export IPUMS_API_KEY="..."  first,
# or type it when it asks.

import argparse

import pandas as pd

from src.analysis import compute_metrics
from src.data import load_data, process_data
from src.utils import config
from src.utils.helpers import make_folders
from src.visualization import plot_results

STEPS = ["download", "clean", "join", "charts"]


def make_charts():
    """Chart tables, the 3 charts and their captions."""
    requests = load_data.load_requests_with_tracts()
    acs = load_data.load_acs()
    tracts = load_data.load_sf_tracts()
    print(f"{len(requests):,} requests with a tract, {len(tracts)} tracts, {len(acs)} ACS rows")

    groups = compute_metrics.income_quartiles(acs, set(tracts["GEOID"]))
    print(groups.groupby("income_group", observed=True)["income"].agg(["size", "min", "max"]))
    captions = {}

    # chart 1: number of requests of each type, 2020-2025 (all cleaned requests)
    by_type = compute_metrics.requests_by_type(load_data.load_clean_requests(["request_type"]))
    by_type.to_csv(config.TABLES / "chart1_requests_by_type.csv")
    captions["chart1_requests_by_type.png"] = plot_results.plot_requests_by_type(by_type)

    # chart 2: response time (days from request to closed), by income quartile
    response = compute_metrics.response_time_by_income(requests, groups)
    response.to_csv(config.TABLES / "chart2_response_time_by_income.csv")
    captions["chart2_response_time_by_income.png"] = plot_results.plot_response_time_by_income(response)

    # chart 3: total requests per year in each income quartile (counts, not per resident)
    by_year = compute_metrics.requests_by_year(requests, groups)
    by_year.to_csv(config.TABLES / "chart3_requests_by_year.csv")
    captions["chart3_requests_by_year.png"] = plot_results.plot_requests_by_year(by_year)

    text = "\n\n".join(f"**{name}**: {caption}" for name, caption in captions.items())
    (config.VISUALIZATIONS / "chart_captions.md").write_text(
        "# Chart captions\n\n" + text + "\n", encoding="utf-8")
    print(text)


def main():
    parser = argparse.ArgumentParser(description="SF 311 requests by census tract income")
    parser.add_argument("--start", choices=STEPS, default="download",
                        help="the step to start from (earlier steps' files must already exist)")
    args = parser.parse_args()
    todo = STEPS[STEPS.index(args.start):]
    make_folders()

    if "download" in todo:
        print("\n== 1. download ==")
        load_data.download_311()
        load_data.download_nhgis()
    if "clean" in todo:
        print("\n== 2. clean ==")
        process_data.clean_requests()
        process_data.clean_acs()
    if "join" in todo:
        print("\n== 3. spatial join ==")
        tracts = process_data.spatial_join()
        plot_results.plot_request_map(tracts)
    if "charts" in todo:
        print("\n== 4. charts ==")
        make_charts()


if __name__ == "__main__":
    pd.set_option("display.width", 120)
    main()
