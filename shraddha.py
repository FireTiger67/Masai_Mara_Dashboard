import streamlit as st
import pandas as pd
import geopandas as gpd
import folium
from streamlit_folium import st_folium

# --------------------------------------------------
# PAGE CONFIG
# --------------------------------------------------
st.set_page_config(layout="wide")
st.title("Masai Mara Wildlife Co-occurrence Dashboard")

st.markdown("""
Interactive dashboard to explore **where multiple Big Five species are spotted together**
by **species**, **season**, and **year range**.
""")

# --------------------------------------------------
# LOAD DATA (CSV – CLOUD SAFE)
# --------------------------------------------------
@st.cache_data
def load_data():
    df = pd.read_csv(
        "big_5_masai_mara.csv",
        sep="\t",
        low_memory=False
    )

    df = df[[
        "species",
        "decimalLatitude",
        "decimalLongitude",
        "eventDate"
    ]].dropna()

    df["eventDate"] = pd.to_datetime(df["eventDate"], errors="coerce")
    df.dropna(subset=["eventDate"], inplace=True)

    df["year"] = df["eventDate"].dt.year
    df = df[(df["year"] >= 1990) & (df["year"] <= 2025)]

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

    return gdf

gdf = load_data()

# --------------------------------------------------
# SIDEBAR FILTERS
# --------------------------------------------------
st.sidebar.header("Filters")

selected_animals = st.sidebar.multiselect(
    "Select Animals",
    options=sorted(gdf["species"].unique()),
    default=sorted(gdf["species"].unique())
)

selected_season = st.sidebar.selectbox(
    "Select Season",
    options=["All"] + sorted(gdf["season"].unique())
)

year_range = st.sidebar.slider(
    "Year Range",
    int(gdf["year"].min()),
    int(gdf["year"].max()),
    (2000, 2025)
)

show_points = st.sidebar.checkbox("Show individual sightings", value=True)
show_cooccur = st.sidebar.checkbox("Show co-occurrence zones", value=True)

# --------------------------------------------------
# FILTER DATA
# --------------------------------------------------
filtered = gdf[
    (gdf["species"].isin(selected_animals)) &
    (gdf["year"] >= year_range[0]) &
    (gdf["year"] <= year_range[1])
]

if selected_season != "All":
    filtered = filtered[filtered["season"] == selected_season]

# --------------------------------------------------
# CO-OCCURRENCE ANALYSIS (GRID BASED)
# --------------------------------------------------
# Project to meters for grid calculation
filtered_m = filtered.to_crs(epsg=32736)  # UTM zone for Kenya

grid_size = 5000  # 5 km

filtered_m["gx"] = (filtered_m.geometry.x // grid_size).astype(int)
filtered_m["gy"] = (filtered_m.geometry.y // grid_size).astype(int)

# Count unique species per grid cell
cooccur_cells = (
    filtered_m
    .groupby(["gx", "gy"])["species"]
    .nunique()
    .reset_index(name="species_count")
)

# Keep only cells with co-occurrence
cooccur_cells = cooccur_cells[cooccur_cells["species_count"] >= 2]

# Convert back to lat/lon
cooccur_cells["x"] = cooccur_cells["gx"] * grid_size
cooccur_cells["y"] = cooccur_cells["gy"] * grid_size

cooccur_gdf = gpd.GeoDataFrame(
    cooccur_cells,
    geometry=gpd.points_from_xy(
        cooccur_cells.x,
        cooccur_cells.y
    ),
    crs="EPSG:32736"
).to_crs(epsg=4326)

# --------------------------------------------------
# MAP
# --------------------------------------------------
species_colors = {
    "Panthera leo": "red",
    "Loxodonta africana": "green",
    "Panthera pardus": "purple",
    "Syncerus caffer": "blue",
    "Diceros bicornis": "black"
}

m = folium.Map(location=[-1.4, 35.2], zoom_start=9)

# Individual sightings
if show_points:
    for _, row in filtered.iterrows():
        folium.CircleMarker(
            location=[row.geometry.y, row.geometry.x],
            radius=3,
            color=species_colors.get(row["species"], "gray"),
            fill=True,
            fill_opacity=0.4,
        ).add_to(m)

# Co-occurrence zones
if show_cooccur:
    for _, row in cooccur_gdf.iterrows():
        folium.CircleMarker(
            location=[row.geometry.y, row.geometry.x],
            radius=12,
            color="orange",
            fill=True,
            fill_opacity=0.7,
            popup=f"Co-occurrence zone<br>Species count: {row['species_count']}"
        ).add_to(m)

st_folium(m, width=1100, height=550)

# --------------------------------------------------
# SUMMARY
# --------------------------------------------------
st.subheader("Co-occurrence Summary")

st.write(
    f"Number of co-occurrence zones: **{len(cooccur_gdf)}**"
)

species_summary = (
    filtered
    .groupby("species")
    .size()
    .reset_index(name="sightings")
    .sort_values("sightings", ascending=False)
)

st.dataframe(species_summary, use_container_width=True)

# --------------------------------------------------
# FOOTNOTE
# --------------------------------------------------
st.markdown("""
**Note:**  
Co-occurrence indicates shared spatial presence within a grid cell and does not
imply direct interaction between species.
""")
