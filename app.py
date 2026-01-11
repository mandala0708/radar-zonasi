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

# ================== GPS OTOMATIS ==================
geo = get_geolocation()

if geo:
    user_lat = geo["coords"]["latitude"]
    user_lon = geo["coords"]["longitude"]
    gps_ready = True
else:
    user_lat = 0.0
    user_lon = 0.0
    gps_ready = False
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

# ---------- Haversine ----------
def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1))*cos(radians(lat2))*sin(dlon/2)**2
    return R * (2 * atan2(sqrt(a), sqrt(1-a)))

def get_nearest_school(df, lat, lon, max_distance):
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

# ---------- Sidebar ----------
with st.sidebar:
    st.header("Kontrol")

    sekolah_df = load_sekolah_df()
    sekolah_list = sekolah_df["nama"].tolist()
    default_school = sekolah_list[0] if sekolah_list else None

    if st.session_state["map_data"] and st.session_state["map_data"].get("last_object_clicked"):
        latc = st.session_state["map_data"]["last_object_clicked"]["lat"]
        lonc = st.session_state["map_data"]["last_object_clicked"]["lng"]
        tmp = sekolah_df.copy()
        tmp["dist"] = ((tmp["lat"]-latc)**2 + (tmp["lon"]-lonc)**2)**0.5
        default_school = tmp.sort_values("dist").iloc[0]["nama"]

    selected_school = st.selectbox(
        "Pilih sekolah",
        sekolah_list,
        index=sekolah_list.index(default_school) if default_school else 0,
        key="selected_school"
    )

    st.markdown("### 📡 Status GPS")
    if gps_ready:
        st.success(f"🟢 GPS AKTIF\n\nLat: {user_lat:.6f}\nLon: {user_lon:.6f}")
    else:
        st.warning("🔴 GPS TIDAK AKTIF\nIzinkan lokasi di browser")

    radius = st.slider("Radius (meter)", 100, 5000, 1000)

    name, dist = get_nearest_school(sekolah_df, user_lat, user_lon, radius)
    if name:
        st.success(f"Sekolah terdekat: {name} ({dist:.0f} m)")

# ---------- Data ----------
fb = load_feedback_df()

# ---------- Layout ----------
col1, col2 = st.columns([2,1])

# ---------- Helper ----------
def sentiment_color(avg):
    if avg >= 70: return "green"
    if avg >= 40: return "orange"
    return "red"

# ---------- Map ----------
with col1:
    center = [user_lat, user_lon] if gps_ready else [-6.2, 106.8]
    m = folium.Map(location=center, zoom_start=12)

    stats = {}
    if not fb.empty:
        g = fb.groupby("sekolah").agg({"pos_pct":"mean","id":"count"}).reset_index()
        for _, r in g.iterrows():
            stats[r["sekolah"]] = r

    if gps_ready:
        folium.Marker(
            [user_lat, user_lon],
            tooltip="📍 Lokasi Anda",
            icon=folium.Icon(color="blue", icon="user")
        ).add_to(m)
        folium.Circle(
            [user_lat, user_lon],
            radius=radius,
            color="blue",
            fill=True,
            fill_opacity=0.08
        ).add_to(m)

    for _, r in sekolah_df.iterrows():
        nama = r["nama"]
        if nama in stats:
            avg = stats[nama]["pos_pct"]
            cnt = stats[nama]["id"]
            popup = f"<b>{nama}</b><br>Sentimen: {avg:.1f}%<br>Ulasan: {cnt}"
            color = sentiment_color(avg)
        else:
            popup = f"<b>{nama}</b><br>Belum ada ulasan"
            color = "gray"

        folium.CircleMarker(
            [r["lat"], r["lon"]],
            radius=8,
            popup=popup,
            tooltip=nama,
            color=color,
            fill=True
        ).add_to(m)

    st.session_state["map_data"] = st_folium(m, width=700, height=600)

# ---------- Panel ----------
with col2:
    st.subheader("Panel Sekolah & Ulasan")
    st.markdown(f"**Sekolah terpilih:** {selected_school}")

    if "last_comment_time" not in st.session_state:
        st.session_state["last_comment_time"] = 0

    opini = st.text_area("Tulis opini / ulasan")

    if st.button("Analisis & Simpan"):
        if time.time() - st.session_state["last_comment_time"] < 10:
            st.warning("Tunggu beberapa detik sebelum mengirim lagi.")
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
        df_sel = fb[fb["sekolah"]==selected_school]
        if df_sel.empty:
            st.info("Belum ada ulasan.")
        else:
            for _, r in df_sel.iterrows():
                st.write(f"• {r['opini']} (Pos: {r['pos_pct']:.1f}%)")

    st.markdown("---")
    st.subheader("📥 Export CSV")
    if st.button("Download CSV Ulasan"):
        if fb.empty:
            st.warning("Belum ada data.")
        else:
            csv = fb.to_csv(index=False).encode("utf-8")
            st.download_button(
                "⬇️ Download CSV",
                csv,
                "ulasan_sekolah.csv",
                "text/csv"
            )

    st.markdown("---")
    st.write("gusti mandala")
