import os
from flask import Flask, request, redirect, session, render_template_string
import requests
import google.generativeai as genai
from datetime import datetime
import time
import sqlite3
from fitparse import FitFile # <-- Library baru untuk bedah file Garmin

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'kunci_rahasia_coach_ai_super_aman')

# --- KONFIGURASI (GANTI DENGAN DATA KAMU) ---
STRAVA_CLIENT_ID = '238033'
STRAVA_CLIENT_SECRET = 'a4232274aaa68d05b8832d931b9620136780a647'
GEMINI_API_KEY = 'AIzaSyAri81jKrN3XqbarvbC-nLqTmA3zuhb3v4'

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

# --- FUNGSI BEDAH FILE .FIT ---
def parse_fit_data(file_path):
    try:
        fitfile = FitFile(file_path)
        data_ringkas = {
            "type": "Aktivitas Luar",
            "distance_m": 0,
            "duration_m": 0,
            "avg_hr": 0,
            "max_hr": 0,
            "calories": 0,
            "recovery_time": 0 # Data recovery sering ada di file Garmin
        }
        
        hr_list = []
        for record in fitfile.get_messages('session'):
            for data in record:
                if data.name == 'total_distance': data_ringkas['distance_m'] = data.value
                if data.name == 'total_timer_time': data_ringkas['duration_m'] = data.value / 60
                if data.name == 'avg_heart_rate': data_ringkas['avg_hr'] = data.value
                if data.name == 'max_heart_rate': data_ringkas['max_hr'] = data.value
                if data.name == 'total_calories': data_ringkas['calories'] = data.value
                if data.name == 'sport': data_ringkas['type'] = data.value

        return data_ringkas
    except Exception as e:
        return f"Error bedah file: {str(e)}"

# --- CSS (Ditambah gaya untuk Form Upload) ---
CSS_STYLE = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    body { font-family: 'Inter', sans-serif; background-color: #f4f7f6; color: #333; padding: 20px; }
    .container { max-width: 700px; margin: 40px auto; background: #fff; padding: 40px; border-radius: 24px; box-shadow: 0 10px 40px rgba(0,0,0,0.08); }
    .btn-primary { background: #FC4C02; color: white; padding: 14px 28px; border-radius: 12px; text-decoration: none; font-weight: 600; display: block; width: 100%; border: none; cursor: pointer; margin-top: 10px;}
    .upload-section { border: 2px dashed #cbd5e0; padding: 20px; border-radius: 12px; margin-top: 30px; text-align: center; }
    .ai-content { margin-top: 30px; line-height: 1.7; }
</style>
"""

@app.route('/')
def home():
    return f'''
        <!DOCTYPE html><html><head>{CSS_STYLE}</head><body>
        <div class="container" style="max-width: 450px; text-align: center;">
            <h2 style="color: #FC4C02;">AI Coach 40+</h2>
            
            <form action="/login" method="GET">
                <input type="number" name="age" placeholder="Umur (Contoh: 56)" required style="padding: 15px; width: 85%; border-radius: 12px; border: 1px solid #ddd; margin-bottom: 10px;">
                <button type="submit" class="btn-primary">Hubungkan Strava</button>
            </form>

            <div class="upload-section">
                <p style="font-weight: bold; margin-top: 0;">Analisis Mendalam (.FIT)</p>
                <form action="/upload" method="POST" enctype="multipart/form-data">
                    <input type="number" name="age" placeholder="Umur" required style="width: 50%; margin-bottom: 10px; padding: 5px;">
                    <input type="file" name="file_fit" accept=".fit" required style="font-size: 0.8em; margin-bottom: 10px;">
                    <button type="submit" style="background: #2d3748; color: white; padding: 10px; border-radius: 8px; cursor: pointer; border: none; width: 100%;">Upload & Bedah File</button>
                </form>
                <p style="font-size: 0.7em; color: #718096; margin-top: 10px;">Gunakan file asli dari Garmin/Coros untuk data HR lebih detail.</p>
            </div>
        </div>
        </body></html>
    '''

@app.route('/upload', methods=['POST'])
def upload_file():
    user_age = request.form.get('age')
    file = request.files.get('file_fit')
    
    if not file: return "File tidak ditemukan."
    
    # Simpan sementara
    temp_path = "temp_activity.fit"
    file.save(temp_path)
    
    # Bedah data menggunakan fungsi fitparse tadi
    data = parse_fit_data(temp_path)
    os.remove(temp_path) # Hapus file setelah dibedah agar hemat memori

    if isinstance(data, str): return data # Jika error

    # Racik Prompt untuk AI dengan data lebih detail
    prompt = f"""
    Kamu pelatih ahli usia {user_age} tahun. Saya baru saja mengupload file aktivitas .FIT mentah.
    Data yang ditemukan:
    - Jenis: {data['type']}
    - Jarak: {round(data['distance_m']/1000, 2)} km
    - Durasi: {round(data['duration_m'], 1)} menit
    - Detak Jantung Rata-rata: {data['avg_hr']} bpm
    - Detak Jantung Maksimal: {data['max_hr']} bpm
    - Kalori Terbakar: {data['calories']} kcal

    Berikan analisis mendalam. Karena ini data mentah, evaluasi distribusi intensitasnya. 
    Berikan saran spesifik untuk jantung usia {user_age} tahun. 
    JANGAN gunakan markdown ```html. Gunakan <h3>, <p>, <ul>, <li>.
    """
    
    ai_response = model.generate_content(prompt)
    laporan = ai_response.text.replace("```html", "").replace("```", "").strip()

    return f'''
        <!DOCTYPE html><html><head>{CSS_STYLE}</head><body>
        <div class="container">
            <h2 style="text-align: center;">Analisis File Mentah</h2>
            <div class="ai-content">{laporan}</div>
            <div style="text-align: center; margin-top: 30px;">
                <a href="/" style="color: #FC4C02; text-decoration: none; font-weight: bold;">&larr; Kembali</a>
            </div>
        </div>
        </body></html>
    '''

# (Route login & callback tetap sama untuk fungsi Strava kamu)
# ...
