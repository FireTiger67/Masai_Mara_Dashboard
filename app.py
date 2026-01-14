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
Interactive geospatial dashboard to explore **Big Five wildlife sightings**
in the Masai Mara by **species**, **season**, and **year range**, with a focus
on **shared habitat use (co-occurrence)**.
""")

# --------------------------------------------------
# SPECIES NAME MAPPING (Scientific → Common)
# --------------------------------------------------
SPECIES_NAME_MAP = {
    "Panthera leo": "Lion",
    "Loxodonta africana": "African Elephant",
    "Panthera pardus": "Leopard",
    "Syncerus caffer": "African Buffalo",
    "Diceros bicornis": "Black Rhinoceros"
}

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

    df["common_name"] = df["species"].map(SPECIES_NAME_MAP)

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

selected_common = st.sidebar.multiselect(
    "Select Animal(s)",
    options=sorted(gdf["common_name"].unique()),
    default=sorted(gdf["common_name"].unique())
)

selected_species = [
    sci for sci, com in SPECIES_NAME_MAP.items()
    if com in selected_common
]

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
show_counts = st.sidebar.checkbox("Show counts on map", value=True)

# --------------------------------------------------
# FILTER DATA
# --------------------------------------------------
filtered = gdf[
    (gdf["species"].isin(selected_species)) &
    (gdf["year"] >= year_range[0]) &
    (gdf["year"] <= year_range[1])
]

if selected_season != "All":
    filtered = filtered[filtered["season"] == selected_season]

# --------------------------------------------------
# MOST FREQUENT SEASON PER SPECIES (CARDS)
# --------------------------------------------------
st.subheader("Most Frequently Observed Season per Species")

season_counts = (
    filtered
    .groupby(["common_name", "season"])
    .size()
    .reset_index(name="count")
)

top_seasons = (
    season_counts
    .sort_values(["common_name", "count"], ascending=[True, False])
    .groupby("common_name")
    .first()
    .reset_index()
)

if not top_seasons.empty:
    cols = st.columns(len(top_seasons))
    for i, row in top_seasons.iterrows():
        cols[i].metric(
            label=row["common_name"],
            value=row["season"]
        )
else:
    st.info("No seasonal data available for the selected filters.")

st.caption(
    "Cards show the season in which each selected species is most frequently observed."
)

# --------------------------------------------------
# GRID-BASED CO-OCCURRENCE (GENERAL)
# --------------------------------------------------
filtered_m = filtered.to_crs(epsg=32736)  # meters (UTM)
grid_size = 5000  # 5 km

filtered_m["gx"] = (filtered_m.geometry.x // grid_size).astype(int)
filtered_m["gy"] = (filtered_m.geometry.y // grid_size).astype(int)

cooccur_cells = (
    filtered_m
    .groupby(["gx", "gy"])["species"]
    .nunique()
    .reset_index(name="species_count")
)

cooccur_cells = cooccur_cells[cooccur_cells["species_count"] >= 2]

cooccur_cells["x"] = cooccur_cells["gx"] * grid_size
cooccur_cells["y"] = cooccur_cells["gy"] * grid_size

cooccur_gdf = gpd.GeoDataFrame(
    cooccur_cells,
    geometry=gpd.points_from_xy(cooccur_cells.x, cooccur_cells.y),
    crs="EPSG:32736"
).to_crs(epsg=4326)

# --------------------------------------------------
# GRID COUNTS FOR MAP LABELS
# --------------------------------------------------
filtered["lat_bin"] = filtered.geometry.y.round(2)
filtered["lon_bin"] = filtered.geometry.x.round(2)

zone_counts = (
    filtered
    .groupby(["common_name", "lat_bin", "lon_bin"])
    .size()
    .reset_index(name="count")
)

# --------------------------------------------------
# METRICS
# --------------------------------------------------
c1, c2, c3 = st.columns(3)
c1.metric("Total Sightings", len(filtered))
c2.metric("Animals Selected", len(selected_common))
c3.metric("Season", selected_season)

# --------------------------------------------------
# MAP
# --------------------------------------------------
species_colors = {
    "Lion": "red",
    "African Elephant": "green",
    "Leopard": "purple",
    "African Buffalo": "blue",
    "Black Rhinoceros": "black"
}

m = folium.Map(location=[-1.4, 35.2], zoom_start=9)

# Individual sightings
if show_points:
    for _, row in filtered.iterrows():
        folium.CircleMarker(
            [row.geometry.y, row.geometry.x],
            radius=3,
            color=species_colors.get(row["common_name"], "gray"),
            fill=True,
            fill_opacity=0.4,
            popup=row["common_name"]
        ).add_to(m)

# Co-occurrence zones
if show_cooccur:
    for _, row in cooccur_gdf.iterrows():
        folium.CircleMarker(
            [row.geometry.y, row.geometry.x],
            radius=12,
            color="orange",
            fill=True,
            fill_opacity=0.7,
            popup=f"Co-occurrence zone<br>Species count: {row['species_count']}"
        ).add_to(m)

# Counts on map
if show_counts:
    for _, row in zone_counts.iterrows():
        folium.Marker(
            [row.lat_bin, row.lon_bin],
            icon=folium.DivIcon(
                html=f"""
                <div style="font-size:11px;font-weight:bold;text-align:center;">
                    {row['count']}
                </div>
                """
            )
        ).add_to(m)

st_folium(m, width=1100, height=550)

# --------------------------------------------------
# SUMMARY TABLE & CHART
# --------------------------------------------------
st.subheader("Species-wise Sightings (Current Selection)")

species_summary = (
    filtered
    .groupby("common_name")
    .size()
    .reset_index(name="sightings")
    .sort_values("sightings", ascending=False)
)

st.dataframe(species_summary, use_container_width=True)
st.bar_chart(species_summary.set_index("common_name")["sightings"])

# --------------------------------------------------
# EXPLANATION
# --------------------------------------------------
st.markdown("### Co-occurrence Analysis Explanation")

st.markdown("""
Co-occurrence zones represent spatial grid cells (5 km × 5 km) where **two or more species**
are observed within the same area. These zones indicate **shared habitat use or similar
environmental preferences**, but do **not imply direct interaction** between species.

This analysis provides quantitative evidence of **spatial overlap** in wildlife distributions
and helps identify ecologically important zones in the Masai Mara.
""")

# --------------------------------------------------
# FOOTNOTE
# --------------------------------------------------
st.markdown("""
**Note:**  
Sightings are based on GBIF occurrence records and represent observed presence,
not population estimates.
""")

