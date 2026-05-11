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
        
       prompt = f"""
        PERANMU: Kamu adalah "AI Coach", sistem cerdas tanpa umur. 
        Klienmu adalah manusia berusia {user_age} tahun.

        Hari ini klien melakukan sesi olahraga berikut (Data Strava):
        {teks_untuk_ai}

        TUGAS UTAMA: Buatlah analisis berwujud "INFOGRAFIS HTML" yang sangat visual.
        
        ATURAN KETAT (PENTING!):
        1. DILARANG KERAS menggunakan tanda bintang (**) atau Markdown. Gunakan <b> atau <strong>.
        2. JANGAN PERNAH menyebutkan umurmu sendiri. Fokus pada usia klien ({user_age} tahun).
        3. GUNAKAN IKON EMOTICON di setiap judul.
        4. WAJIB gunakan format HTML Kartu berwarna di bawah ini:

        <div style="background: #ffffff; border-left: 5px solid #3182CE; padding: 18px; margin-bottom: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.05);">
            <h3 style="margin-top: 0; color: #2c5282;">🏃‍♂️ Ringkasan Performa</h3>
            <p>... (Analisis pace dan durasi lari klien hari ini) ...</p>
        </div>

        <div style="background: #ffffff; border-left: 5px solid #E53E3E; padding: 18px; margin-bottom: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.05);">
            <h3 style="margin-top: 0; color: #9B2C2C;">❤️ Analisis Jantung</h3>
            <p>... (Hitung HR Max klien: 220 - {user_age}. Evaluasi rata-rata HR {hr_avg} bpm masuk zona apa) ...</p>
        </div>

        <div style="background: #ffffff; border-left: 5px solid #D69E2E; padding: 18px; margin-bottom: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.05);">
            <h3 style="margin-top: 0; color: #975A16;">🛡️ Evaluasi & Pemulihan</h3>
            <p>... (Beri tahu apakah sesi hari ini aman untuk dirutinkan bagi pelari {user_age} tahun atau butuh istirahat) ...</p>
        </div>

        <div style="background: #ffffff; border-left: 5px solid #38A169; padding: 18px; margin-bottom: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.05);">
            <h3 style="margin-top: 0; color: #22543D;">💪 Strength Training Khusus</h3>
            <p>Untuk menjaga otot dan sendi usia {user_age}+, lakukan 3 gerakan ini:</p>
            <ul>
                <li><b>1. Gerakan Nama:</b> Penjelasan singkat cara dan manfaat.</li>
                <li><b>2. Gerakan Nama:</b> Penjelasan singkat cara dan manfaat.</li>
                <li><b>3. Gerakan Nama:</b> Penjelasan singkat cara dan manfaat.</li>
            </ul>
        </div>
        """
    
    else:
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
        
        prompt = f"""Kamu adalah AI Sports Analyst. Klienmu berusia {user_age} tahun. Evaluasi data YTD ini:
        LARI: {teks_lari}
        RENANG: {teks_renang}
        ATURAN KETAT: JANGAN gunakan markdown ```html. Gunakan HTML standar <h3>, <p>, <ul>, <li>."""

    try:
        ai_response = model.generate_content(prompt)
        laporan_html = ai_response.text.replace("```html", "").replace("```", "").strip()
    except Exception as e:
        return f"<h1>SERVER MENGAKU ERROR:</h1><p>{str(e)}</p>"

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

@app.route('/upload', methods=['POST'])
def upload_file():
    user_age = request.form.get('age') or "50"
    file = request.files.get('file_fit')
    
    if not file: return "File tidak ditemukan."
    
    temp_path = "temp_activity.fit"
    file.save(temp_path)
    
    data = parse_fit_data(temp_path)
    
    if os.path.exists(temp_path): os.remove(temp_path)

    if isinstance(data, str): 
        return f"Maaf, gagal membedah data: {data}"

    j_km = round(data['distance_m'] / 1000, 2)
    w_mnt = round(data['duration_m'], 1)

    prompt = f"""
    PERANMU SANGAT JELAS: Kamu adalah "AI Coach", sebuah sistem kecerdasan buatan. KAMU BUKAN MANUSIA DAN TIDAK MEMILIKI UMUR.
    Pengguna yang datanya kamu analisis adalah manusia berusia {user_age} tahun.

    Klien mengupload file aktivitas dengan data berikut:
    - Olahraga: {data['type']}
    - Jarak: {j_km} km
    - Durasi: {w_mnt} menit
    - HR Rata-rata: {data['avg_hr']} bpm
    - HR Maksimal: {data['max_hr']} bpm

    TUGAS UTAMA: Buatlah analisis berwujud "INFOGRAFIS HTML".
    
    ATURAN KETAT (JIKA DILANGGAR SISTEM AKAN ERROR):
    1. DILARANG KERAS menggunakan tanda bintang (**) atau Markdown apa pun. Gunakan HANYA tag HTML <b> atau <strong>.
    2. JANGAN PERNAH menyebutkan umurmu. Sebutkan usia klien ({user_age} tahun) dalam analisismu.
    3. WAJIB gunakan format HTML di bawah ini persis sebagai template jawabanmu:

    <div style="background: #ffffff; border-left: 5px solid #3182CE; padding: 18px; margin-bottom: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.05);">
        <h3 style="margin-top: 0; color: #2c5282;">🏃‍♂️ Ringkasan Kinerja</h3>
        <p>... (berikan evaluasi efisiensi pace dan durasi di sini) ...</p>
    </div>

    <div style="background: #ffffff; border-left: 5px solid #E53E3E; padding: 18px; margin-bottom: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.05);">
        <h3 style="margin-top: 0; color: #9B2C2C;">❤️ Analisis Zona Jantung</h3>
        <p>... (Hitung HR Max klien: 220 - {user_age}. Jelaskan angka {data['avg_hr']} bpm masuk zona apa untuknya) ...</p>
    </div>

    <div style="background: #ffffff; border-left: 5px solid #D69E2E; padding: 18px; margin-bottom: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.05);">
        <h3 style="margin-top: 0; color: #975A16;">🛡️ Evaluasi Keamanan</h3>
        <p>... (Jelaskan apakah ini sesi Easy, Tempo, atau Hard. Apakah aman dilakukan sering-sering?) ...</p>
    </div>

    <div style="background: #ffffff; border-left: 5px solid #38A169; padding: 18px; margin-bottom: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.05);">
        <h3 style="margin-top: 0; color: #22543D;">💪 Panduan Strength Training (Usia {user_age}+)</h3>
        <p>Untuk menunjang lari dan mencegah cedera di usia ini, lakukan 3 gerakan ramah sendi berikut:</p>
        <ul>
            <li><b>Gerakan 1:</b> ... (Sebutkan nama dan cara singkat) ...</li>
            <li><b>Gerakan 2:</b> ... (Sebutkan nama dan cara singkat) ...</li>
            <li><b>Gerakan 3:</b> ... (Sebutkan nama dan cara singkat) ...</li>
        </ul>
    </div>
    """
    
    try:
        ai_response = model.generate_content(prompt)
        laporan = ai_response.text.replace("```html", "").replace("```", "").strip()
    except Exception as e:
        return f"<h1>SERVER MENGAKU ERROR:</h1><p>{str(e)}</p>"

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
