import time
from sentiment import detect_sentiment, correct_negative_sentence
from math import radians, sin, cos, sqrt, atan2
import pandas as pd
import nltk
import streamlit as st
from streamlit_js_eval import get_geolocation
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

# ---------- Page config ----------
st.set_page_config(page_title="Radar Zonasi Sentimen — Streamlit", layout="wide")

# ================== ✅ GPS OTOMATIS (RESMI & WORK) ==================
geo = get_geolocation()

if geo:
    user_lat = geo["coords"]["latitude"]
    user_lon = geo["coords"]["longitude"]
    gps_ready = True
else:
    user_lat = 0.0
    user_lon = 0.0
    gps_ready = False
# ===================================================================

# ---------- Setup ----------
if "nltk_ready" not in st.session_state:
    nltk.download("vader_lexicon", quiet=True)
    st.session_state["nltk_ready"] = True

if "db_initialized" not in st.session_state:
    init_db()
    insert_sample_sekolah_if_empty()
    st.session_state["db_initialized"] = True

# ---------- Haversine ----------
def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c

def get_nearest_school(df, lat, lon, max_distance=5000):
    if lat == 0.0 or lon == 0.0:
        return None, None
    df2 = df.copy()
    df2["distance_m"] = df2.apply(
        lambda r: haversine(lat, lon, float(r["lat"]), float(r["lon"])), axis=1
    )
    df2 = df2.sort_values("distance_m")
    n = df2.iloc[0]
    if n["distance_m"] > max_distance:
        return None, None
    return n["nama"], n["distance_m"]

# ================= UI =================
st.title("📍 Radar Zonasi Sekolah — Analisis Sentimen")

with st.sidebar:
    st.header("Kontrol")

    sekolah_df = load_sekolah_df()
    sekolah_list = sekolah_df["nama"].tolist()
    selected_school = st.selectbox("Pilih sekolah", sekolah_list)

    st.markdown("### 📡 Status GPS")
    if gps_ready:
        st.success(f"🟢 GPS AKTIF\n\nLat: {user_lat:.6f}\nLon: {user_lon:.6f}")
    else:
        st.warning("🔴 GPS TIDAK AKTIF\nGunakan input manual")


    radius = st.slider("Radius (meter)", 100, 5000, 1000)

    name, dist = get_nearest_school(sekolah_df, lat, lon, radius)
    if name:
        st.success(f"Sekolah terdekat: {name} ({dist:.0f} m)")

# ---------- Map ----------
col1, col2 = st.columns([2,1])
with col1:
    center = [lat, lon] if lat != 0 else [-6.2, 106.8]
    m = folium.Map(location=center, zoom_start=12)

    if gps_ready:
        folium.Marker(
            [lat, lon],
            tooltip="📍 Lokasi Anda",
            icon=folium.Icon(color="blue", icon="user")
        ).add_to(m)

    fb = load_feedback_df()
    stats = {}
    if not fb.empty:
        g = fb.groupby("sekolah").agg({"pos_pct":"mean"}).reset_index()
        for _, r in g.iterrows():
            stats[r["sekolah"]] = r["pos_pct"]

    for _, r in sekolah_df.iterrows():
        color = "gray"
        if r["nama"] in stats:
            color = "green" if stats[r["nama"]] >= 70 else "orange"
        folium.CircleMarker(
            [r["lat"], r["lon"]],
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
            pos, vader = detect_sentiment(opini)
            sid = get_sekolah_id_by_nama(selected_school)
            save_feedback(sid, opini, pos, vader)
            st.success("Opini tersimpan")
        else:
            st.warning("Opini kosong")

st.write("gusti mandala")

