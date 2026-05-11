import os
from flask import Flask, request, redirect, session, send_file
import requests
import google.generativeai as genai
from datetime import datetime
import time
import sqlite3
from fitparse import FitFile
from PIL import Image, ImageDraw, ImageFont
import io
import urllib.request

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'kunci_rahasia_coach_ai_super_aman')

# --- KONFIGURASI API ---
STRAVA_CLIENT_ID = os.environ.get('STRAVA_CLIENT_ID')
STRAVA_CLIENT_SECRET = os.environ.get('STRAVA_CLIENT_SECRET')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

def init_db():
    conn = sqlite3.connect('coach_data.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (athlete_id INTEGER PRIMARY KEY, age INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS reports (id INTEGER PRIMARY KEY AUTOINCREMENT, athlete_id INTEGER, tanggal TEXT, tipe_analisis TEXT, laporan_html TEXT)''')
    conn.commit()
    conn.close()

init_db()

def parse_fit_data(file_path):
    try:
        fitfile = FitFile(file_path)
        data_ringkas = {
            "type": "Aktivitas", "distance_m": 0, "duration_m": 0,
            "avg_hr": 0, "max_hr": 0, "calories": 0
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

# --- CSS SUPER UI/UX ---
CSS_STYLE = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700;800&display=swap');
    body { font-family: 'Poppins', sans-serif; background-color: #f0f4f8; color: #334155; line-height: 1.6; margin: 0; padding: 20px; }
    .container { max-width: 900px; margin: 0 auto; }
    
    /* Tampilan Header Mewah */
    .header-banner { background: linear-gradient(135deg, #1e293b, #0f172a); color: white; text-align: center; padding: 40px 20px; border-radius: 24px; margin-bottom: 30px; box-shadow: 0 10px 25px rgba(0,0,0,0.1); position: relative; overflow: hidden; }
    .header-banner h2 { margin: 0; font-size: 2.5em; font-weight: 800; letter-spacing: 1px; color: #f8fafc; text-transform: uppercase; }
    .header-banner p { margin: 10px 0 0; color: #94a3b8; font-size: 1.1em; }
    .header-banner::after { content: ''; position: absolute; top: -50px; right: -50px; width: 150px; height: 150px; background: rgba(255,255,255,0.05); border-radius: 50%; }

    /* CSS Grid untuk Layout Kartu 2x2 */
    .info-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 25px; margin-bottom: 30px; }

    /* Desain Kartu / Panel */
    .info-card { background: #ffffff; border-radius: 20px; padding: 25px; box-shadow: 0 10px 30px rgba(0,0,0,0.04); border: 1px solid #e2e8f0; transition: transform 0.3s ease; }
    .info-card:hover { transform: translateY(-5px); box-shadow: 0 15px 35px rgba(0,0,0,0.08); }
    
    /* Judul Setiap Kartu dengan Garis Bawah */
    .info-card h3 { margin-top: 0; font-size: 1.5em; display: flex; align-items: center; gap: 10px; padding-bottom: 15px; border-bottom: 2px dashed #e2e8f0; margin-bottom: 20px; text-transform: uppercase; font-weight: 800; }
    
    /* Warna Tematik per Kartu */
    .card-performa h3 { color: #0284c7; } /* Biru */
    .card-jantung h3 { color: #e11d48; }  /* Merah */
    .card-evaluasi h3 { color: #ca8a04; } /* Kuning Gelap */
    .card-strength h3 { color: #16a34a; } /* Hijau */

    /* Highlight Data Angka */
    .data-row { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; font-size: 1.1em; background: #f8fafc; padding: 10px 15px; border-radius: 12px; }
    .data-value { font-weight: 800; color: #0f172a; font-size: 1.2em; }
    .info-card ul { padding-left: 20px; margin-top: 10px; }
    .info-card li { margin-bottom: 10px; }

    /* Tombol */
    .btn-primary { background: #FC4C02; color: white; padding: 14px 28px; border-radius: 12px; text-decoration: none; font-weight: 700; display: inline-block; border: none; cursor: pointer; text-align: center; box-shadow: 0 4px 6px rgba(252,76,2,0.3); }
    .btn-outline { background: white; color: #1e293b; border: 2px solid #cbd5e0; padding: 12px 26px; border-radius: 12px; text-decoration: none; font-weight: 700; display: inline-block; margin-right: 10px; }
    .actions { text-align: center; margin-top: 40px; padding-bottom: 40px; }
    
    /* Tampilan Halaman Utama */
    .home-card { max-width: 450px; margin: 40px auto; background: white; padding: 40px; border-radius: 24px; box-shadow: 0 10px 40px rgba(0,0,0,0.08); text-align: center; }
    .upload-section { border: 2px dashed #cbd5e0; padding: 25px; border-radius: 16px; margin-top: 35px; background: #f8fafc; }
</style>
"""

@app.route('/')
def home():
    return f'''
        <!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">{CSS_STYLE}</head><body>
        <div class="home-card">
            <h2 style="color: #FC4C02; font-size: 2.5em; margin-bottom: 5px; font-weight: 800;">AI Coach</h2>
            <p style="color: #64748b; margin-bottom: 30px;">Analisis Lari Profesional untuk Usia 40+</p>
            <form action="/login" method="GET">
                <input type="number" name="age" placeholder="Umur Anda (Misal: 56)" required style="padding: 15px; width: 80%; border-radius: 12px; border: 1px solid #cbd5e0; margin-bottom: 15px; text-align: center; font-size: 1.1em;">
                <button type="submit" class="btn-primary" style="width: 88%; font-size: 1.1em;">Hubungkan Strava</button>
            </form>
            <div class="upload-section">
                <h4 style="margin-top: 0; color: #334155;">Analisis File Mentah (.FIT)</h4>
                <form action="/upload" method="POST" enctype="multipart/form-data">
                    <input type="number" name="age" placeholder="Umur" required style="width: 80%; padding: 10px; border-radius: 8px; border: 1px solid #cbd5e0; margin-bottom: 10px; text-align: center;">
                    <input type="file" name="file_fit" accept=".fit" required style="margin-bottom: 15px;">
                    <button type="submit" style="background: #1e293b; color: white; padding: 12px; border-radius: 8px; cursor: pointer; border: none; width: 85%; font-weight: bold;">Upload & Bedah Data</button>
                </form>
            </div>
            <div style="margin-top: 25px;"><a href="/riwayat" style="color: #2b6cb0; text-decoration: none; font-weight: bold;">Lihat Buku Harian &rarr;</a></div>
        </div>
        </body></html>
    '''

@app.route('/login')
def login():
    age = request.args.get('age')
    redirect_uri_dinamis = request.host_url + 'callback'
    if "localhost" not in redirect_uri_dinamis: 
        redirect_uri_dinamis = redirect_uri_dinamis.replace("http://", "https://")
    return redirect(f"https://www.strava.com/oauth/authorize?client_id={STRAVA_CLIENT_ID}&response_type=code&redirect_uri={redirect_uri_dinamis}&approval_prompt=force&scope=activity:read_all&state={age}")

@app.route('/callback')
def callback():
    code = request.args.get('code')
    user_age = request.args.get('state')
    if not code: return "Akses ditolak."

    token_response = requests.post('https://www.strava.com/oauth/token', data={'client_id': STRAVA_CLIENT_ID, 'client_secret': STRAVA_CLIENT_SECRET, 'code': code, 'grant_type': 'authorization_code'}).json()
    if 'access_token' not in token_response: return f"Gagal masuk Strava."
    
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
    
    hari_ini_str = datetime.now().strftime('%Y-%m-%d')
    aktivitas_hari_ini = [act for act in activities if act.get('start_date_local', '').startswith(hari_ini_str)]
    
    if aktivitas_hari_ini:
        tipe_analisis = f"ANALISIS STRAVA HARI INI"
        teks_untuk_ai = "\n".join([f"- {act.get('type')}: {round(act.get('distance',0)/1000,2)}km, {round(act.get('moving_time',0)/60,1)}mnt, HR {act.get('average_heartrate',0)}bpm" for act in aktivitas_hari_ini])
        
        prompt = f"""
        PERANMU: Kamu adalah "AI Coach", sistem cerdas tanpa umur. Klienmu berusia {user_age} tahun.
        Data Strava: {teks_untuk_ai}
        TUGAS: Buat "INFOGRAFIS HTML". DILARANG menggunakan markdown/tanda bintang. 
        WAJIB gunakan struktur HTML ini PERSIS (Isi bagian ... dengan analisismu):

        <div class="info-grid">
            <div class="info-card card-performa">
                <h3>🏃‍♂️ PERFORMA</h3>
                <p>... (Analisis performa pace dan jarak) ...</p>
            </div>
            <div class="info-card card-jantung">
                <h3>❤️ JANTUNG</h3>
                <div class="data-row">📈 <span>Max HR Klien: <span class="data-value">... bpm</span> (220-{user_age})</span></div>
                <p>... (Evaluasi zona jantung) ...</p>
            </div>
            <div class="info-card card-evaluasi">
                <h3>🛡️ EVALUASI</h3>
                <p>... (Kesimpulan tingkat keamanan dan pemulihan) ...</p>
            </div>
            <div class="info-card card-strength">
                <h3>💪 STRENGTH</h3>
                <p>Latihan beban tanpa melompat untuk pelari matang:</p>
                <ul>
                    <li><b>Gerakan 1:</b> ...</li>
                    <li><b>Gerakan 2:</b> ...</li>
                </ul>
            </div>
        </div>
        """
    else:
        tipe_analisis = "REKAP TAHUN INI"
        prompt = f"Klien usia {user_age}. Evaluasi YTD. JANGAN pakai markdown. Gunakan HTML <h3> dan <ul>."

    try:
        ai_response = model.generate_content(prompt)
        laporan_html = ai_response.text.replace("```html", "").replace("```", "").strip()
    except Exception as e:
        return f"<h1>ERROR AI:</h1><p>{str(e)}</p>"

    return f'''
        <!DOCTYPE html><html><head><meta charset="UTF-8">{CSS_STYLE}</head><body>
        <div class="container">
            <div class="header-banner">
                <h2>{tipe_analisis}</h2>
                <p>Menganalisis performa berdasarkan usia {user_age} tahun</p>
            </div>
            {laporan_html}
            <div class="actions">
                <a href="/" class="btn-outline">Kembali ke Menu</a>
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
    if isinstance(data, str): return f"Gagal membedah: {data}"

    j_km = round(data['distance_m'] / 1000, 2)
    w_mnt = round(data['duration_m'], 1)

    prompt = f"""
    PERANMU: Kamu adalah "AI Coach", sistem cerdas tanpa umur. Klienmu berusia {user_age} tahun.
    Data FIT: {data['type']}, Jarak {j_km} km, Waktu {w_mnt} menit, HR {data['avg_hr']} bpm.
    TUGAS: Buat "INFOGRAFIS HTML". DILARANG menggunakan markdown/tanda bintang. 
    WAJIB gunakan struktur HTML ini PERSIS TANPA DIUBAH KELASNYA:

    <div class="info-grid">
        <div class="info-card card-performa">
            <h3>🏃‍♂️ PERFORMA</h3>
            <div class="data-row">📏 <span>Jarak: <span class="data-value">{j_km} km</span></span></div>
            <div class="data-row">⏳ <span>Waktu: <span class="data-value">{w_mnt} mnt</span></span></div>
            <p>... (Berikan pujian/analisis pace di sini) ...</p>
        </div>

        <div class="info-card card-jantung">
            <h3>❤️ JANTUNG</h3>
            <div class="data-row">💓 <span>HR Rata-rata: <span class="data-value">{data['avg_hr']} bpm</span></span></div>
            <div class="data-row">📈 <span>Max HR Klien: <span class="data-value">... bpm</span> (220-{user_age})</span></div>
            <p>... (Evaluasi zona latihan ini) ...</p>
        </div>

        <div class="info-card card-evaluasi">
            <h3>🛡️ EVALUASI</h3>
            <p>... (Kesimpulan aman/tidak dilakukan sering, butuh rest day/tidak) ...</p>
        </div>

        <div class="info-card card-strength">
            <h3>💪 STRENGTH</h3>
            <p>Optimasi forma & keselamatan otot (usia {user_age}+):</p>
            <ul>
                <li><b>Gerakan 1:</b> ...</li>
                <li><b>Gerakan 2:</b> ...</li>
                <li><b>Gerakan 3:</b> ...</li>
            </ul>
        </div>
    </div>
    """
    
    try:
        ai_response = model.generate_content(prompt)
        laporan = ai_response.text.replace("```html", "").replace("```", "").strip()
    except Exception as e:
        return f"<h1>ERROR AI:</h1><p>{str(e)}</p>"

    # Kita simpan tombol Pillow IG untuk jaga-jaga, tapi kita taruh di bawah
    tombol_download = f'''
        <a href="/download_card?jarak={j_km}&waktu={w_mnt}&hr={data['avg_hr']}&tipe={data['type']}" 
           class="btn-primary">📸 Unduh Kartu IG Basic</a>
    '''

    return f'''
        <!DOCTYPE html><html><head><meta charset="UTF-8">{CSS_STYLE}</head><body>
        <div class="container">
            <div class="header-banner">
                <h2>ANALISIS FILE MENTAH</h2>
                <p>Data Akurasi Tinggi | Klien Usia {user_age} Tahun</p>
            </div>
            {laporan}
            <div class="actions">
                <a href="/" class="btn-outline">Kembali ke Menu</a>
                {tombol_download}
            </div>
        </div>
        </body></html>
    '''

@app.route('/download_card')
def download_card():
    # Rute cadangan untuk generate Pillow (dibiarkan tetap hidup)
    j_km = request.args.get('jarak', '0')
    w_mnt = request.args.get('waktu', '0')
    hr = request.args.get('hr', '0')
    tipe = request.args.get('tipe', 'LARI')
    img = Image.new('RGB', (800, 1200), color='#1A202C')
    draw = ImageDraw.Draw(img)
    font_url = "https://github.com/googlefonts/roboto/raw/main/src/hinted/Roboto-Bold.ttf"
    if not os.path.exists("Roboto-Bold.ttf"):
        try: urllib.request.urlretrieve(font_url, "Roboto-Bold.ttf")
        except: pass
    try: font_title = ImageFont.truetype("Roboto-Bold.ttf", 60); font_label = ImageFont.truetype("Roboto-Bold.ttf", 35); font_value = ImageFont.truetype("Roboto-Bold.ttf", 100)
    except: font_title = font_label = font_value = ImageFont.load_default()
    draw.rectangle([(50, 50), (750, 180)], fill='#FC4C02'); draw.text((90, 85), f"AI COACH SUMMARY", fill="white", font=font_title)
    draw.text((50, 240), f"AKTIVITAS: {tipe.upper()}", fill="#A0AEC0", font=font_label); draw.line([(50, 300), (750, 300)], fill="#4A5568", width=3)
    draw.text((50, 350), "JARAK (KM)", fill="#FC4C02", font=font_label); draw.text((50, 400), f"{j_km}", fill="white", font=font_value)
    draw.text((50, 600), "WAKTU (MENIT)", fill="#3182CE", font=font_label); draw.text((50, 650), f"{w_mnt}", fill="white", font=font_value)
    draw.text((50, 850), "AVG HEART RATE", fill="#E53E3E", font=font_label); draw.text((50, 900), f"{hr} BPM", fill="white", font=font_value)
    draw.rectangle([(0, 1100), (800, 1200)], fill='#2D3748'); draw.text((180, 1130), "Generated by AI Coach 40+ 🚀", fill="#CBD5E0", font=font_label)
    img_io = io.BytesIO()
    img.save(img_io, 'JPEG', quality=85)
    img_io.seek(0)
    return send_file(img_io, mimetype='image/jpeg', as_attachment=True, download_name=f'AI_Coach_{tipe}.jpg')

@app.route('/riwayat')
def riwayat():
    return "<div style='text-align:center; padding: 50px; font-family: sans-serif;'>Fitur Riwayat Aktif. <br><br><a href='/' style='color:#FC4C02;'>Kembali</a></div>"

if __name__ == '__main__':
    app.run(port=5000, debug=True)
