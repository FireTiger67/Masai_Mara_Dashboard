# ================================
# INSTALL REQUIRED PACKAGES
# ================================
!pip install -q streamlit-folium pygbif geopandas folium shapely pyproj

# ================================
# IMPORTS
# ================================
import pandas as pd
import geopandas as gpd
import folium
from pygbif import occurrences as occ
from shapely.geometry import Point

# ================================
# LOAD GBIF DATA (MASAI MARA)
# ================================
mara_wkt = (
    "POLYGON(("
    "34.7 -1.8, "
    "35.5 -1.8, "
    "35.5 -1.2, "
    "34.7 -1.2, "
    "34.7 -1.8"
    "))"
)

records = occ.search(
    geometry=mara_wkt,
    hasCoordinate=True,
    limit=2000
)

df = pd.DataFrame(records["results"])

df = df[[
    "species",
    "decimalLatitude",
    "decimalLongitude"
]].dropna()

gdf = gpd.GeoDataFrame(
    df,
    geometry=gpd.points_from_xy(
        df.decimalLongitude,
        df.decimalLatitude
    ),
    crs="EPSG:4326"
)

# ================================
# SELECT TWO MOST COMMON SPECIES (COLAB SAFE)
# ================================
top_species = gdf["species"].value_counts().head(2).index.tolist()
species_a, species_b = top_species

# ================================
# GRID-BASED CO-OCCURRENCE
# ================================
gdf_m = gdf.to_crs(epsg=32736)  # meters

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

# ================================
# FOLIUM MAP (REAL WORLD MAP)
# ================================
m = folium.Map(location=[-1.5, 35.1], zoom_start=10)

# Species A
for _, r in gdf[gdf["species"] == species_a].iterrows():
    folium.CircleMarker(
        [r.geometry.y, r.geometry.x],
        radius=3,
        color="blue",
        fill=True,
        fill_opacity=0.4,
    ).add_to(m)

# Species B
for _, r in gdf[gdf["species"] == species_b].iterrows():
    folium.CircleMarker(
        [r.geometry.y, r.geometry.x],
        radius=3,
        color="green",
        fill=True,
        fill_opacity=0.4,
    ).add_to(m)

# Co-occurrence zones
for _, r in co_gdf.iterrows():
    folium.CircleMarker(
        [r.geometry.y, r.geometry.x],
        radius=10,
        color="orange",
        fill=True,
        fill_opacity=0.8,
        popup=f"{species_a} + {species_b}"
    ).add_to(m)

m
