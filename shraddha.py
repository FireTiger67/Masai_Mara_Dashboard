"""
gbif_cooccurrence.py

Fetches GBIF occurrence data for Masai Mara
and computes spatial co-occurrence zones
"""

import pandas as pd
import geopandas as gpd
from pygbif import occurrences as occ

# ------------------------------------
# MASAI MARA BOUNDING POLYGON (WKT)
# ------------------------------------
mara_wkt = (
    "POLYGON(("
    "34.7 -1.8, "
    "35.5 -1.8, "
    "35.5 -1.2, "
    "34.7 -1.2, "
    "34.7 -1.8"
    "))"
)

# ------------------------------------
# FETCH GBIF DATA
# ------------------------------------
print("Fetching GBIF data...")

records = occ.search(
    geometry=mara_wkt,
    hasCoordinate=True,
    limit=2000
)

df = pd.DataFrame(records["results"])

df = df[[
    "species",
    "decimalLatitude",
    "decimalLongitude",
    "eventDate"
]].dropna()

print(f"Records fetched: {len(df)}")

# ------------------------------------
# SAVE RAW SIGHTINGS
# ------------------------------------
df.to_csv("masai_mara_occurrences.csv", index=False)

# ------------------------------------
# GEO DATAFRAME
# ------------------------------------
gdf = gpd.GeoDataFrame(
    df,
    geometry=gpd.points_from_xy(
        df.decimalLongitude,
        df.decimalLatitude
    ),
    crs="EPSG:4326"
)

# ------------------------------------
# SELECT TOP 2 SPECIES (DATA-DRIVEN)
# ------------------------------------
top_species = gdf["species"].value_counts().head(2).index.tolist()
species_a, species_b = top_species

print("Top species:")
print(species_a)
print(species_b)

# ------------------------------------
# GRID-BASED CO-OCCURRENCE
# ------------------------------------
gdf_m = gdf.to_crs(epsg=32736)  # meters (UTM zone)

grid_size = 5000  # 5 km

gdf_m["gx"] = (gdf_m.geometry.x // grid_size).astype(int)
gdf_m["gy"] = (gdf_m.geometry.y // grid_size).astype(int)

a_cells = gdf_m[gdf_m["species"] == species_a][["gx", "gy"]]
b_cells = gdf_m[gdf_m["species"] == species_b][["gx", "gy"]]

cooccur = pd.merge(a_cells, b_cells, on=["gx", "gy"]).drop_duplicates()

cooccur["x"] = cooccur["gx"] * grid_size
cooccur["y"] = cooccur["gy"] * grid_size

co_gdf = gpd.GeoDataFrame(
    cooccur,
    geometry=gpd.points_from_xy(cooccur.x, cooccur.y),
    crs="EPSG:32736"
).to_crs(epsg=4326)

# ------------------------------------
# SAVE CO-OCCURRENCE ZONES
# ------------------------------------
co_gdf[["gx", "gy", "geometry"]].to_csv(
    "cooccurrence_zones.csv",
    index=False
)

print("Co-occurrence zones saved.")
print("Done.")

