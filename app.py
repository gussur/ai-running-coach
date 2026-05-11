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

# --- FUNGSI BEDAH FILE .FIT (ANTI-CRASH) ---
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
                # Tambahan 'or 0' agar jika datanya kosong (None), otomatis jadi 0
                if data.name == 'total_distance': data_ringkas['distance_m'] = data.value or 0
                if data.name == 'total_timer_time': data_ringkas['duration_m'] = (data.value or 0) / 60
                if data.name == 'avg_heart_rate': data_ringkas['avg_hr'] = data.value or 0
                if data.name == 'max_heart_rate': data_ringkas['max_hr'] = data.value or 0
                if data.name == 'total_calories': data_ringkas['calories'] = data.value or 0
                if data.name == 'sport': data_ringkas['type'] = data.value or "Aktivitas"

        return data_ringkas
    except Exception as e:
        return f"GAGAL MEMBACA FILE: {str(e)}"

# --- RUTE UPLOAD ---
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
    if os.path.exists(temp_path):
        os.remove(temp_path)

    # Jika hasil bedah berupa teks error, tampilkan ke layar (bukan Error 500)
    if isinstance(data, str): 
        return f"Maaf, ada masalah saat membedah data: {data}"

    # Pastikan angka aman sebelum diracik untuk AI
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

    Berikan analisis mendalam berdasar data di atas. Evaluasi zona jantungnya.
    JANGAN gunakan markdown ```html. Gunakan <h3>, <p>, <ul>, <li>.
    """
    
    ai_response = model.generate_content(prompt)
    laporan = ai_response.text.replace("```html", "").replace("```", "").strip()

    return f'''
        <!DOCTYPE html><html><head>{CSS_STYLE}</head><body>
        <div class="container">
            <h2 style="text-align: center;">Analisis File Mentah (.FIT)</h2>
            <div class="ai-content">{laporan}</div>
            <div style="text-align: center; margin-top: 30px;">
                <a href="/" style="background: #FC4C02; color: white; padding: 12px 25px; text-decoration: none; border-radius: 8px;">&larr; Kembali</a>
            </div>
        </div>
        </body></html>
    '''
# (Route login & callback tetap sama untuk fungsi Strava kamu)
# ...
