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

# --- CSS GLOBAL ---
CSS_STYLE = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    body { font-family: 'Inter', sans-serif; background-color: #f4f7f6; color: #333; line-height: 1.6; margin: 0; padding: 20px; }
    .container { max-width: 700px; margin: 40px auto; background: #ffffff; padding: 40px; border-radius: 24px; box-shadow: 0 10px 40px rgba(0,0,0,0.08); }
    h2, h3, h4 { color: #1a202c; }
    .badge { display: inline-block; background: #FFF0E9; color: #FC4C02; padding: 6px 16px; border-radius: 20px; font-weight: 700; font-size: 0.85em; margin-bottom: 20px;}
    .stats-box { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px; margin-bottom: 30px; text-align: center; }
    .btn-primary { background: #FC4C02; color: white; padding: 14px 28px; border-radius: 12px; text-decoration: none; font-weight: 600; display: inline-block; border: none; cursor: pointer; text-align: center;}
    .btn-outline { background: transparent; color: #FC4C02; border: 2px solid #FC4C02; padding: 12px 26px; border-radius: 12px; text-decoration: none; font-weight: 600; display: inline-block; margin-left: 10px;}
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
            <form action="/login" method="GET">
                <input type="number" name="age" placeholder="Umur Anda" required style="padding: 15px; width: 80%; border-radius: 12px; border: 1px solid #cbd5e0; margin-bottom: 15px; text-align: center;">
                <button type="submit" class="btn-primary" style="width: 88%;">Hubungkan Strava</button>
            </form>
            <div class="upload-section">
                <h4 style="margin-top: 0;">Analisis File .FIT</h4>
                <form action="/upload" method="POST" enctype="multipart/form-data">
                    <input type="number" name="age" placeholder="Umur" required style="width: 80%; padding: 10px; border-radius: 8px; border: 1px solid #cbd5e0; margin-bottom: 10px; text-align: center;">
                    <input type="file" name="file_fit" accept=".fit" required style="margin-bottom: 15px;">
                    <button type="submit" style="background: #2d3748; color: white; padding: 12px; border-radius: 8px; cursor: pointer; border: none; width: 85%; font-weight: bold;">Upload & Bedah Data</button>
                </form>
            </div>
            <div style="margin-top: 25px;"><a href="/riwayat" style="color: #2b6cb0; text-decoration: none; font-weight: bold;">Lihat Riwayat &rarr;</a></div>
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
    if not code: 
        return "Akses ditolak."

    token_response = requests.post('https://www.strava.com/oauth/token', data={'client_id': STRAVA_CLIENT_ID, 'client_secret': STRAVA_CLIENT_SECRET, 'code': code, 'grant_type': 'authorization_code'}).json()
    if 'access_token' not in token_response: 
        return f"Gagal masuk Strava."
    
    access_token = token_response.get('access_token')
    athlete_id = token_response.get('athlete', {}).get('id')

    if athlete_id:
        session['athlete_id'] = athlete_id
        conn = sqlite3.connect('coach_data.db')
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO users (athlete_id, age) VALUES (?, ?)", (athlete_id, user_age))
        conn.commit()
        conn.close()

    tahun_ini = datetime.now().year
    timestamp_after = int(time.mktime(datetime(tahun_ini, 1, 1).timetuple()))
    activities = requests.get(f'https://www.strava.com/api/v3/athlete/activities?after={timestamp_after}&per_page=200', headers={'Authorization': f'Bearer {access_token}'}).json()
    
    hari_ini_str = datetime.now().strftime('%Y-%m-%d')
    aktivitas_hari_ini = [act for act in activities if act.get('start_date_local', '').startswith(hari_ini_str)]
    
    if aktivitas_hari_ini:
        tipe_analisis = f"Sesi Hari Ini ({len(aktivitas_hari_ini)} Aktivitas)"
        teks_untuk_ai = "\n".join([f"- {act.get('type')}: {round(act.get('distance',0)/1000,2)}km, {round(act.get('moving_time',0)/60,1)}mnt, HR {act.get('average_heartrate',0)}bpm" for act in aktivitas_hari_ini])
        
        prompt = f"""
        PERANMU: Kamu adalah "AI Coach", sistem cerdas tanpa umur. Klienmu berusia {user_age} tahun.
        Data Strava: {teks_untuk_ai}
        TUGAS: Buat "INFOGRAFIS HTML". DILARANG menggunakan markdown/tanda bintang. Gunakan template HTML ini:
        <div style="background: #ffffff; border-left: 5px solid #3182CE; padding: 18px; margin-bottom: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.05);"><h3 style="margin-top: 0; color: #2c5282;">🏃‍♂️ Performa</h3><p>...</p></div>
        <div style="background: #ffffff; border-left: 5px solid #E53E3E; padding: 18px; margin-bottom: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.05);"><h3 style="margin-top: 0; color: #9B2C2C;">❤️ Jantung</h3><p>...</p></div>
        <div style="background: #ffffff; border-left: 5px solid #D69E2E; padding: 18px; margin-bottom: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.05);"><h3 style="margin-top: 0; color: #975A16;">🛡️ Evaluasi</h3><p>...</p></div>
        <div style="background: #ffffff; border-left: 5px solid #38A169; padding: 18px; margin-bottom: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.05);"><h3 style="margin-top: 0; color: #22543D;">💪 Strength</h3><p>...</p><ul><li>...</li></ul></div>
        """
    else:
        tipe_analisis = "Rekap YTD"
        prompt = f"Klien usia {user_age}. Evaluasi YTD. JANGAN pakai markdown. Gunakan HTML <h3> dan <ul>."

    try:
        ai_response = model.generate_content(prompt)
        laporan_html = ai_response.text.replace("```html", "").replace("```", "").strip()
    except Exception as e:
        return f"<h1>ERROR AI:</h1><p>{str(e)}</p>"

    return f'''
        <!DOCTYPE html><html><head><meta charset="UTF-8">{CSS_STYLE}</head><body>
        <div class="container">
            <h2 style="text-align: center;">{tipe_analisis}</h2>
            <div>{laporan_html}</div>
            <div class="actions"><a href="/" class="btn-outline">Kembali</a></div>
        </div>
        </body></html>
    '''

@app.route('/upload', methods=['POST'])
def upload_file():
    user_age = request.form.get('age') or "50"
    file = request.files.get('file_fit')
    if not file: 
        return "File tidak ditemukan."
    
    temp_path = "temp_activity.fit"
    file.save(temp_path)
    data = parse_fit_data(temp_path)
    if os.path.exists(temp_path): 
        os.remove(temp_path)
    
    if isinstance(data, str): 
        return f"Gagal membedah: {data}"

    j_km = round(data['distance_m'] / 1000, 2)
    w_mnt = round(data['duration_m'], 1)

    prompt = f"""
    PERANMU: Kamu adalah "AI Coach", sistem cerdas tanpa umur. Klienmu berusia {user_age} tahun.
    Data FIT: {data['type']}, {j_km}km, {w_mnt}mnt, HR {data['avg_hr']}bpm.
    TUGAS: Buat "INFOGRAFIS HTML". DILARANG menggunakan markdown/tanda bintang. Gunakan template HTML ini:
    <div style="background: #ffffff; border-left: 5px solid #3182CE; padding: 18px; margin-bottom: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.05);"><h3 style="margin-top: 0; color: #2c5282;">🏃‍♂️ Performa</h3><p>...</p></div>
    <div style="background: #ffffff; border-left: 5px solid #E53E3E; padding: 18px; margin-bottom: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.05);"><h3 style="margin-top: 0; color: #9B2C2C;">❤️ Jantung</h3><p>...</p></div>
    <div style="background: #ffffff; border-left: 5px solid #D69E2E; padding: 18px; margin-bottom: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.05);"><h3 style="margin-top: 0; color: #975A16;">🛡️ Evaluasi</h3><p>...</p></div>
    <div style="background: #ffffff; border-left: 5px solid #38A169; padding: 18px; margin-bottom: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.05);"><h3 style="margin-top: 0; color: #22543D;">💪 Strength</h3><p>...</p><ul><li>...</li></ul></div>
    """
    
    try:
        ai_response = model.generate_content(prompt)
        laporan = ai_response.text.replace("```html", "").replace("```", "").strip()
    except Exception as e:
        return f"<h1>ERROR AI:</h1><p>{str(e)}</p>"

    tombol_download = f'''
        <a href="/download_card?jarak={j_km}&waktu={w_mnt}&hr={data['avg_hr']}&tipe={data['type']}" 
           class="btn-primary" style="background: #3182CE; padding: 12px 24px;">
           📸 Download Kartu IG
        </a>
    '''

    return f'''
        <!DOCTYPE html><html><head><meta charset="UTF-8">{CSS_STYLE}</head><body>
        <div class="container">
            <h2 style="text-align: center;">Analisis File Mentah</h2>
            <div>{laporan}</div>
            <div class="actions">
                <a href="/" class="btn-outline" style="margin-right: 10px;">Kembali</a>
                {tombol_download}
            </div>
        </div>
        </body></html>
    '''

@app.route('/download_card')
def download_card():
    j_km = request.args.get('jarak', '0')
    w_mnt = request.args.get('waktu', '0')
    hr = request.args.get('hr', '0')
    tipe = request.args.get('tipe', 'LARI')

    img = Image.new('RGB', (800, 1200), color='#1A202C')
    draw = ImageDraw.Draw(img)

    font_url = "https://github.com/googlefonts/roboto/raw/main/src/hinted/Roboto-Bold.ttf"
    if not os.path.exists("Roboto-Bold.ttf"):
        try: 
            urllib.request.urlretrieve(font_url, "Roboto-Bold.ttf")
        except: 
            pass
    
    try:
        font_title = ImageFont.truetype("Roboto-Bold.ttf", 60)
        font_label = ImageFont.truetype("Roboto-Bold.ttf", 35)
        font_value = ImageFont.truetype("Roboto-Bold.ttf", 100)
    except:
        font_title = font_label = font_value = ImageFont.load_default()

    draw.rectangle([(50, 50), (750, 180)], fill='#FC4C02')
    draw.text((90, 85), f"AI COACH SUMMARY", fill="white", font=font_title)
    draw.text((50, 240), f"AKTIVITAS: {tipe.upper()}", fill="#A0AEC0", font=font_label)
    draw.line([(50, 300), (750, 300)], fill="#4A5568", width=3)
    
    draw.text((50, 350), "JARAK (KM)", fill="#FC4C02", font=font_label)
    draw.text((50, 400), f"{j_km}", fill="white", font=font_value)
    
    draw.text((50, 600), "WAKTU (MENIT)", fill="#3182CE", font=font_label)
    draw.text((50, 650), f"{w_mnt}", fill="white", font=font_value)
    
    draw.text((50, 850), "AVG HEART RATE", fill="#E53E3E", font=font_label)
    draw.text((50, 900), f"{hr} BPM", fill="white", font=font_value)

    draw.rectangle([(0, 1100), (800, 1200)], fill='#2D3748')
    draw.text((180, 1130), "Generated by AI Coach 40+ 🚀", fill="#CBD5E0", font=font_label)

    img_io = io.BytesIO()
    img.save(img_io, 'JPEG', quality=85)
    img_io.seek(0)
    return send_file(img_io, mimetype='image/jpeg', as_attachment=True, download_name=f'AI_Coach_{tipe}.jpg')

@app.route('/riwayat')
def riwayat():
    return "<div style='text-align:center; padding: 50px;'>Fitur Riwayat Aktif. <a href='/'>Kembali</a></div>"

if __name__ == '__main__':
    app.run(port=5000, debug=True)
