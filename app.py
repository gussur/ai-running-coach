import os
from flask import Flask, request, redirect, session
import requests
import google.generativeai as genai
from datetime import datetime
import time
import sqlite3
from fitparse import FitFile

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'kunci_rahasia_coach_ai_super_aman')

# --- KONFIGURASI API ---
STRAVA_CLIENT_ID = os.environ.get('STRAVA_CLIENT_ID')
STRAVA_CLIENT_SECRET = os.environ.get('STRAVA_CLIENT_SECRET')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

# --- INISIALISASI DATABASE ---
def init_db():
    conn = sqlite3.connect('coach_data.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (athlete_id INTEGER PRIMARY KEY, age INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS reports (id INTEGER PRIMARY KEY AUTOINCREMENT, athlete_id INTEGER, tanggal TEXT, tipe_analisis TEXT, laporan_html TEXT)''')
    conn.commit()
    conn.close()

init_db()

# --- FUNGSI BEDAH FILE .FIT ---
def parse_fit_data(file_path):
    try:
        fitfile = FitFile(file_path)
        data_ringkas = {
            "type": "Aktivitas",
            "distance_m": 0,
            "duration_m": 0,
            "avg_hr": 0,
            "max_hr": 0,
            "calories": 0
        }
        
        for record in fitfile.get_messages('session'):
            for data in record:
                if data.name == 'total_distance': data_ringkas['distance_m'] = data.value or 0
                if data.name == 'total_timer_time': data_ringkas['duration_m'] = (data.value or 0) / 60
                if data.name == 'avg_heart_rate': data_ringkas['avg_hr'] = data.value or 0
                if data.name == 'max_heart_rate': data_ringkas['max_hr'] = data.value or 0
                if data.name == 'total_calories': data_ringkas['calories'] = data.value or 0
                if data.name == 'sport': data_ringkas['type'] = data.value or "Aktivitas"

        return data_ringkas
    except Exception as e:
        return f"GAGAL MEMBACA FILE: {str(e)}"

# --- CSS GLOBAL ---
CSS_STYLE = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    body { font-family: 'Inter', sans-serif; background-color: #f4f7f6; color: #333; line-height: 1.6; margin: 0; padding: 20px; }
    .container { max-width: 700px; margin: 40px auto; background: #ffffff; padding: 40px; border-radius: 24px; box-shadow: 0 10px 40px rgba(0,0,0,0.08); }
    h2, h3, h4 { color: #1a202c; }
    .badge { display: inline-block; background: #FFF0E9; color: #FC4C02; padding: 6px 16px; border-radius: 20px; font-weight: 700; font-size: 0.85em; margin-bottom: 20px; letter-spacing: 0.5px;}
    .stats-box { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px; margin-bottom: 30px; text-align: center; }
    .ai-content { color: #2d3748; font-size: 1.05em; }
    .ai-content h3, .ai-content h4 { border-bottom: 2px solid #edf2f7; padding-bottom: 10px; margin-top: 30px; color: #2c5282; }
    .btn-primary { background: #FC4C02; color: white; padding: 14px 28px; border-radius: 12px; text-decoration: none; font-weight: 600; display: inline-block; transition: 0.3s; width: 80%; text-align: center; border: none; cursor: pointer; font-size: 1em;}
    .btn-primary:hover { background: #e34302; transform: translateY(-2px); box-shadow: 0 4px 12px rgba(252, 76, 2, 0.3); }
    .btn-outline { background: transparent; color: #FC4C02; border: 2px solid #FC4C02; padding: 12px 26px; border-radius: 12px; text-decoration: none; font-weight: 600; display: inline-block; transition: 0.3s; margin-left: 10px;}
    .actions { text-align: center; margin-top: 40px; }
    .upload-section { border: 2px dashed #cbd5e0; padding: 25px; border-radius: 12px; margin-top: 35px; text-align: center; background: #f8fafc; }
</style>
"""

# ==========================================
# RUTE 1: HALAMAN UTAMA (LANDING PAGE)
# ==========================================
@app.route('/')
def home():
    return f'''
        <!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">{CSS_STYLE}</head><body>
        <div class="container" style="text-align: center; max-width: 450px;">
            <h2 style="color: #FC4C02; font-size: 2.2em; margin-bottom: 5px;">AI Coach 40+</h2>
            <p style="color: #718096; margin-bottom: 30px;">Pendamping cerdas untuk pelari usia matang.</p>
            
            <form action="/login" method="GET">
                <input type="number" name="age" placeholder="Masukkan Umur (Contoh: 56)" required 
                       style="padding: 15px; width: 80%; border-radius: 12px; border: 1px solid #cbd5e0; margin-bottom: 15px; font-size: 1.1em; text-align: center; outline: none;">
                <br>
                <button type="submit" class="btn-primary" style="width: 88%;">Hubungkan Strava</button>
            </form>

            <div class="upload-section">
                <h4 style="margin-top: 0; color: #4a5568;">Analisis File Mentah (.FIT)</h4>
                <p style="font-size: 0.85em; color: #718096; margin-bottom: 15px;">Data HR lebih akurat dari Garmin/Coros.</p>
                <form action="/upload" method="POST" enctype="multipart/form-data">
                    <input type="number" name="age" placeholder="Umur Anda" required style="width: 80%; padding: 10px; border-radius: 8px; border: 1px solid #cbd5e0; margin-bottom: 10px; text-align: center;">
                    <input type="file" name="file_fit" accept=".fit" required style="margin-bottom: 15px; font-size: 0.9em;">
                    <button type="submit" style="background: #2d3748; color: white; padding: 12px; border-radius: 8px; cursor: pointer; border: none; width: 85%; font-weight: bold;">Upload & Bedah Data</button>
                </form>
            </div>
            
            <div style="margin-top: 25px;">
                <a href="/riwayat" style="color: #2b6cb0; text-decoration: none; font-size: 0.9em; font-weight: bold;">Lihat Riwayat Laporan &rarr;</a>
            </div>
        </div>
        </body></html>
    '''

# ==========================================
# RUTE 2: LOGIN STRAVA
# ==========================================
@app.route('/login')
def login():
    age = request.args.get('age')
    redirect_uri_dinamis = request.host_url + 'callback'
    if "localhost" not in redirect_uri_dinamis:
        redirect_uri_dinamis = redirect_uri_dinamis.replace("http://", "https://")

    auth_url = (f"https://www.strava.com/oauth/authorize?client_id={STRAVA_CLIENT_ID}"
                f"&response_type=code&redirect_uri={redirect_uri_dinamis}"
                f"&approval_prompt=force&scope=activity:read_all"
                f"&state={age}")
    return redirect(auth_url)

# ==========================================
# RUTE 3: CALLBACK STRAVA & ANALISIS AI
# ==========================================
@app.route('/callback')
def callback():
    code = request.args.get('code')
    user_age = request.args.get('state')
    if not code: return "Akses ditolak."

    # 1. Dapatkan Token
    token_response = requests.post('https://www.strava.com/oauth/token', data={
        'client_id': STRAVA_CLIENT_ID, 'client_secret': STRAVA_CLIENT_SECRET, 'code': code, 'grant_type': 'authorization_code'
    }).json()
    
    if 'access_token' not in token_response: return f"Gagal masuk Strava. Error: {token_response}"
    access_token = token_response.get('access_token')
    athlete_id = token_response.get('athlete', {}).get('id')

    # Simpan Session
    if athlete_id:
        session['athlete_id'] = athlete_id
        conn = sqlite3.connect('coach_data.db')
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO users (athlete_id, age) VALUES (?, ?)", (athlete_id, user_age))
        conn.commit(); conn.close()

    # 2. Tarik Data YTD
    tahun_ini = datetime.now().year
    timestamp_after = int(time.mktime(datetime(tahun_ini, 1, 1).timetuple()))
    activities = requests.get(f'https://www.strava.com/api/v3/athlete/activities?after={timestamp_after}&per_page=200', headers={'Authorization': f'Bearer {access_token}'}).json()
    
    if isinstance(activities, dict) and 'message' in activities: return "Gagal menarik data Strava."

    hari_ini_str = datetime.now().strftime('%Y-%m-%d')
    aktivitas_hari_ini = [act for act in activities if act.get('start_date_local', '').startswith(hari_ini_str)]
    tipe_label = {'Run': '🏃 Lari', 'Swim': '🏊 Renang', 'Ride': '🚴 Sepeda', 'Walk': '🚶 Jalan', 'Hike': '🧗 Mendaki'}

    # 3. Logika Analisis (Bisa mendeteksi banyak aktivitas hari ini)
    if aktivitas_hari_ini:
        tipe_analisis = f"Sesi Hari Ini ({len(aktivitas_hari_ini)} Aktivitas)"
        detail_hari_ini = []
        ringkasan_ui = []
        
        for act in aktivitas_hari_ini:
            t_asli = act.get('type')
            j_km = round(act.get('distance', 0) / 1000, 2)
            w_menit = round(act.get('moving_time', 0) / 60, 1)
            hr_avg = act.get('average_heartrate', 0)
            
            detail_hari_ini.append(f"- {t_asli}: {j_km}km, {w_menit}mnt, HR {hr_avg}bpm")
            ringkasan_ui.append(f"<b>{tipe_label.get(t_asli, t_asli)}</b> ({j_km}km)")

        tampilan_ui_teks = " | ".join(ringkasan_ui)
        teks_untuk_ai = "\n".join(detail_hari_ini)
        
        prompt = f"""Kamu pelatih olahraga usia {user_age} tahun. Klien melakukan beberapa sesi hari ini:
        {teks_untuk_ai}
        Berikan evaluasi menyeluruh untuk sesi hari ini. Analisis apakah kombinasinya baik untuk pemulihan atau terlalu berat.
        ATURAN KETAT: JANGAN gunakan markdown ```html. Gunakan tag HTML standar <h3>, <p>, <ul>, <li>, <strong>."""
    
    else:
        # Jika tidak ada aktivitas hari ini, rekap YTD
        tipe_analisis = "Rekap YTD Komprehensif"
        rekap_ui = {}
        diary_lari, diary_renang = [], []
        
        for act in activities:
            t_asli = act.get('type')
            label = tipe_label.get(t_asli, f'✨ {t_asli}')
            rekap_ui[label] = rekap_ui.get(label, 0) + 1
            
            tgl = act.get('start_date_local', '')[:10]
            j_km = act.get('distance', 0) / 1000
            w_mnt = act.get('moving_time', 0) / 60
            hr = act.get('average_heartrate', 0)
            
            if t_asli == 'Run': diary_lari.append(f"Tgl {tgl}: {j_km:.1f}km, {w_mnt:.0f}mnt, HR {hr}bpm")
            elif t_asli == 'Swim': diary_renang.append(f"Tgl {tgl}: {j_km*1000:.0f}m, {w_mnt:.0f}mnt")
            
        tampilan_ui_teks = " | ".join([f"<b>{k}</b>: {v}x" for k, v in rekap_ui.items()])
        teks_lari = '\n'.join(diary_lari) if diary_lari else "Tidak ada"
        teks_renang = '\n'.join(diary_renang) if diary_renang else "Tidak ada"
        
        prompt = f"""Kamu Sports Analyst untuk usia {user_age} tahun. Evaluasi data YTD ini:
        LARI: {teks_lari}
        RENANG: {teks_renang}
        ATURAN KETAT: JANGAN gunakan markdown ```html. Gunakan HTML standar <h3>, <p>, <ul>, <li>."""

    # Generate AI
    ai_response = model.generate_content(prompt)
    laporan_html = ai_response.text.replace("```html", "").replace("```", "").strip()

    # Simpan Report
    if athlete_id:
        conn = sqlite3.connect('coach_data.db'); c = conn.cursor()
        c.execute("INSERT INTO reports (athlete_id, tanggal, tipe_analisis, laporan_html) VALUES (?, ?, ?, ?)", (athlete_id, hari_ini_str, tipe_analisis, laporan_html))
        conn.commit(); conn.close()

    return f'''
        <!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">{CSS_STYLE}</head><body>
        <div class="container">
            <div style="text-align: center;">
                <div class="badge">ANALISIS STRAVA</div>
                <h2 style="margin-top: 0; margin-bottom: 25px;">{tipe_analisis}</h2>
                <div class="stats-box"><p>{tampilan_ui_teks}</p></div>
            </div>
            <div class="ai-content">{laporan_html}</div>
            <div class="actions">
                <a href="/riwayat" class="btn-primary" style="background:#2d3748; width: auto; padding: 12px 24px;">Lihat Riwayat</a>
                <a href="/" class="btn-outline">Kembali</a>
            </div>
        </div>
        </body></html>
    '''

# ==========================================
# RUTE 4: UPLOAD FILE .FIT
# ==========================================
@app.route('/upload', methods=['POST'])
def upload_file():
    user_age = request.form.get('age') or "50"
    file = request.files.get('file_fit')
    
    if not file: return "File tidak ditemukan."
    
    temp_path = "temp_activity.fit"
    file.save(temp_path)
    
    # Bedah data
    data = parse_fit_data(temp_path)
    
    # Hapus file dengan aman
    if os.path.exists(temp_path): os.remove(temp_path)

    # Jika hasil bedah berupa teks error
    if isinstance(data, str): 
        return f"Maaf, gagal membedah data: {data}"

    j_km = round(data['distance_m'] / 1000, 2)
    w_mnt = round(data['duration_m'], 1)

    prompt = f"""
    Kamu pelatih ahli usia {user_age} tahun. Klien mengupload file aktivitas .FIT mentah.
    Data:
    - Jenis: {data['type']}
    - Jarak: {j_km} km
    - Durasi: {w_mnt} menit
    - Detak Jantung Rata-rata: {data['avg_hr']} bpm
    - Detak Jantung Maksimal: {data['max_hr']} bpm
    - Kalori Terbakar: {data['calories']} kcal

    Berikan analisis mendalam berdasar data di atas. Evaluasi zona jantungnya untuk usia tersebut.
    JANGAN gunakan markdown ```html. Gunakan <h3>, <p>, <ul>, <li>.
    """
    
    ai_response = model.generate_content(prompt)
    laporan = ai_response.text.replace("```html", "").replace("```", "").strip()

    return f'''
        <!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">{CSS_STYLE}</head><body>
        <div class="container">
            <div style="text-align: center;">
                <div class="badge" style="background: #EBF8FF; color: #3182CE;">ANALISIS .FIT</div>
                <h2 style="margin-top: 0; margin-bottom: 25px;">Data File Mentah</h2>
                <div class="stats-box"><p>{j_km} km | {w_mnt} mnt | HR {data['avg_hr']} bpm</p></div>
            </div>
            <div class="ai-content">{laporan}</div>
            <div class="actions">
                <a href="/" class="btn-primary" style="width: auto; padding: 12px 24px;">&larr; Kembali ke Beranda</a>
            </div>
        </div>
        </body></html>
    '''

# ==========================================
# RUTE 5: RIWAYAT LAPORAN
# ==========================================
@app.route('/riwayat')
def riwayat():
    athlete_id = session.get('athlete_id')
    if not athlete_id: return redirect('/')

    conn = sqlite3.connect('coach_data.db'); c = conn.cursor()
    c.execute("SELECT tanggal, tipe_analisis, laporan_html FROM reports WHERE athlete_id = ? ORDER BY id DESC", (athlete_id,))
    data_riwayat = c.fetchall()
    conn.close()

    html_riwayat = ""
    for baris in data_riwayat:
        isi = baris[2].replace("```html", "").replace("```", "").strip()
        html_riwayat += f'''
        <div style="background: white; border: 1px solid #e2e8f0; border-radius: 16px; padding: 25px; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.02);">
            <div class="badge" style="background: #edf2f7; color: #4a5568; margin-bottom: 15px;">{baris[0]} &bull; {baris[1]}</div>
            <div class="ai-content">{isi}</div>
        </div>
        '''

    if not html_riwayat: html_riwayat = "<p style='text-align:center;'>Belum ada riwayat laporan Strava.</p>"

    return f'''
        <!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">{CSS_STYLE}</head><body style="background: #f4f7f6;">
        <div class="container" style="background: transparent; box-shadow: none; padding-top: 10px;">
            <h2 style="text-align: center; color: #FC4C02;">Buku Harian Kebugaran</h2>
            <p style="text-align: center; color: #718096; margin-bottom: 40px;">Rekam jejak saran dari AI Coach Anda.</p>
            {html_riwayat}
            <div class="actions">
                <a href="/" class="btn-outline" style="background: white;">&larr; Kembali ke Beranda</a>
            </div>
        </div>
        </body></html>
    '''

if __name__ == '__main__':
    app.run(port=5000, debug=True)
