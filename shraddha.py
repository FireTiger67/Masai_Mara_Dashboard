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
by **species**, **season**, **year range**, and **pairwise spatial co-occurrence**.
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

st.sidebar.markdown("### Pairwise Co-occurrence")
pair_a = st.sidebar.selectbox(
    "Species A",
    options=sorted(gdf["species"].unique())
)

pair_b = st.sidebar.selectbox(
    "Species B",
    options=sorted(gdf["species"].unique()),
    index=1
)

show_points = st.sidebar.checkbox("Show individual sightings", value=True)
show_general_cooccur = st.sidebar.checkbox("Show general co-occurrence zones", value=True)
show_pairwise = st.sidebar.checkbox("Show pairwise co-occurrence zones", value=True)
show_counts = st.sidebar.checkbox("Show counts on map", value=True)

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
# MOST FREQUENT SEASON PER SPECIES (CARDS)
# --------------------------------------------------
st.subheader("Most Frequently Observed Season per Species")

season_counts = (
    filtered
    .groupby(["species", "season"])
    .size()
    .reset_index(name="count")
)

top_seasons = (
    season_counts
    .sort_values(["species", "count"], ascending=[True, False])
    .groupby("species")
    .first()
    .reset_index()
)

if not top_seasons.empty:
    cols = st.columns(len(top_seasons))
    for i, row in top_seasons.iterrows():
        cols[i].metric(
            label=row["species"],
            value=row["season"]
        )
else:
    st.info("No seasonal data available for the selected filters.")

# --------------------------------------------------
# GRID-BASED CO-OCCURRENCE (GENERAL)
# --------------------------------------------------
filtered_m = filtered.to_crs(epsg=32736)  # meters
grid_size = 5000  # 5 km

filtered_m["gx"] = (filtered_m.geometry.x // grid_size).astype(int)
filtered_m["gy"] = (filtered_m.geometry.y // grid_size).astype(int)

general_cells = (
    filtered_m
    .groupby(["gx", "gy"])["species"]
    .nunique()
    .reset_index(name="species_count")
)

general_cells = general_cells[general_cells["species_count"] >= 2]

general_cells["x"] = general_cells["gx"] * grid_size
general_cells["y"] = general_cells["gy"] * grid_size

general_cooccur = gpd.GeoDataFrame(
    general_cells,
    geometry=gpd.points_from_xy(general_cells.x, general_cells.y),
    crs="EPSG:32736"
).to_crs(epsg=4326)

# --------------------------------------------------
# PAIRWISE CO-OCCURRENCE
# --------------------------------------------------
pair_df = filtered_m[filtered_m["species"].isin([pair_a, pair_b])]

pair_cells = (
    pair_df
    .groupby(["gx", "gy"])["species"]
    .nunique()
    .reset_index(name="species_count")
)

pair_cells = pair_cells[pair_cells["species_count"] == 2]

pair_cells["x"] = pair_cells["gx"] * grid_size
pair_cells["y"] = pair_cells["gy"] * grid_size

pair_cooccur = gpd.GeoDataFrame(
    pair_cells,
    geometry=gpd.points_from_xy(pair_cells.x, pair_cells.y),
    crs="EPSG:32736"
).to_crs(epsg=4326)

# --------------------------------------------------
# GRID COUNTS FOR MAP LABELS
# --------------------------------------------------
filtered["lat_bin"] = filtered.geometry.y.round(2)
filtered["lon_bin"] = filtered.geometry.x.round(2)

zone_counts = (
    filtered
    .groupby(["species", "lat_bin", "lon_bin"])
    .size()
    .reset_index(name="count")
)

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
            [row.geometry.y, row.geometry.x],
            radius=3,
            color=species_colors.get(row["species"], "gray"),
            fill=True,
            fill_opacity=0.4
        ).add_to(m)

# General co-occurrence zones
if show_general_cooccur:
    for _, row in general_cooccur.iterrows():
        folium.CircleMarker(
            [row.geometry.y, row.geometry.x],
            radius=12,
            color="orange",
            fill=True,
            fill_opacity=0.6,
            popup=f"General co-occurrence<br>Species count: {row['species_count']}"
        ).add_to(m)

# Pairwise co-occurrence zones
if show_pairwise and pair_a != pair_b:
    for _, row in pair_cooccur.iterrows():
        folium.CircleMarker(
            [row.geometry.y, row.geometry.x],
            radius=14,
            color="red",
            fill=True,
            fill_opacity=0.8,
            popup=f"{pair_a} + {pair_b}"
        ).add_to(m)

# Counts
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
# SUMMARY TABLE
# --------------------------------------------------
st.subheader("Species-wise Sightings")

species_summary = (
    filtered
    .groupby("species")
    .size()
    .reset_index(name="sightings")
    .sort_values("sightings", ascending=False)
)

st.dataframe(species_summary, use_container_width=True)
st.bar_chart(species_summary.set_index("species")["sightings"])

# --------------------------------------------------
# EXPLANATION
# --------------------------------------------------
st.markdown("### Co-occurrence Analysis Explanation")

st.markdown("""
- **General co-occurrence** shows grid cells (5 km × 5 km) where two or more species are observed together.
- **Pairwise co-occurrence** highlights zones where the selected species pair is observed within the same grid cell.
- Co-occurrence indicates **shared spatial presence**, not direct interaction or behavioural relationships.
""")

st.markdown("""
**Note:** Sightings are based on GBIF occurrence records and represent observed presence,
not population estimates.
""")

