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
from folium.plugins import Fullscreen, MeasureControl

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

# ================== GPS OTOMATIS ==================
geo = get_geolocation()
user_lat = geo["coords"]["latitude"] if geo else -6.2
user_lon = geo["coords"]["longitude"] if geo else 106.8
gps_ready = geo is not None
# ==================================================

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
if "radius_on" not in st.session_state:
    st.session_state["radius_on"] = True
if "radius" not in st.session_state:
    st.session_state["radius"] = 1000

# ---------- Haversine ----------
def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1))*cos(radians(lat2))*sin(dlon/2)**2
    return R * (2 * atan2(sqrt(a), sqrt(1-a)))

# ================= UI =================
st.title("📍 Radar Zonasi Sekolah — Analisis Sentimen")
sekolah_df = load_sekolah_df()
fb = load_feedback_df()
col1, col2 = st.columns([2,1])

# ================= MAP =================
with col1:
    center = st.session_state["zoom_center"] or ([user_lat, user_lon] if gps_ready else [-6.2, 106.8])
    zoom = 15 if st.session_state["zoom_center"] else 12
    m = folium.Map(location=center, zoom_start=zoom)

    Fullscreen(position="topright", title="Fullscreen", title_cancel="Exit Fullscreen", force_separate_button=True).add_to(m)
    MeasureControl(position="bottomleft", primary_length_unit="meters").add_to(m)
    folium.LayerControl(position="topright").add_to(m)

    # Statistik sentimen
    stats = {}
    if not fb.empty:
        g = fb.groupby("sekolah").agg({"pos_pct":"mean","id":"count"}).reset_index()
        for _, r in g.iterrows():
            stats[r["sekolah"]] = r

    # Marker user
    if gps_ready:
        folium.Marker([user_lat, user_lon], tooltip="📍 Lokasi Anda", icon=folium.Icon(color="blue", icon="user")).add_to(m)

    # Marker sekolah
    nearest_distance = None
    for _, r in sekolah_df.iterrows():
        dist = haversine(user_lat, user_lon, r["lat"], r["lon"]) if gps_ready and st.session_state["radius_on"] else None
        if dist and dist > st.session_state["radius"]:
            continue

        nama = r["nama"]
        if nama in stats:
            avg = stats[nama]["pos_pct"]
            cnt = stats[nama]["id"]
            popup = f"<b>{nama}</b><br>Sentimen: {avg:.1f}%<br>Ulasan: {cnt}"
            color = "green" if avg >= 70 else "orange" if avg >= 40 else "red"
        else:
            popup = f"<b>{nama}</b><br>Belum ada ulasan"
            color = "gray"

        highlight = dist is not None and (nearest_distance is None or dist < nearest_distance)
        if highlight:
            nearest_distance = dist
            st.session_state["selected_school_temp"] = nama
            st.session_state["zoom_center_temp"] = [r["lat"], r["lon"]]

        folium.CircleMarker(
            [r["lat"], r["lon"]],
            radius=8,
            color="blue" if highlight else color,
            fill=True,
            fill_color="blue" if highlight else color,
            popup=popup,
            tooltip=folium.Tooltip(nama, permanent=True, direction="top")
        ).add_to(m)

    # Circle radius
    if gps_ready and st.session_state["radius_on"]:
        folium.Circle([user_lat, user_lon], radius=st.session_state["radius"], color="blue", fill=True, fill_opacity=0.08).add_to(m)

    st.session_state["map_data"] = st_folium(m, width=700, height=600)

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

    # Auto zoom ke sekolah
    row = sekolah_df[sekolah_df["nama"] == selected_school]
    if not row.empty:
        lat, lon = float(row.iloc[0]["lat"]), float(row.iloc[0]["lon"])
        st.session_state["zoom_center"] = [lat, lon]

    st.markdown("### 📡 Status GPS")
    if gps_ready:
        st.success(f"🟢 GPS AKTIF\nLat: {user_lat:.6f}\nLon: {user_lon:.6f}")
    else:
        st.warning("🔴 GPS TIDAK AKTIF")

    st.subheader("Radius Zonasi")
    st.session_state["radius_on"] = st.toggle("Aktifkan Radius", value=True)
    st.session_state["radius"] = st.slider("Radius (meter)", 100, 10000, 1000, 100, disabled=not st.session_state["radius_on"])

# ================= PANEL ULASAN =================
with col2:
    st.subheader("Panel Sekolah & Ulasan")
    selected_school = st.session_state["selected_school_temp"] or st.session_state["selected_school"]
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
    df_export = fb[fb["sekolah"] == selected_school]
    if not df_export.empty:
        csv = df_export.to_csv(index=False).encode("utf-8")
        st.download_button(f"⬇️ Download CSV {selected_school}", csv, f"ulasan_{selected_school}.csv", "text/csv")
    else:
        st.warning("Belum ada data ulasan untuk sekolah ini.")

    st.markdown("---")
    st.write("gusti mandala")
