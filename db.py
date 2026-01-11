import sqlite3  # Library untuk akses database SQLite
import threading  # Library untuk mengatur lock/thread-safe
import time  # Library untuk delay saat retry
import pandas as pd  # Library manipulasi data dan membaca query menjadi DataFrame
import streamlit as st  # Library Streamlit untuk session_state/cache
from pathlib import Path  # Untuk menangani path file secara cross-platform

# ------------------- Path dan koneksi database -------------------
DB = Path(__file__).parent / "feedback.db"  # File database berada di folder yang sama dengan script ini

conn_global = sqlite3.connect(DB, timeout=30, check_same_thread=False)  # Koneksi global SQLite
conn_global.row_factory = sqlite3.Row  # Agar hasil fetch bisa diakses seperti dictionary
db_lock = threading.Lock()  # Lock untuk memastikan akses DB aman antar thread

# ------------------- Inisialisasi database -------------------
def init_db():
    with db_lock:  # Lock agar thread-safe
        c = conn_global.cursor()
        # Membuat tabel sekolah jika belum ada
        c.execute("""
            CREATE TABLE IF NOT EXISTS sekolah (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nama TEXT UNIQUE,
                info TEXT,
                lat REAL,
                lon REAL,
                akreditasi TEXT
            )
        """)
        # Membuat tabel feedback jika belum ada
        c.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sekolah_id INTEGER,
                opini TEXT,
                pos_pct REAL,
                vader_compound REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(sekolah_id) REFERENCES sekolah(id)
            )
        """)
        # Membuat index untuk mempercepat query berdasarkan sekolah_id di feedback
        c.execute("CREATE INDEX IF NOT EXISTS idx_feedback_sekolah ON feedback(sekolah_id)")
        # Membuat index untuk mempercepat query berdasarkan nama sekolah
        c.execute("CREATE INDEX IF NOT EXISTS idx_sekolah_nama ON sekolah(nama)")
        conn_global.commit()  # Simpan perubahan

# ------------------- Insert sample data sekolah jika tabel kosong -------------------
def insert_sample_sekolah_if_empty():
    with db_lock:
        c = conn_global.cursor()
        c.execute("SELECT COUNT(1) FROM sekolah")  # Cek jumlah data sekolah
        count = c.fetchone()[0]
        if count == 0:  # Jika kosong, masukkan data sample
            sample_data = [
                ("SMAN 3 PAGAR ALAM","JL. MERDEKA BUMI AGUNG, Kel. BUMI AGUNG, Kec. DEMPO UTARA",-4.0567331,103.1969652,"A"),
                ("SMA Taman Siswa Pagar Alam","JLN DEMPO RAYA No.96, Gn. Dempo, Kec. Pagar Alam Selatan",-4.0391165,103.196982,"C"),
                ("SMA Model Negeri 4 Pagaralam","Pagar Alam, Sumatera Selatan.",-4.0419617,103.2278845,"A"),
                ("SMA Negeri 1 Pagar Alam","Kota Pagar Alam, Sumatera Selatan.",-4.0137128,103.2498493,"A"),
                ("SMA Nahdlatul Ulama Pagaralam","Pagar Alam, Sumatera Selatan",-4.0168254,103.2542662,"C"),
                ("SMA Muhammadiyah Pagaralam","Pagar Alam, Sumatera Selatan",-4.0247497,103.2542317,"C"),
                ("SMA Negeri 2 Pagar Alam","JL. Masik Siagim SP. Bacang, Karang Dalo, Kecamatan Dempo Tengah, Kota Pagar Alam",-4.0491788,103.3005961,"A"),
                ("SMA Negeri 5 Pagar Alam","JL. Lintas Pagar Alam–Lahat, Desa Atung Bungsu, Kec. Dempo Selatan, Kota Pagar Alam",-4.0216000,103.4007000,"B"),
                ("SMP Negeri 3 Pagar Alam","Pagar Alam, Sumatera Selatan",-4.0686737,103.1876586,"B"),
                ("SMP Negeri 10 Kota Pagar Alam","Pagar Alam, Sumatera Selatan",-4.0925019,103.2169849,"B"),
                ("SMPN 7 Pagar Alam","Pagar Alam, Sumatera Selatan",-4.0724978,103.2669791,"B"),
                ("SMP Negeri 6 Kota Pagar Alam","Pagar Alam, Sumatera Selatan",-4.0247554,103.189743,"B"),
                ("SMP IT Ar Raihan Kota Pagar Alam","Pagar Alam, Sumatera Selatan",-4.0153858,103.2202963,"B"),
                ("SMP Negeri 2 Kota Pagar Alam","Pagar Alam, Sumatera Selatan",-4.0239647,103.2229994,"B"),
                ("SMP IT Ababil Pagar Alam","Pagar Alam, Sumatera Selatan",-4.0274488,103.2443081,"B"),
                ("SMP Xaverius Pagar Alam","Pagar Alam, Sumatera Selatan",-4.0214371,103.2481156,"B"),
                ("SMP-SMA IT Al-Quds Pagar Alam","Pagar Alam, Sumatera Selatan",-4.001176,103.2450104,"B"),
                ("TK-SD-SMP Methodist-5 Pagar Alam","Pagar Alam, Sumatera Selatan",-4.0237208,103.2519359,"B"),
                ("SMP Muhammadiyah Pagar Alam","Pagar Alam, Sumatera Selatan",-4.0250264,103.2535736,"B"),
                ("SMP Islam Tunas Ilmu Pagar Alam","Pagar Alam, Sumatera Selatan",-4.027633,103.2533692,"B"),
                ("SMP Muhammadiyah 3 Bandar Lampung","Pagar Alam, Sumatera Selatan",-4.0192318,103.2526231,"B"),
                ("SMPN 1 Pagar Alam","Pagar Alam, Sumatera Selatan",-4.01801,103.25476,"B"),
                ("SMP PGRI Pagar Alam","Pagar Alam, Sumatera Selatan",-4.01779,103.25385,"B"),
                ("SMP 'Aisyiyah Terpadu","Pagar Alam, Sumatera Selatan",-4.0234139,103.2715783,"B"),
                ("SMP Negeri 8 Pagar Alam","Pagar Alam, Sumatera Selatan",-4.0348499,103.2766974,"B"),
                ("SMP N 4 Pagar Alam","Pagar Alam, Sumatera Selatan",-4.0493517,103.2998674,"B"),
                ("SMP N 5 Pagar Alam","Pagar Alam, Sumatera Selatan",-4.0791514,103.3328989,"B"),
                ("SMP Negeri 9 Pagar Alam","Pagar Alam, Sumatera Selatan",-4.0184189,103.4015071,"B")
                
                
            ]  
            # Loop insert semua sample data
            for s in sample_data:
                c.execute(
                    "INSERT OR IGNORE INTO sekolah (nama, info, lat, lon, akreditasi) VALUES (?, ?, ?, ?, ?)",
                    s
                )
            conn_global.commit()  # Simpan ke DB

# ------------------- Insert atau update sekolah (bisa kapan saja) -------------------
def insert_or_update_sekolah(sekolah_list):
    """
    Fungsi untuk menambahkan daftar sekolah baru atau update jika sudah ada.
    sekolah_list: list of tuples (nama, info, lat, lon, akreditasi)
    """
    if not sekolah_list:
        return  # Jika list kosong, langsung keluar

    with db_lock:  # Pastikan thread-safe
        c = conn_global.cursor()
        for s in sekolah_list:
            # INSERT OR REPLACE → jika nama sekolah sudah ada, update data lain
            c.execute(
                """
                INSERT INTO sekolah (nama, info, lat, lon, akreditasi)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(nama) DO UPDATE SET
                    info=excluded.info,
                    lat=excluded.lat,
                    lon=excluded.lon,
                    akreditasi=excluded.akreditasi
                """,
                s
            )
        conn_global.commit()  # Simpan ke DB

    # Reset cache supaya data terbaru langsung tampil
    st.session_state["sekolah_cache"] = None



# ------------------- Ambil ID sekolah berdasarkan nama -------------------
def get_sekolah_id_by_nama(nama):
    with db_lock:
        c = conn_global.cursor()
        c.execute("SELECT id FROM sekolah WHERE nama = ?", (nama,))
        row = c.fetchone()
        return row["id"] if row else None  # Kembalikan None jika tidak ada

# ------------------- Load DataFrame sekolah dengan cache -------------------
def load_sekolah_df():
    if st.session_state.get("sekolah_cache") is not None:  # Pakai cache dulu
        return st.session_state["sekolah_cache"]
    df = safe_read("SELECT * FROM sekolah")  # Baca DB
    st.session_state["sekolah_cache"] = df  # Simpan cache
    return df

# ------------------- Load DataFrame feedback dengan cache -------------------
def load_feedback_df():
    if st.session_state.get("feedback_cache") is not None:  # Pakai cache dulu
        return st.session_state["feedback_cache"]
    df = safe_read("""
        SELECT f.*, s.nama AS sekolah, s.akreditasi
        FROM feedback f
        JOIN sekolah s ON f.sekolah_id = s.id
        ORDER BY f.created_at DESC
    """)
    st.session_state["feedback_cache"] = df  # Simpan cache
    return df

# ------------------- Simpan feedback baru ke DB -------------------
def save_feedback(sekolah_id, opini, pos_pct, vader_compound):
    with db_lock:
        c = conn_global.cursor()
        c.execute(
            "INSERT INTO feedback (sekolah_id, opini, pos_pct, vader_compound) VALUES (?, ?, ?, ?)",
            (sekolah_id, opini, pos_pct, vader_compound)
        )
        conn_global.commit()
    st.session_state["feedback_cache"] = None  # Reset cache agar load ulang

# ------------------- Fungsi membaca query DB aman (retry jika terkunci) -------------------
def safe_read(query, params=None, max_retries=6):
    attempt = 0
    while attempt < max_retries:
        try:
            with db_lock:
                if params:
                    return pd.read_sql_query(query, conn_global, params=params)
                return pd.read_sql_query(query, conn_global)
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower():  # Jika DB terkunci
                attempt += 1
                time.sleep(0.1 * attempt)  # Delay progresif sebelum retry
            else:
                raise
    return pd.DataFrame()  # Jika semua retry gagal, kembalikan DataFrame kosong
