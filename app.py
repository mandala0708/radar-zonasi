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

# ---------- Custom CSS ----------
st.markdown("""
<style>
.stCard {background:#fff;padding:15px;border-radius:15px;box-shadow:0 4px 12px rgba(0,0,0,.1)}
h1,h2,h3{font-weight:700}
div.stButton>button{background:#4CAF50;color:white!important;border-radius:10px}
div.stButton>button:hover{background:#45a049}
</style>
""", unsafe_allow_html=True)

# ---------- Setup ----------
if "nltk_ready" not in st.session_state:
    nltk.download("vader_lexicon", quiet=True)
    st.session_state["nltk_ready"] = True

if "db_initialized" not in st.session_state:
    init_db()
    insert_sample_sekolah_if_empty()
    st.session_state["db_initialized"] = True

if "map_data" not in st.session_state:
    st.session_state["map_data"] = None

if "selected_school" not in st.session_state:
    st.session_state["selected_school"] = None

if "zoom_center" not in st.session_state:
    st.session_state["zoom_center"] = None

if "manual_lat_lon" not in st.session_state:
    st.session_state["manual_lat_lon"] = {"lat": None, "lon": None}

# ---------- Haversine ----------
def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1))*cos(radians(lat2))*sin(dlon/2)**2
    return R * (2 * atan2(sqrt(a), sqrt(1-a)))

# ================= UI =================
st.title("📍 Radar Zonasi Sekolah — Analisis Sentimen")

# ================= GPS / Manual Input =================
geo = get_geolocation()
if geo:
    gps_lat = geo["coords"]["latitude"]
    gps_lon = geo["coords"]["longitude"]
    gps_ready = True
else:
    gps_lat = None
    gps_lon = None
    gps_ready = False

st.subheader("📌 Lokasi Anda")
st.markdown("Jika GPS tidak akurat, Anda bisa masukkan koordinat manual:")
manual_lat = st.number_input("Latitude (manual fallback)", value=gps_lat if gps_lat else 0.0, format="%.7f")
manual_lon = st.number_input("Longitude (manual fallback)", value=gps_lon if gps_lon else 0.0, format="%.7f")

# Pilih koordinat yang digunakan
if gps_ready and gps_lat is not None and gps_lon is not None:
    user_lat, user_lon = gps_lat, gps_lon
else:
    user_lat, user_lon = manual_lat, manual_lon

# ================= RADIUS CONTROL =================
st.subheader("🎯 Pengaturan Radius Zonasi")
radius_on = st.toggle("Aktifkan Radius", value=True)

radius = st.slider(
    "Radius (meter)",
    100, 10000, 10000, 100,
    disabled=not radius_on
)

# ================= LOAD DATA =================
sekolah_df = load_sekolah_df()
fb = load_feedback_df()

# ================= MAP =================
col1, col2 = st.columns([2,1])

with col1:
    # Map center
    if st.session_state["zoom_center"]:
        center = st.session_state["zoom_center"]
        zoom = 15
    else:
        center = [user_lat, user_lon] if user_lat and user_lon else [-6.2, 106.8]
        zoom = 12

    m = folium.Map(location=center, zoom_start=zoom)
    
    # Statistik sentimen
    stats = {}
    if not fb.empty:
        g = fb.groupby("sekolah").agg({"pos_pct":"mean","id":"count"}).reset_index()
        for _, r in g.iterrows():
            stats[r["sekolah"]] = r

    # Marker lokasi user
    if user_lat and user_lon:
        folium.Marker(
            [user_lat, user_lon],
            tooltip="📍 Lokasi Anda",
            icon=folium.Icon(color="blue", icon="user")
        ).add_to(m)
        if radius_on:
            folium.Circle(
                [user_lat, user_lon],
                radius=radius,
                color="blue",
                fill=True,
                fill_opacity=0.08
            ).add_to(m)

    # MARKER SEKOLAH
    nearest_distance = None
    nearest_school_name = None
    for _, r in sekolah_df.iterrows():
        # Filter berdasarkan radius
        if user_lat and user_lon and radius_on:
            dist = haversine(user_lat, user_lon, r["lat"], r["lon"])
            if dist > radius:
                continue
        else:
            dist = None

        nama = r["nama"]
        if nama in stats:
            avg = stats[nama]["pos_pct"]
            cnt = stats[nama]["id"]
            popup = f"<b>{nama}</b><br>Sentimen: {avg:.1f}%<br>Ulasan: {cnt}"
            color = "green" if avg >= 70 else "orange" if avg >= 40 else "red"
        else:
            popup = f"<b>{nama}</b><br>Belum ada ulasan"
            color = "gray"

        highlight = False
        if dist is not None and (nearest_distance is None or dist < nearest_distance):
            nearest_distance = dist
            nearest_school_name = nama
            highlight = True

        folium.CircleMarker(
            [r["lat"], r["lon"]],
            radius=8,
            color="blue" if highlight else color,
            fill=True,
            fill_color="blue" if highlight else color,
            popup=popup,
            tooltip=folium.Tooltip(nama, permanent=True, direction="top")
        ).add_to(m)

    # Simpan map data
    map_data = st_folium(m, width=700, height=600)
    st.session_state["map_data"] = map_data

# ================= MAP → SELECTBOX SYNC =================
if map_data and map_data.get("last_object_clicked"):
    latc = map_data["last_object_clicked"]["lat"]
    lonc = map_data["last_object_clicked"]["lng"]

    tmp = sekolah_df.copy()
    tmp["dist"] = tmp.apply(lambda r: haversine(latc, lonc, r["lat"], r["lon"]), axis=1)
    nearest = tmp.sort_values("dist").iloc[0]

    if st.session_state["selected_school"] != nearest["nama"]:
        st.session_state["selected_school"] = nearest["nama"]
        st.session_state["zoom_center"] = [nearest["lat"], nearest["lon"]]
        st.rerun()

# ================= SIDEBAR =================
with st.sidebar:
    st.header("Kontrol")
    sekolah_list = sekolah_df["nama"].tolist()
    if st.session_state["selected_school"] is None:
        st.session_state["selected_school"] = sekolah_list[0]

    selected_school = st.selectbox(
        "Pilih / Cari sekolah",
        sekolah_list,
        index=sekolah_list.index(st.session_state["selected_school"]),
        key="selected_school"
    )

    # Auto zoom
    row = sekolah_df[sekolah_df["nama"] == selected_school]
    if not row.empty:
        lat, lon = float(row.iloc[0]["lat"]), float(row.iloc[0]["lon"])
        if st.session_state["zoom_center"] != [lat, lon]:
            st.session_state["zoom_center"] = [lat, lon]
            st.rerun()

    st.markdown("### 📡 Status GPS")
    if gps_ready:
        st.success(f"🟢 GPS AKTIF\n\nLat: {user_lat:.6f}\nLon: {user_lon:.6f}")
    else:
        st.warning("🔴 GPS TIDAK AKTIF (gunakan input manual)")

# ================= PANEL ULASAN =================
with col2:
    st.subheader("Panel Sekolah & Ulasan")
    st.markdown(f"**Sekolah terpilih:** {selected_school}")

    if "last_comment_time" not in st.session_state:
        st.session_state["last_comment_time"] = 0

    opini = st.text_area("Tulis opini / ulasan")

    if st.button("Analisis & Simpan"):
        if time.time() - st.session_state["last_comment_time"] < 10:
            st.warning("Tunggu beberapa detik.")
        elif not opini.strip():
            st.warning("Opini kosong.")
        else:
            pos, vader = detect_sentiment(opini)
            found, corrected = correct_negative_sentence(opini)
            sid = get_sekolah_id_by_nama(selected_school)
            save_feedback(sid, opini, pos, vader)
            st.session_state["last_comment_time"] = time.time()
            st.success("Opini tersimpan.")
            if found or vader < 0:
                st.warning("Kalimat negatif terdeteksi. Saran: " + corrected)

    if st.button("Tampilkan Ulasan Terbaru"):
        df_sel = fb[fb["sekolah"] == selected_school]
        if df_sel.empty:
            st.info("Belum ada ulasan.")
        else:
            for _, r in df_sel.iterrows():
                st.write(f"• {r['opini']} (Pos: {r['pos_pct']:.1f}%)")

    st.markdown("---")
    st.subheader("📥 Export CSV")
    if st.button("Download CSV Ulasan"):
        # Filter feedback sekolah terpilih
        df_export = fb[fb["sekolah"] == selected_school]
        if df_export.empty:
            st.warning("Belum ada data ulasan untuk sekolah ini.")
        else:
            csv = df_export.to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Download CSV", csv, f"ulasan_{selected_school}.csv", "text/csv")

    st.markdown("---")
    st.write("gusti mandala")
