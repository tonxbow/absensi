import requests
import os
import sys

VERSION_FILE_URL = 'https://raw.githubusercontent.com/tonxbow/absensi/main/version.txt'  # Ganti dengan URL file versi online
MAIN_FILE_URL = 'https://raw.githubusercontent.com/tonxbow/absensi/main/updater.py'         # Ganti dengan URL aplikasi terbaru

LOCAL_VERSION = '1.0.3'
LOCAL_FILE = 'updater.py'

def get_online_version():
    try:
        response = requests.get(VERSION_FILE_URL)
        return response.text.strip()
    except:
        return None

def download_latest():
    print("Mengunduh versi terbaru...")
    response = requests.get(MAIN_FILE_URL)
    with open(LOCAL_FILE, 'wb') as f:
        f.write(response.content)

def restart_app():
    print("Menjalankan ulang aplikasi...")
    os.execv(sys.executable, ['python'] + sys.argv)

def check_for_update():
    online_version = get_online_version()
    if online_version and online_version != LOCAL_VERSION:
        print(f"Versi baru tersedia: {online_version}")
        download_latest()
        restart_app()
    else:
        print("Aplikasi sudah versi terbaru.")

if __name__ == '__main__':
    check_for_update()
    # lanjutkan ke logika utama aplikasimu di bawah
    print("Menjalankan aplikasi versi", LOCAL_VERSION)
