from flask import Flask, request, redirect, session
import requests
import google.generativeai as genai
from datetime import datetime
import time
import sqlite3
import os # <-- Tambahkan ini

app = Flask(__name__)
# Ambil secret key dari server, jika tidak ada pakai teks default
app.secret_key = os.environ.get('SECRET_KEY', 'kunci_rahasia_coach_ai_super_aman')

# --- KONFIGURASI AMAN (MENGAMBIL DARI BRANKAS SERVER) ---
STRAVA_CLIENT_ID = os.environ.get('STRAVA_CLIENT_ID')
STRAVA_CLIENT_SECRET = os.environ.get('STRAVA_CLIENT_SECRET')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')
REDIRECT_URI = 'https://ai-running-coach-m662.onrender.com/callback'

# --- CSS GLOBAL UNTUK UI PREMIUM ---
CSS_STYLE = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    body { font-family: 'Inter', sans-serif; background-color: #f4f7f6; color: #333; line-height: 1.6; margin: 0; padding: 20px; }
    .container { max-width: 700px; margin: 40px auto; background: #ffffff; padding: 40px; border-radius: 24px; box-shadow: 0 10px 40px rgba(0,0,0,0.08); }
    h2, h3, h4 { color: #1a202c; }
    .badge { display: inline-block; background: #FFF0E9; color: #FC4C02; padding: 6px 16px; border-radius: 20px; font-weight: 700; font-size: 0.85em; margin-bottom: 20px; letter-spacing: 0.5px;}
    .stats-box { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px; margin-bottom: 30px; text-align: center; }
    .stats-box p { margin: 0; font-size: 1.05em; font-weight: 600; color: #4a5568; }
    
    /* Styling khusus untuk konten AI agar rapi */
    .ai-content { color: #2d3748; font-size: 1.05em; }
    .ai-content h3, .ai-content h4 { border-bottom: 2px solid #edf2f7; padding-bottom: 10px; margin-top: 30px; color: #2c5282; }
    .ai-content ul { padding-left: 20px; }
    .ai-content li { margin-bottom: 10px; }
    .ai-content strong { color: #1a202c; }
    
    .btn-primary { background: #FC4C02; color: white; padding: 14px 28px; border-radius: 12px; text-decoration: none; font-weight: 600; display: inline-block; transition: 0.3s; width: 80%; max-width: 300px; text-align: center;}
    .btn-primary:hover { background: #e34302; transform: translateY(-2px); box-shadow: 0 4px 12px rgba(252, 76, 2, 0.3); }
    .btn-outline { background: transparent; color: #FC4C02; border: 2px solid #FC4C02; padding: 12px 26px; border-radius: 12px; text-decoration: none; font-weight: 600; display: inline-block; transition: 0.3s; margin-left: 10px;}
    .btn-outline:hover { background: #fff5f0; }
    .actions { text-align: center; margin-top: 40px; }
</style>
"""

def init_db():
    conn = sqlite3.connect('coach_data.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (athlete_id INTEGER PRIMARY KEY, age INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS reports (id INTEGER PRIMARY KEY AUTOINCREMENT, athlete_id INTEGER, tanggal TEXT, tipe_analisis TEXT, laporan_html TEXT)''')
    conn.commit()
    conn.close()
init_db()

@app.route('/')
def home():
    return f'''
        <!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">{CSS_STYLE}</head><body>
        <div class="container" style="text-align: center; max-width: 450px;">
            <h2 style="color: #FC4C02; font-size: 2em; margin-bottom: 10px;">AI Running Coach 40+</h2>
            <p style="color: #718096; margin-bottom: 30px;">Pendamping cerdas untuk pelari usia matang.</p>
            <form action="/login" method="GET">
                <input type="number" name="age" placeholder="Masukkan Umur Anda (Contoh: 56)" required 
                       style="padding: 15px; width: 80%; border-radius: 12px; border: 1px solid #cbd5e0; margin-bottom: 25px; font-size: 1.1em; text-align: center; outline: none;">
                <br>
                <button type="submit" class="btn-primary" style="width: 88%; border: none; cursor: pointer; font-size: 1.1em;">
                    Hubungkan & Analisis
                </button>
            </form>
        </div>
        </body></html>
    '''

@app.route('/login')
def login():
    age = request.args.get('age')
    # Mengambil URL otomatis (localhost atau url asli dari Render nanti)
    redirect_uri_dinamis = request.host_url + 'callback'
    
    auth_url = (f"https://www.strava.com/oauth/authorize?client_id={STRAVA_CLIENT_ID}"
                f"&response_type=code&redirect_uri={redirect_uri_dinamis}"
                f"&approval_prompt=force&scope=activity:read_all"
                f"&state={age}")
    return redirect(auth_url)

@app.route('/callback')
def callback():
    code = request.args.get('code')
    user_age = request.args.get('state')
    if not code: return "Akses ditolak."

    token_response = requests.post('https://www.strava.com/oauth/token', data={
        'client_id': STRAVA_CLIENT_ID, 'client_secret': STRAVA_CLIENT_SECRET, 'code': code, 'grant_type': 'authorization_code'
    }).json()
    
    if 'access_token' not in token_response: return f"Gagal masuk Strava. Error: {token_response}"
    access_token = token_response.get('access_token')
    athlete_id = token_response.get('athlete', {}).get('id')

    if athlete_id:
        session['athlete_id'] = athlete_id
        conn = sqlite3.connect('coach_data.db')
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO users (athlete_id, age) VALUES (?, ?)", (athlete_id, user_age))
        conn.commit(); conn.close()

    tahun_ini = datetime.now().year
    timestamp_after = int(time.mktime(datetime(tahun_ini, 1, 1).timetuple()))
    activities = requests.get(f'https://www.strava.com/api/v3/athlete/activities?after={timestamp_after}&per_page=200', headers={'Authorization': f'Bearer {access_token}'}).json()
    
    if isinstance(activities, dict) and 'message' in activities: return "Gagal menarik data Strava."

    hari_ini_str = datetime.now().strftime('%Y-%m-%d')
    aktivitas_hari_ini = [act for act in activities if act.get('start_date_local', '').startswith(hari_ini_str)]
    tipe_label = {'Run': '🏃 Lari', 'Swim': '🏊 Renang', 'Ride': '🚴 Sepeda', 'Walk': '🚶 Jalan', 'Hike': '🧗 Mendaki'}

    # Ekstraksi Data Historis untuk AI
    diary_lari, diary_renang, diary_lain = [], [], []
    for act in activities:
        t_asli = act.get('type')
        tgl = act.get('start_date_local', '')[:10]
        jarak = act.get('distance', 0) / 1000
        waktu = act.get('moving_time', 0) / 60
        hr = act.get('average_heartrate', 0)
        
        if t_asli == 'Run': diary_lari.append(f"Tgl {tgl}: Jarak {jarak:.1f}km, Waktu {waktu:.0f}mnt, AvgHR {hr}bpm")
        elif t_asli == 'Swim': diary_renang.append(f"Tgl {tgl}: Jarak {jarak*1000:.0f}m, Waktu {waktu:.0f}mnt")
        else: diary_lain.append(f"Tgl {tgl}: {t_asli} selama {waktu:.0f}mnt")

    teks_lari = '\n'.join(diary_lari) if diary_lari else "Tidak ada"
    teks_renang = '\n'.join(diary_renang) if diary_renang else "Tidak ada"

    if aktivitas_hari_ini:
        tipe_analisis = "Sesi Hari Ini"
        act_today = aktivitas_hari_ini[0]
        jarak_km = round(act_today.get('distance', 0) / 1000, 2)
        waktu_menit = round(act_today.get('moving_time', 0) / 60, 1)
        tipe_olahraga = act_today.get('type')
        tampilan_ui_teks = f"<b>{tipe_label.get(tipe_olahraga, tipe_olahraga)}</b> &bull; {jarak_km} km &bull; {waktu_menit} menit"
        
        prompt = f"""Kamu analis olahraga untuk usia {user_age} tahun. Hari ini klien melakukan {tipe_olahraga} ({jarak_km}km, {waktu_menit} mnt).
        Tulis evaluasi pemulihan. ATURAN KETAT: JANGAN gunakan markdown ```html. HANYA gunakan tag <h3>, <p>, <ul>, <li>, <strong>. DILARANG menggunakan inline style atau CSS kotak-kotak."""
    else:
        tipe_analisis = "Rekap YTD Komprehensif"
        rekap_ui = {}
        for act in activities:
            label = tipe_label.get(act.get('type'), '✨ Lain')
            rekap_ui[label] = rekap_ui.get(label, 0) + 1
        tampilan_ui_teks = " | ".join([f"<b>{k}</b>: {v}x" for k, v in rekap_ui.items()])
        
        prompt = f"""Kamu Sports Data Analyst untuk usia {user_age} tahun. Evaluasi data YTD ini:
        LARI: {teks_lari}
        RENANG: {teks_renang}
        
        ATURAN KETAT: 
        1. JANGAN gunakan tag markdown ```html. Jangan tulis kata html.
        2. HANYA gunakan tag HTML standar: <h3>, <h4>, <p>, <ul>, <li>, <strong>.
        3. DILARANG menggunakan styling inline (seperti style="..."), flexbox, tabel, atau kolom.
        4. Tulis dalam bentuk paragraf dan bullet points yang rapi dan mudah dibaca."""

    ai_response = model.generate_content(prompt)
    laporan_html = ai_response.text

    # --- PEMBERSIH MARKDOWN ---
    # Ini memastikan kata ```html hilang dari layar
    laporan_html = laporan_html.replace("```html", "").replace("```", "").strip()

    if athlete_id:
        conn = sqlite3.connect('coach_data.db'); c = conn.cursor()
        c.execute("INSERT INTO reports (athlete_id, tanggal, tipe_analisis, laporan_html) VALUES (?, ?, ?, ?)", (athlete_id, hari_ini_str, tipe_analisis, laporan_html))
        conn.commit(); conn.close()

    return f'''
        <!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">{CSS_STYLE}</head><body>
        <div class="container">
            <div style="text-align: center;">
                <div class="badge">ANALISIS PELATIH</div>
                <h2 style="margin-top: 0; margin-bottom: 25px;">{tipe_analisis}</h2>
                <div class="stats-box"><p>{tampilan_ui_teks}</p></div>
            </div>
            
            <div class="ai-content">
                {laporan_html}
            </div>
            
            <div class="actions">
                <a href="/riwayat" class="btn-primary" style="background:#2d3748; width: auto; padding: 12px 24px;">Lihat Riwayat</a>
                <a href="/" class="btn-outline">Cek Ulang</a>
            </div>
        </div>
        </body></html>
    '''

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
        # Bersihkan markdown juga untuk data riwayat agar tidak merusak tampilan
        isi = baris[2].replace("```html", "").replace("```", "").strip()
        html_riwayat += f'''
        <div style="background: white; border: 1px solid #e2e8f0; border-radius: 16px; padding: 25px; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.02);">
            <div class="badge" style="background: #edf2f7; color: #4a5568; margin-bottom: 15px;">{baris[0]} &bull; {baris[1]}</div>
            <div class="ai-content">{isi}</div>
        </div>
        '''

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
