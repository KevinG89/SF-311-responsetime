# Functions that make the map and the charts. Each one saves a .png to visualizations/
# and returns a one-sentence caption for the report.

import geopandas as gpd
import matplotlib.pyplot as plt

from src.utils import config
from src.utils.helpers import save_figure

plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})


def plot_request_map(tracts):
    """Map of cleaned requests per tract: a check that the spatial join worked."""
    ax = tracts.plot(column="request_count", cmap="YlOrRd", edgecolor="grey",
                     linewidth=0.3, legend=True, figsize=(10, 10),
                     legend_kwds={"label": "Assigned requests (count)"})
    ax.set_title("SF 311 requests by census tract, 2020–2025\n"
                 "Spatial join check — counts, not response times")
    # Focus the display on the study area; retain all tracts in the saved data.
    view = gpd.GeoSeries(gpd.points_from_xy([-122.52, -122.35], [37.70, 37.84]),
                         crs="EPSG:4326").to_crs(config.CRS).total_bounds
    ax.set_xlim(view[0] - 1000, view[2] + 1000)
    ax.set_ylim(view[1] - 1000, view[3] + 1000)
    ax.set_axis_off()
    save_figure(ax.figure, "requests_by_tract.png", source=None)
    return "Number of cleaned 311 requests assigned to each census tract, 2020-2025."


def plot_requests_by_type(table):
    """Chart 1: horizontal bar chart of the number of requests of each type, 2020-2025."""
    table = table.sort_values("requests")  # largest bar on top
    fig, ax = plt.subplots(figsize=(8, 4.5))
    bars = ax.barh(table.index, table["requests"] / 1000, color="#1f4e79")
    labels = [f"{n:,} ({p:.1f}%)" for n, p in zip(table["requests"], table["pct"])]
    ax.bar_label(bars, labels=labels, padding=3, fontsize=8)
    ax.set_xlim(0, table["requests"].max() / 1000 * 1.3)
    ax.set_xlabel("311 requests, 2020-2025 (thousands)")
    ax.set_title("Cleaned 311 requests by type, San Francisco 2020-2025", loc="left")
    save_figure(fig, "chart1_requests_by_type.png",
                source="Source: DataSF 311 Cases (opened 2020-2025, cleaned).")

    top = table.index[-1]
    second = table.index[-2]
    return (f"{top} makes up {table.loc[top, 'pct']:.0f}% of the {table['requests'].sum():,} cleaned "
            f"requests from 2020 to 2025, followed by {second} ({table.loc[second, 'pct']:.0f}%).")


def plot_response_time_by_income(table):
    """Chart 2: bar chart of the median days to close a request in each income quartile."""
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    colors = [config.QUARTILE_COLORS[q] for q in table.index]
    bars = ax.bar(table.index, table["median_days"], color=colors)
    # label each bar in days and hours, e.g. "0.76 days (18 h)"
    labels = [f"{d:.2f} days ({d * 24:.0f} h)" for d in table["median_days"]]
    ax.bar_label(bars, labels=labels, padding=3)
    ax.set_ylim(0, table["median_days"].max() * 1.2)
    ax.set_xlabel("Tract median household income quartile")
    ax.set_ylabel("Days from request to closed\n(median request)")
    ax.set_title("311 response time by tract income, San Francisco 2020-2025", loc="left")
    save_figure(fig, "chart2_response_time_by_income.png")

    low = table.loc[config.QUARTILES[0]]
    high = table.loc[config.QUARTILES[3]]
    return (f"The median request in the lowest-income tracts was closed in {low['median_days'] * 24:.0f} "
            f"hours, compared with {high['median_days'] * 24:.0f} hours in the highest-income tracts "
            f"(means are much longer, {low['mean_days']:.1f} and {high['mean_days']:.1f} days, because a "
            f"few requests stay open for months).")


def plot_requests_by_year(table):
    """Chart 3: total requests per year in each income quartile, one line per quartile."""
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    for q in config.QUARTILES:
        ax.plot(table.index, table[q] / 1000, marker="o", lw=2, color=config.QUARTILE_COLORS[q], label=q)
    ax.set_xticks(table.index)
    ax.set_ylim(0, table.max().max() / 1000 * 1.12)
    ax.set_xlabel("Year request was opened")
    ax.set_ylabel("311 requests (thousands)")
    ax.legend(title="Income quartile", frameon=False, bbox_to_anchor=(1.0, 1.0), loc="upper left")
    ax.set_title("Total 311 requests per year by tract income quartile", loc="left")
    save_figure(fig, "chart3_requests_by_year.png")

    totals = table.sum()
    first, last = table.index[0], table.index[-1]
    parts = ", ".join(f"{q} {totals[q]:,}" for q in config.QUARTILES)
    return (f"Total requests {first}-{last} by income quartile: {parts}. Requests in the lowest-income "
            f"quartile grew from {table.loc[first, config.QUARTILES[0]]:,} in {first} to "
            f"{table.loc[last, config.QUARTILES[0]]:,} in {last}.")
