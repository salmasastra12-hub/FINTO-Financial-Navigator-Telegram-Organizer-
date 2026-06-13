"""
FINTO - Financial Navigator & Telegram Organizer
Aplikasi manajemen keuangan personal berbasis Streamlit
dengan integrasi API Telegram untuk pengingat tagihan.
"""

import streamlit as st
import pandas as pd
import hashlib
import requests
import os
from datetime import datetime, date
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER

# ============================================================
# KONFIGURASI DASAR & FILE DATABASE
# ============================================================

st.set_page_config(page_title="FINTO - Financial Navigator & Telegram Organizer",
                    page_icon="💰", layout="wide")

FILE_USER = "database_pengguna.csv"
FILE_KAS = "database_keuangan.csv"

KOLOM_USER = [
    "nama_pengguna", "password_hash", "telegram_token",
    "telegram_chat_id", "reminder_harian_aktif"
]

KOLOM_KAS = [
    "tanggal_input", "nama_pengguna", "tipe", "kategori",
    "jumlah_rp", "penyimpanan_dana", "batas_waktu",
    "status", "periode_bulan"
]


def init_database():
    """Membuat file CSV jika belum ada."""
    if not os.path.exists(FILE_USER):
        pd.DataFrame(columns=KOLOM_USER).to_csv(FILE_USER, index=False)
    if not os.path.exists(FILE_KAS):
        pd.DataFrame(columns=KOLOM_KAS).to_csv(FILE_KAS, index=False)


def load_users():
    return pd.read_csv(FILE_USER, dtype=str).fillna("")


def load_kas():
    df = pd.read_csv(FILE_KAS, dtype=str).fillna("")
    if not df.empty:
        df["jumlah_rp"] = pd.to_numeric(df["jumlah_rp"], errors="coerce").fillna(0)
    return df


def save_users(df):
    df.to_csv(FILE_USER, index=False)


def save_kas(df):
    df.to_csv(FILE_KAS, index=False)


# ============================================================
# 4.2 SISTEM AUTENTIKASI AKUN & PRIVASI MULTI-USER (SHA-256)
# ============================================================

def hash_password(password: str) -> str:
    """Mengenkripsi password polos menjadi hash SHA-256."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def validasi_login(username: str, password: str) -> bool:
    df_user = load_users()
    hashed = hash_password(password)
    cocok = df_user[
        (df_user["nama_pengguna"] == username)
        & (df_user["password_hash"] == hashed)
    ]
    return not cocok.empty


def daftar_user_baru(username, password, token, chat_id, reminder_aktif=False):
    df_user = load_users()
    if username in df_user["nama_pengguna"].values:
        return False, "Nama pengguna sudah terdaftar. Silakan gunakan nama lain."

    baris_baru = {
        "nama_pengguna": username,
        "password_hash": hash_password(password),
        "telegram_token": token,
        "telegram_chat_id": chat_id,
        "reminder_harian_aktif": str(reminder_aktif),
    }
    df_user = pd.concat([df_user, pd.DataFrame([baris_baru])], ignore_index=True)
    save_users(df_user)
    return True, "Registrasi berhasil! Silakan login pada tab 'Saya Kembali'."


# ============================================================
# 4.1 MODUL ONBOARDING & PANDUAN KONEKSI TELEGRAM
# ============================================================

def modul_onboarding():
    with st.expander("📲 Panduan Menghubungkan Bot Telegram (Klik untuk membuka)"):
        st.markdown(
            """
            Agar FINTO dapat mengirim pengingat tagihan ke Telegram Anda, lakukan
            langkah-langkah berikut:

            **1. Dapatkan HTTP API Token dari @BotFather**
            - Buka Telegram, cari **@BotFather**.
            - Kirim perintah `/newbot`, lalu ikuti instruksi pemberian nama bot.
            - BotFather akan memberikan **HTTP API Token** (contoh:
              `123456789:ABCdefGhIJKlmNoPQRstuVwxyZ`). Simpan token ini.

            **2. Dapatkan Chat ID Anda dari @userinfobot**
            - Cari **@userinfobot** di Telegram.
            - Kirim pesan apa saja (misalnya `/start`).
            - Bot akan membalas dengan **Chat ID** Anda (berupa angka).

            **3. Aktifkan bot Anda**
            - Cari nama bot yang baru Anda buat di Telegram.
            - Kirim perintah **`/start`** pada bot tersebut.
            - Langkah ini *wajib* dilakukan, karena Telegram tidak mengizinkan
              bot mengirim pesan ke pengguna yang belum memulai obrolan dengannya.

            **4. Masukkan Token & Chat ID**
            - Salin Token dan Chat ID ke dalam form registrasi FINTO di samping.
            """
        )


# ============================================================
# 4.3 MODUL PENGINGAT HARIAN (TOGGLE & SIMULASI ENGINE 21:00)
# ============================================================

def kirim_pesan_telegram(token: str, chat_id: str, teks: str):
    """Mengirim pesan teks ke Telegram menggunakan API sendMessage."""
    if not token or not chat_id:
        return False, "Token atau Chat ID belum diatur."

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": teks, "parse_mode": "Markdown"}

    try:
        response = requests.post(url, data=payload, timeout=10)
        if response.status_code == 200:
            return True, "Pesan terkirim ke Telegram."
        return False, f"Gagal mengirim pesan (kode: {response.status_code})."
    except requests.exceptions.RequestException as e:
        return False, f"Terjadi kesalahan koneksi: {e}"


def modul_pengaturan_reminder(username, df_user):
    st.subheader("⏰ Konfigurasi Jadwal Pengurusan Rutin Harian (21:00 WIB)")

    user_row = df_user[df_user["nama_pengguna"] == username].iloc[0]
    status_aktif = str(user_row["reminder_harian_aktif"]) == "True"

    toggle_value = st.toggle(
        "Aktifkan Pengingat Harian Otomatis Jam 21:00 WIB",
        value=status_aktif,
        key="reminder_aktif",
    )

    if toggle_value != status_aktif:
        idx = df_user[df_user["nama_pengguna"] == username].index[0]
        df_user.at[idx, "reminder_harian_aktif"] = str(toggle_value)
        save_users(df_user)
        st.success("Status pengingat harian berhasil diperbarui.")

    st.caption(
        "Jika diaktifkan, sistem akan mengirimkan ringkasan keuangan dan "
        "status tagihan setiap pukul 21:00 WIB melalui bot Telegram Anda."
    )

    if st.button("🔔 Jalankan Simulasi Engine Jam 9 Malam"):
        if st.session_state.get("reminder_aktif", False):
            df_kas_user = ambil_kas_user(username)
            ringkasan = hitung_ringkasan_keuangan(df_kas_user)

            teks = (
                "*🌙 Pengingat Malam FINTO (21:00 WIB)*\n\n"
                f"Halo *{username}*, berikut ringkasan keuangan Anda hari ini:\n\n"
                f"💵 Sisa Saldo: Rp {ringkasan['sisa_saldo']:,.0f}\n"
                f"📥 Total Pemasukan: Rp {ringkasan['total_masuk']:,.0f}\n"
                f"📤 Total Pengeluaran: Rp {ringkasan['total_keluar']:,.0f}\n"
                f"⚠️ Tagihan Belum Dibayar: Rp {ringkasan['tagihan_belum_bayar']:,.0f}\n"
                f"💰 Limit Dana Jajan Aman: Rp {ringkasan['limit_jajan_aman']:,.0f}\n\n"
                "_Pesan otomatis dari FINTO - Financial Navigator & Telegram Organizer._"
            )

            sukses, pesan = kirim_pesan_telegram(
                user_row["telegram_token"], user_row["telegram_chat_id"], teks
            )
            if sukses:
                st.success(f"Simulasi berhasil dijalankan. {pesan}")
            else:
                st.error(f"Simulasi gagal: {pesan}")
        else:
            st.warning("Pengingat harian belum diaktifkan. Aktifkan toggle di atas terlebih dahulu.")


# ============================================================
# 4.4 FORM INPUT JURNAL KAS (OFFLINE-SAFE ENTRY)
# ============================================================

def bersihkan_angka(teks: str) -> float:
    """Membersihkan string angka dari titik, koma, dan spasi."""
    teks_bersih = str(teks).replace(".", "").replace(",", "").strip()
    if teks_bersih == "":
        return 0.0
    try:
        return float(teks_bersih)
    except ValueError:
        return 0.0


def modul_input_jurnal(username):
    st.subheader("📝 Input Jurnal Aktivitas Kas")

    with st.form("form_input_jurnal", clear_on_submit=True):
        col1, col2 = st.columns(2)

        with col1:
            tanggal_input = st.date_input("Tanggal Transaksi", value=date.today())
            tipe = st.radio("Tipe Transaksi", ["Masuk", "Keluar"], horizontal=True)
            kategori = st.selectbox(
                "Kategori",
                [
                    "Gaji/Uang Saku", "Sewa Kos", "Listrik", "Internet",
                    "Iuran Akademik", "Makan & Minum", "Transportasi",
                    "Hiburan", "Tabungan", "Lainnya",
                ],
            )

        with col2:
            jumlah_str = st.text_input(
                "Jumlah (Rp)", placeholder="Contoh: 150.000 atau 150,000"
            )
            penyimpanan_dana = st.selectbox(
                "Penyimpanan Dana", ["Tunai", "Rekening Bank", "E-Wallet"]
            )

            tagihan_wajib = st.checkbox("Transaksi ini merupakan tagihan wajib?")
            batas_waktu = None
            status = "Lunas"
            if tagihan_wajib:
                batas_waktu = st.date_input("Batas Waktu Pembayaran")
                status = "Belum Dibayar"

        submitted = st.form_submit_button("💾 Amankan Transaksi Ke Dalam Sistem")

        if submitted:
            jumlah_rp = bersihkan_angka(jumlah_str)

            if jumlah_rp <= 0:
                st.error("Jumlah transaksi tidak valid. Masukkan angka lebih dari 0.")
                return

            df_kas = load_kas()
            baris_baru = {
                "tanggal_input": tanggal_input.strftime("%Y-%m-%d"),
                "nama_pengguna": username,
                "tipe": tipe,
                "kategori": kategori,
                "jumlah_rp": jumlah_rp,
                "penyimpanan_dana": penyimpanan_dana,
                "batas_waktu": batas_waktu.strftime("%Y-%m-%d") if batas_waktu else "",
                "status": status,
                "periode_bulan": tanggal_input.strftime("%Y-%m"),
            }
            df_kas = pd.concat([df_kas, pd.DataFrame([baris_baru])], ignore_index=True)
            save_kas(df_kas)

            st.success(
                "Berhasil Diinputkan! Data transaksi telah sukses "
                "diamankan ke dalam sistem buku kas."
            )
            st.toast("✅ Transaksi tersimpan!")


# ============================================================
# 4.5 DASBOR UTAMA & GENERATOR PDF PREMIUM
# ============================================================

def ambil_kas_user(username):
    df_kas = load_kas()
    if df_kas.empty:
        return df_kas
    return df_kas[df_kas["nama_pengguna"] == username]


def hitung_ringkasan_keuangan(df_kas_user, periode=None):
    if periode:
        df_kas_user = df_kas_user[df_kas_user["periode_bulan"] == periode]

    if df_kas_user.empty:
        return {
            "total_masuk": 0, "total_keluar": 0, "sisa_saldo": 0,
            "tagihan_belum_bayar": 0, "limit_jajan_aman": 0,
        }

    total_masuk = df_kas_user[df_kas_user["tipe"] == "Masuk"]["jumlah_rp"].sum()
    total_keluar = df_kas_user[df_kas_user["tipe"] == "Keluar"]["jumlah_rp"].sum()
    sisa_saldo = total_masuk - total_keluar

    tagihan_belum_bayar = df_kas_user[
        df_kas_user["status"] == "Belum Dibayar"
    ]["jumlah_rp"].sum()

    limit_jajan_aman = sisa_saldo - tagihan_belum_bayar

    return {
        "total_masuk": total_masuk,
        "total_keluar": total_keluar,
        "sisa_saldo": sisa_saldo,
        "tagihan_belum_bayar": tagihan_belum_bayar,
        "limit_jajan_aman": limit_jajan_aman,
    }


def buat_pdf_laporan(username, df_periode, ringkasan, periode):
    """Membuat laporan PDF resmi menggunakan ReportLab."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                             topMargin=2 * cm, bottomMargin=2 * cm,
                             leftMargin=2 * cm, rightMargin=2 * cm)

    styles = getSampleStyleSheet()
    judul_style = ParagraphStyle(
        "Judul", parent=styles["Title"], fontSize=16, alignment=TA_CENTER
    )
    sub_style = ParagraphStyle(
        "Sub", parent=styles["Normal"], fontSize=10, alignment=TA_CENTER
    )

    elemen = []
    elemen.append(Paragraph("LAPORAN BUKU KAS - FINTO", judul_style))
    elemen.append(Paragraph(
        f"Financial Navigator &amp; Telegram Organizer", sub_style
    ))
    elemen.append(Spacer(1, 0.3 * cm))
    elemen.append(Paragraph(
        f"Nama Pengguna: <b>{username}</b> | Periode: <b>{periode}</b>", sub_style
    ))
    elemen.append(Spacer(1, 0.5 * cm))

    # Tabel ringkasan
    data_ringkasan = [
        ["Komponen", "Nilai (Rp)"],
        ["Total Pemasukan", f"{ringkasan['total_masuk']:,.0f}"],
        ["Total Pengeluaran", f"{ringkasan['total_keluar']:,.0f}"],
        ["Sisa Saldo Buku Kas", f"{ringkasan['sisa_saldo']:,.0f}"],
        ["Alokasi Tagihan Belum Dibayar", f"{ringkasan['tagihan_belum_bayar']:,.0f}"],
        ["Limit Dana Jajan Aman", f"{ringkasan['limit_jajan_aman']:,.0f}"],
    ]
    tabel_ringkasan = Table(data_ringkasan, colWidths=[9 * cm, 6 * cm])
    tabel_ringkasan.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2E75B6")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F6FA")]),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
    ]))
    elemen.append(tabel_ringkasan)
    elemen.append(Spacer(1, 0.7 * cm))

    elemen.append(Paragraph("Rincian Transaksi", styles["Heading2"]))
    elemen.append(Spacer(1, 0.2 * cm))

    data_rincian = [["Tanggal", "Tipe", "Kategori", "Jumlah (Rp)", "Status"]]
    for _, row in df_periode.iterrows():
        data_rincian.append([
            row["tanggal_input"], row["tipe"], row["kategori"],
            f"{row['jumlah_rp']:,.0f}", row["status"],
        ])

    if len(data_rincian) == 1:
        data_rincian.append(["-", "-", "Tidak ada data", "-", "-"])

    tabel_rincian = Table(data_rincian, colWidths=[3 * cm, 2.5 * cm, 4 * cm, 3 * cm, 2.5 * cm])
    tabel_rincian.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2E75B6")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (3, 0), (3, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F6FA")]),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
    ]))
    elemen.append(tabel_rincian)

    elemen.append(Spacer(1, 1 * cm))
    elemen.append(Paragraph(
        f"Dokumen ini dibuat secara otomatis oleh sistem FINTO pada "
        f"{datetime.now().strftime('%d-%m-%Y %H:%M')} WIB.",
        sub_style,
    ))

    doc.build(elemen)
    buffer.seek(0)
    return buffer


def modul_dasbor(username):
    st.subheader("📊 Dasbor Utama Laporan Buku Kas")

    df_kas_user = ambil_kas_user(username)

    if df_kas_user.empty:
        st.info("Belum ada data transaksi. Silakan input transaksi pertama Anda.")
        return

    periode_list = sorted(df_kas_user["periode_bulan"].unique(), reverse=True)
    periode_pilihan = st.selectbox("Pilih Periode Bulan", periode_list)

    df_periode = df_kas_user[df_kas_user["periode_bulan"] == periode_pilihan]
    ringkasan = hitung_ringkasan_keuangan(df_kas_user, periode_pilihan)

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Pemasukan", f"Rp {ringkasan['total_masuk']:,.0f}")
    col2.metric("Total Pengeluaran", f"Rp {ringkasan['total_keluar']:,.0f}")
    col3.metric("Sisa Saldo Buku Kas", f"Rp {ringkasan['sisa_saldo']:,.0f}")

    col4, col5 = st.columns(2)
    col4.metric("Alokasi Tagihan Belum Dibayar", f"Rp {ringkasan['tagihan_belum_bayar']:,.0f}")
    col5.metric("Limit Dana Jajan Aman", f"Rp {ringkasan['limit_jajan_aman']:,.0f}")

    st.divider()
    st.markdown("**Rincian Transaksi Periode Ini**")
    st.dataframe(
        df_periode[["tanggal_input", "tipe", "kategori", "jumlah_rp",
                     "penyimpanan_dana", "status", "batas_waktu"]],
        use_container_width=True, hide_index=True,
    )

    pdf_buffer = buat_pdf_laporan(username, df_periode, ringkasan, periode_pilihan)
    st.download_button(
        label="📄 Unduh Laporan PDF",
        data=pdf_buffer,
        file_name=f"Laporan_FINTO_{username}_{periode_pilihan}.pdf",
        mime="application/pdf",
    )


# ============================================================
# 4.6 PANEL NOTIFIKASI & VERIFIKASI KELUNASAN ANGGARAN WAJIB
# ============================================================

def modul_notifikasi_dan_verifikasi(username, df_user):
    st.subheader("🔔 Panel Kendali Notifikasi & Verifikasi Tagihan")

    user_row = df_user[df_user["nama_pengguna"] == username].iloc[0]
    df_kas_user = ambil_kas_user(username)

    # --- Pindai jatuh tempo ---
    st.markdown("**Pindai Jatuh Tempo Tagihan Wajib**")
    if st.button("🚨 Pindai Jalur Jatuh Tempo Tagihan Wajib"):
        tagihan_belum_bayar = df_kas_user[df_kas_user["status"] == "Belum Dibayar"].copy()

        if tagihan_belum_bayar.empty:
            st.info("Status Aman. Tidak ada agenda tagihan mengikat dalam waktu dekat (H-3 s/d H-1).")
        else:
            tagihan_belum_bayar["batas_waktu_dt"] = pd.to_datetime(
                tagihan_belum_bayar["batas_waktu"], errors="coerce"
            )
            hari_ini = pd.Timestamp(date.today())
            tagihan_belum_bayar["selisih_hari"] = (
                tagihan_belum_bayar["batas_waktu_dt"] - hari_ini
            ).dt.days

            mendesak = tagihan_belum_bayar[
                tagihan_belum_bayar["selisih_hari"].isin([1, 2, 3])
                | (tagihan_belum_bayar["selisih_hari"] <= 0)
            ]

            if mendesak.empty:
                st.info("Status Aman. Tidak ada agenda tagihan mengikat dalam waktu dekat (H-3 s/d H-1).")
            else:
                daftar_teks = "\n".join(
                    f"- {row['kategori']} (Rp {row['jumlah_rp']:,.0f}) — "
                    f"jatuh tempo {row['batas_waktu']}"
                    for _, row in mendesak.iterrows()
                )
                st.warning(
                    f"⚠️ Terdapat {len(mendesak)} tagihan mendekati jatuh tempo "
                    f"(H-3 s/d H-1):\n\n{daftar_teks}"
                )

                teks_telegram = (
                    "*🚨 Peringatan Jatuh Tempo Tagihan - FINTO*\n\n"
                    f"Halo *{username}*, berikut tagihan yang mendekati jatuh tempo:\n\n"
                    + daftar_teks
                    + "\n\nMohon segera lakukan pembayaran."
                )
                sukses, pesan = kirim_pesan_telegram(
                    user_row["telegram_token"], user_row["telegram_chat_id"], teks_telegram
                )
                if sukses:
                    st.success(f"Notifikasi Telegram terkirim. {pesan}")
                else:
                    st.error(f"Gagal mengirim notifikasi Telegram: {pesan}")

    st.divider()

    # --- Verifikasi kelunasan ---
    st.markdown("**Verifikasi Kelunasan Anggaran Wajib**")
    df_belum_bayar = df_kas_user[df_kas_user["status"] == "Belum Dibayar"]

    if df_belum_bayar.empty:
        st.success("Semua tagihan wajib telah lunas. Tidak ada yang perlu diverifikasi.")
        return

    for idx, row in df_belum_bayar.iterrows():
        col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
        col1.write(f"**{row['kategori']}** — Rp {row['jumlah_rp']:,.0f}")
        col2.write(f"Jatuh tempo: {row['batas_waktu']}")
        metode_bayar = col3.selectbox(
            "Metode", ["Tunai", "Rekening Bank", "E-Wallet"],
            key=f"metode_{idx}", label_visibility="collapsed",
        )
        if col4.button("✅ Lunas", key=f"lunas_{idx}"):
            df_kas_full = load_kas()
            mask = (
                (df_kas_full["nama_pengguna"] == username)
                & (df_kas_full["tanggal_input"] == row["tanggal_input"])
                & (df_kas_full["kategori"] == row["kategori"])
                & (df_kas_full["jumlah_rp"] == row["jumlah_rp"])
                & (df_kas_full["status"] == "Belum Dibayar")
            )
            df_kas_full.loc[mask, "status"] = "Sudah Dibayar"
            df_kas_full.loc[mask, "penyimpanan_dana"] = metode_bayar
            save_kas(df_kas_full)
            st.rerun()


# ============================================================
# HALAMAN AUTENTIKASI (LOGIN / REGISTRASI)
# ============================================================

def halaman_login():
    st.title("💰 FINTO")
    st.caption("Financial Navigator & Telegram Organizer")

    modul_onboarding()

    tab_login, tab_daftar = st.tabs(["🔑 Saya Kembali", "🆕 Daftar Pengguna Baru"])

    with tab_login:
        with st.form("form_login"):
            username = st.text_input("Nama Pengguna")
            password = st.text_input("Kata Sandi", type="password")
            submit_login = st.form_submit_button("Masuk")

            if submit_login:
                if validasi_login(username, password):
                    df_user = load_users()
                    user_row = df_user[df_user["nama_pengguna"] == username].iloc[0]
                    st.session_state["user_aktif"] = username
                    st.session_state["token_aktif"] = user_row["telegram_token"]
                    st.session_state["chat_id_aktif"] = user_row["telegram_chat_id"]
                    st.rerun()
                else:
                    st.error("Nama pengguna atau kata sandi salah.")

    with tab_daftar:
        with st.form("form_daftar"):
            username_baru = st.text_input("Nama Pengguna Baru")
            password_baru = st.text_input("Kata Sandi Baru", type="password")
            token_baru = st.text_input("Telegram HTTP API Token")
            chat_id_baru = st.text_input("Telegram Chat ID")
            submit_daftar = st.form_submit_button("Daftar")

            if submit_daftar:
                if not username_baru or not password_baru:
                    st.error("Nama pengguna dan kata sandi wajib diisi.")
                else:
                    sukses, pesan = daftar_user_baru(
                        username_baru, password_baru, token_baru, chat_id_baru
                    )
                    if sukses:
                        st.success(pesan)
                    else:
                        st.error(pesan)


# ============================================================
# HALAMAN UTAMA (SETELAH LOGIN)
# ============================================================

def halaman_utama():
    username = st.session_state["user_aktif"]

    with st.sidebar:
        st.title("💰 FINTO")
        st.write(f"👤 Pengguna: **{username}**")
        if st.button("🚪 Keluar"):
            for key in ["user_aktif", "token_aktif", "chat_id_aktif"]:
                st.session_state.pop(key, None)
            st.rerun()

        menu = st.radio(
            "Menu Navigasi",
            ["Input Jurnal Kas", "Dasbor & Laporan PDF",
             "Notifikasi & Verifikasi Tagihan", "Pengaturan Reminder"],
        )

    df_user = load_users()

    if menu == "Input Jurnal Kas":
        modul_input_jurnal(username)
    elif menu == "Dasbor & Laporan PDF":
        modul_dasbor(username)
    elif menu == "Notifikasi & Verifikasi Tagihan":
        modul_notifikasi_dan_verifikasi(username, df_user)
    elif menu == "Pengaturan Reminder":
        modul_pengaturan_reminder(username, df_user)


# ============================================================
# ROUTING UTAMA APLIKASI
# ============================================================

def main():
    init_database()

    if "user_aktif" not in st.session_state:
        halaman_login()
    else:
        halaman_utama()


if __name__ == "__main__":
    main()
