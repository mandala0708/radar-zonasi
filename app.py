import time
from sentiment import detect_sentiment, correct_negative_sentence
from math import radians, sin, cos, sqrt, atan2
import pandas as pd
import nltk
import streamlit as st
import streamlit.components.v1 as components  # ✅ TAMBAHAN
from db import (
    init_db,
    insert_sample_sekolah_if_empty,
    load_sekolah_df,
    load_feedback_df,
    save_feedback,
    get_sekolah_id_by_nama
)
from streamlit_folium import st_folium
import folium

# ---------- Basic page config ----------
st.set_page_config(page_title="Radar Zonasi Sentimen — Streamlit", layout="wide")

# ================== ✅ GPS OTOMATIS (FINAL & STABIL) ==================
if "user_lat" not in st.session_state:
    st.session_state["user_lat"] = 0.0
    st.session_state["user_lon"] = 0.0
    st.session_state["gps_ready"] = False
    st.session_state["gps_tried"] = False

# Jalankan GPS hanya sekali
if not st.session_state["gps_tried"]:
    components.html(
        """
        <script>
        navigator.geolocation.getCurrentPosition(
            (pos) => {
                const lat = pos.coords.latitude;
                const lon = pos.coords.longitude;

                const url = new URL(window.location);
                url.searchParams.set("lat", lat);
                url.searchParams.set("lon", lon);
                window.location.href = url.toString();
            },
            (err) => {
                console.log("GPS error:", err.message);
            }
        );
        </script>
        """,
        height=0
    )
    st.session_state["gps_tried"] = True

# Ambil koordinat dari URL (API TERBARU)
params = st.query_params
if "lat" in params and "lon" in params:
    st.session_state["user_lat"] = float(params["lat"])
    st.session_state["user_lon"] = float(params["lon"])
    st.session_state["gps_ready"] = True
# ================================================================

# ---------- Custom CSS ----------
st.markdown("""
<style>
.stCard {
    background: #ffffff;
    padding: 15px;
    border-radius: 15px;
    box-shadow: 0px 4px 12px rgba(0,0,0,0.1);
    margin-bottom: 20px;
}
h1, h2, h3 {
    font-weight: 700;
    color: #2d2d2d;
}
div.stButton > button {
    background-color: #4CAF50;
    color: white !important;
    padding: 10px 18px;
    border-radius: 10px;
    font-weight: bold;
}
</style>
""", unsafe_allow_html=True)

# ---------- Setup ----------
if "nltk_ready" not in st.session_state:
    nltk.download("vader_lexicon", quiet=True)
    st.session_state["nltk_ready"] = True

# ---------- Initialize DB ----------
if "db_initialized" not in st.session_state:
    init_db()
    insert_sample_sekolah_if_empty()
    st.session_state["db_initialized"] = True

# ---------- Cache ----------
if "feedback_cache" not in st.session_state: st.session_state["feedback_cache"] = None
if "sekolah_cache" not in st.session_state: st.session_state["sekolah_cache"] = None
if "map_data" not in st.session_state: st.session_state["map_data"] = None

# ---------- Haversine ----------
def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c

# ---------- Nearest school ----------
def get_nearest_school(df, user_lat, user_lon, max_distance=5000):
    if user_lat == 0.0 or user_lon == 0.0:
        return None, None
    df2 = df.copy()
    df2["distance_m"] = df2.apply(
        lambda r: haversine(user_lat, user_lon, float(r["lat"]), float(r["lon"])),
        axis=1
    )
    df2 = df2.sort_values("distance_m")
    nearest = df2.iloc[0]
    if nearest["distance_m"] > max_distance:
        return None, None
    return nearest["nama"], nearest["distance_m"]

# ================= UI =================
st.title("📍 Radar Zonasi Sekolah — Analisis Sentimen")

# ---------- Sidebar ----------
with st.sidebar:
    st.header("Kontrol")

    sekolah_df_side = load_sekolah_df()
    sekolah_list = sekolah_df_side["nama"].tolist()
    selected_school = st.selectbox("Pilih sekolah", sekolah_list)

    st.markdown("---")
    st.markdown("### 📡 Status GPS")

    if st.session_state["gps_ready"]:
        st.success(
            f"🟢 GPS AKTIF\n\n"
            f"Latitude: {st.session_state['user_lat']:.6f}\n"
            f"Longitude: {st.session_state['user_lon']:.6f}"
        )
    else:
        st.warning(
            "🔴 GPS TIDAK AKTIF\n\n"
            "Gunakan input manual atau izinkan lokasi di browser."
        )

    st.markdown("---")
    st.markdown("### Lokasi Manual (Fallback)")
    user_lat_manual = st.number_input("Latitude Manual", value=0.0, format="%.7f")
    user_lon_manual = st.number_input("Longitude Manual", value=0.0, format="%.7f")

    user_lat = st.session_state["user_lat"] if st.session_state["gps_ready"] else user_lat_manual
    user_lon = st.session_state["user_lon"] if st.session_state["gps_ready"] else user_lon_manual

    radius_m = st.slider("Radius (meter)", 100, 5000, 1000, step=50)

    nearest_name, nearest_distance = get_nearest_school(
        sekolah_df_side, user_lat, user_lon, radius_m
    )
    if nearest_name:
        st.success(f"Sekolah terdekat: {nearest_name} ({nearest_distance:.0f} m)")

# ---------- Load Data ----------
sekolah_df = load_sekolah_df()
fb = load_feedback_df()

# ---------- Layout ----------
col1, col2 = st.columns([2, 1])

def sentiment_color(avg):
    if avg >= 70:
        return "green"
    elif avg >= 40:
        return "orange"
    else:
        return "red"

# ---------- Map ----------
with col1:
    center = [user_lat, user_lon] if user_lat != 0 else [-6.2, 106.8]
    m = folium.Map(location=center, zoom_start=12)

    if st.session_state["gps_ready"]:
        folium.Marker(
            location=[user_lat, user_lon],
            tooltip="📍 Lokasi Anda (GPS)",
            icon=folium.Icon(color="blue", icon="user")
        ).add_to(m)
        folium.Circle(
            location=[user_lat, user_lon],
            radius=radius_m,
            color="blue",
            fill=True,
            fill_opacity=0.08
        ).add_to(m)

    stats = {}
    if fb is not None and not fb.empty:
        g = fb.groupby("sekolah").agg({"pos_pct":"mean","id":"count"}).reset_index()
        for _, r in g.iterrows():
            stats[r["sekolah"]] = r["pos_pct"]

    for _, r in sekolah_df.iterrows():
        color = sentiment_color(stats[r["nama"]]) if r["nama"] in stats else "gray"
        folium.CircleMarker(
            location=[r["lat"], r["lon"]],
            radius=8,
            color=color,
            fill=True,
            tooltip=r["nama"]
        ).add_to(m)

    st_folium(m, width=700, height=600)

# ---------- Panel ----------
with col2:
    st.subheader("Panel Sekolah & Ulasan")

    opini = st.text_area("Tulis opini")

    if st.button("Analisis & Simpan"):
        if opini.strip():
            pos_pct, vader = detect_sentiment(opini)
            school_id = get_sekolah_id_by_nama(selected_school)
            save_feedback(school_id, opini, pos_pct, vader)
            st.success("Opini tersimpan")

            found, corrected = correct_negative_sentence(opini)
            if found or vader < 0:
                st.warning("Kalimat negatif terdeteksi. Saran: " + corrected)
        else:
            st.warning("Opini kosong!")

    if st.button("Download CSV"):
        csv = load_feedback_df().to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Download CSV", csv, "ulasan_sekolah.csv", "text/csv")

st.write("gusti mandala")
