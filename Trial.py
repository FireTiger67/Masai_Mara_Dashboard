import streamlit as st
import pandas as pd
import geopandas as gpd
import folium
from streamlit_folium import st_folium
import os

st.set_page_config(layout="wide")
st.title("Masai Mara Wildlife Sensitivity Dashboard")

st.write("🚀 App started successfully")
st.write("📁 Files:", os.listdir())

df = pd.read_csv(
    "big_5_masai_mara.csv",  # fix name if needed
    sep="\t",
    low_memory=False
)

st.write("Rows loaded:", len(df))

df = df[[
    "species",
    "decimalLatitude",
    "decimalLongitude",
    "eventDate"
]].dropna()

df["eventDate"] = pd.to_datetime(df["eventDate"], errors="coerce")
df.dropna(subset=["eventDate"], inplace=True)

df["month"] = df["eventDate"].dt.month

def get_season(m):
    if m in [12, 1, 2]:
        return "Dry"
    elif m in [3, 4, 5]:
        return "Long Rains"
    elif m in [6, 7, 8]:
        return "Migration Peak"
    else:
        return "Short Rains"

df["season"] = df["month"].apply(get_season)

gdf = gpd.GeoDataFrame(
    df,
    geometry=gpd.points_from_xy(
        df.decimalLongitude,
        df.decimalLatitude
    ),
    crs="EPSG:4326"
)

season = st.sidebar.selectbox(
    "Season",
    ["Dry", "Long Rains", "Migration Peak", "Short Rains"]
)

filtered = gdf[gdf["season"] == season]

filtered["lat_bin"] = filtered.geometry.y.round(2)
filtered["lon_bin"] = filtered.geometry.x.round(2)

# species counts for selected season
species_counts = (
    filtered
    .groupby("species")
    .size()
    .reset_index(name="sightings")
    .sort_values("sightings", ascending=False)
)

st.subheader(f"Big Five Sightings in {season} Season")
st.dataframe(species_counts, use_container_width=True)

st.subheader("Species-wise Sightings")

st.bar_chart(
    species_counts.set_index("species")["sightings"]
)

cols = st.columns(len(species_counts))

for i, row in species_counts.iterrows():
    cols[i].metric(
        row["species"],
        int(row["sightings"])
    )


zones = (
    filtered
    .groupby(["lat_bin", "lon_bin"])
    .size()
    .reset_index(name="sightings")
)

m = folium.Map(location=[-1.4, 35.2], zoom_start=9)

for _, r in zones.iterrows():
    folium.CircleMarker(
        [r.lat_bin, r.lon_bin],
        radius=6,
        color="red",
        fill=True,
        fill_opacity=0.6
    ).add_to(m)

st_folium(m, width=1100, height=550)
