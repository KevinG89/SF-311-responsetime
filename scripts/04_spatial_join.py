"""Assign cleaned requests to 2024 SF census tracts and map request counts.

Run from the repository root:
    python scripts/04_spatial_join.py
    python scripts/04_spatial_join.py --tracts path/to/tract_boundaries.shp

Requires the cleaned requests and extracted NHGIS boundary files. No income
join is performed here; that belongs in step 05. Shared-boundary or overlapping
matches remain unassigned for review rather than being counted twice.
"""

import argparse
from pathlib import Path

import geopandas as gpd
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CRS = "EPSG:2227"


def load_tracts(path):
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
    return tracts.to_crs(CRS).reset_index(drop=True)


def assign_tracts(requests, tracts):
    required = {"service_request_id", "lat", "lon"}
    if not required.issubset(requests.columns):
        raise ValueError(f"Missing request columns: {required - set(requests.columns)}")
    if requests["service_request_id"].isna().any() or not requests["service_request_id"].is_unique:
        raise ValueError("Request IDs must be nonmissing and unique.")
    result = requests.reset_index(drop=True).copy()
    lat = pd.to_numeric(result["lat"], errors="coerce")
    lon = pd.to_numeric(result["lon"], errors="coerce")
    valid = lat.between(-90, 90) & lon.between(-180, 180) & lat.ne(0) & lon.ne(0)
    result["GEOID"] = pd.Series(pd.NA, index=result.index, dtype="string")
    result["spatial_join_status"] = "invalid_coordinates"
    result.loc[valid, "spatial_join_status"] = "unmatched"

    # Only carry geometry through the join, avoiding duplication of wide text columns.
    points = gpd.GeoDataFrame(index=result.index[valid], geometry=gpd.points_from_xy(
        lon[valid], lat[valid], crs="EPSG:4326")).to_crs(CRS)
    matches = gpd.sjoin(points, tracts[["GEOID", "geometry"]], how="inner", predicate="within")
    counts = matches.groupby(level=0).size()
    unique = matches.loc[matches.index.isin(counts[counts == 1].index)]
    result.loc[unique.index, "GEOID"] = unique["GEOID"]
    result.loc[unique.index, "spatial_join_status"] = "within"
    result.loc[counts[counts > 1].index, "spatial_join_status"] = "ambiguous"

    # Strict 'within' excludes polygon edges. Retry only points with no interior match.
    remaining = points.loc[~points.index.isin(matches.index)]
    edges = gpd.sjoin(remaining, tracts[["GEOID", "geometry"]], how="inner", predicate="intersects")
    counts = edges.groupby(level=0).size()
    unique = edges.loc[edges.index.isin(counts[counts == 1].index)]
    result.loc[unique.index, "GEOID"] = unique["GEOID"]
    result.loc[unique.index, "spatial_join_status"] = "boundary_single"
    result.loc[counts[counts > 1].index, "spatial_join_status"] = "ambiguous"
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tracts", type=Path, help="Extracted 2024 NHGIS tract .shp path")
    args = parser.parse_args()
    request_path = ROOT / "data/interim/requests_clean.parquet"
    if not request_path.exists():
        parser.error(f"Missing {request_path}. Get the cleaned file from your teammate or run steps 01–03.")
    boundary_path = args.tracts
    if boundary_path is None:
        candidates = sorted((ROOT / "data/raw/nhgis").rglob("*.shp"))
        if len(candidates) != 1:
            parser.error("Expected one extracted tract shapefile in data/raw/nhgis. Use --tracts to select it.")
        boundary_path = candidates[0]
    if not boundary_path.is_file():
        parser.error(f"Boundary file not found: {boundary_path}")

    tracts = load_tracts(boundary_path)
    joined = assign_tracts(pd.read_parquet(request_path), tracts)
    counts = joined["GEOID"].value_counts()
    tracts["request_count"] = tracts["GEOID"].map(counts).fillna(0).astype(int)
    assert tracts["request_count"].sum() == joined["GEOID"].notna().sum()

    for folder in ["data/interim", "logs", "outputs/figures", "outputs/tables"]:
        (ROOT / folder).mkdir(parents=True, exist_ok=True)
    joined.to_parquet(ROOT / "data/interim/requests_with_tracts.parquet", index=False)
    tracts.to_parquet(ROOT / "data/interim/sf_tracts.parquet", index=False)
    summary = joined["spatial_join_status"].value_counts().rename_axis("status").reset_index(name="requests")
    summary.to_csv(ROOT / "logs/spatial_join_log.csv", index=False)
    joined.loc[joined["GEOID"].isna()].to_parquet(
        ROOT / "data/interim/requests_unassigned.parquet", index=False)
    tracts[["GEOID", "request_count"]].to_csv(ROOT / "outputs/tables/requests_by_tract.csv", index=False)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ax = tracts.plot(column="request_count", cmap="YlOrRd", edgecolor="grey",
                     linewidth=0.3, legend=True, figsize=(10, 10),
                     legend_kwds={"label": "Assigned requests (count)"})
    ax.set_title("SF 311 requests by census tract, 2020–2025\nSpatial join check — counts, not response times")
    # Focus the display on the study area; retain all tracts in the saved data.
    view = gpd.GeoSeries(gpd.points_from_xy([-122.52, -122.35], [37.70, 37.84]),
                         crs="EPSG:4326").to_crs(CRS).total_bounds
    ax.set_xlim(view[0] - 1000, view[2] + 1000)
    ax.set_ylim(view[1] - 1000, view[3] + 1000)
    ax.set_axis_off()
    ax.figure.savefig(ROOT / "outputs/figures/requests_by_tract.png", dpi=200, bbox_inches="tight")
    plt.close(ax.figure)
    print(summary.to_string(index=False))
    print(f"Saved {len(joined):,} requests and {len(tracts)} tracts. Review unassigned requests before analysis.")


if __name__ == "__main__":
    main()
