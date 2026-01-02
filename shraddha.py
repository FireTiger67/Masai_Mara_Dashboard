import streamlit as st
import pandas as pd
import geopandas as gpd
import folium
from streamlit_folium import st_folium

# --------------------------------------------------
# PAGE CONFIG
# --------------------------------------------------
st.set_page_config(layout="wide")
st.title("Masai Mara Wildlife Sightings Dashboard")

st.markdown("""
Interactive geospatial dashboard to explore **Big Five wildlife sightings**
in Masai Mara by **species**, **season**, and **year range**.
""")

# --------------------------------------------------
# LOAD DATA (CSV ONLY – CLOUD SAFE)
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
# GRID + COUNTS
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
# METRICS
# --------------------------------------------------
c1, c2, c3 = st.columns(3)
c1.metric("Total Sightings", len(filtered))
c2.metric("Species Selected", len(selected_animals))
c3.metric("Season", selected_season)

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

for _, row in zone_counts.iterrows():
    color = species_colors.get(row["species"], "gray")

    folium.CircleMarker(
        location=[row.lat_bin, row.lon_bin],
        radius=6 + row["count"] * 0.4,
        color=color,
        fill=True,
        fill_opacity=0.5
    ).add_to(m)

    if show_counts:
        folium.Marker(
            location=[row.lat_bin, row.lon_bin],
            icon=folium.DivIcon(
                html=f"""
                <div style="
                    font-size: 12px;
                    font-weight: bold;
                    color: black;
                    text-align: center;
                ">
                    {row['count']}
                </div>
                """
            )
        ).add_to(m)

st_folium(m, width=1100, height=550)

# --------------------------------------------------
# SPECIES SUMMARY
# --------------------------------------------------
st.subheader("Species-wise Sightings")

species_counts = (
    filtered
    .groupby("species")
    .size()
    .reset_index(name="sightings")
    .sort_values("sightings", ascending=False)
)

st.dataframe(species_counts, use_container_width=True)
st.bar_chart(species_counts.set_index("species")["sightings"])

# --------------------------------------------------
# FOOTNOTE
# --------------------------------------------------
st.markdown("""
**Note:**  
Data is based on GBIF occurrence records and represents observed sightings,
not population estimates.
""")

