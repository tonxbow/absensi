from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, abort
import json, os, subprocess, netifaces
import ipaddress
import glob
import secrets
import re
import tempfile
import threading
import base64
import http.client
from urllib.parse import quote


app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY') or secrets.token_hex(32)

CONFIG_FILE = "setting.json"
ETH_CONN_NAME = "eth0-static"
tailscale_reset_lock = threading.Lock()
SETTINGS_TABS = [('ethernet', 'Ethernet'), ('wifi', 'WiFi'), ('tailscale', 'Tailscale'),
                 ('device', 'Device Info'), ('timezone', 'Timezone'),
                 ('qr', 'QR Scanner'), ('application', 'Aplikasi'),
                 ('git', 'Git / OTA'), ('logs', 'Logs'), ('hardware', 'Hardware'), ('account', 'Akun')]

def settings_redirect(tab):
    return redirect(url_for('network', tab=tab))

def check_tailscale_csrf():
    token = session.get('tailscale_csrf', '')
    if not token or not secrets.compare_digest(token.encode(), request.form.get('csrf_token', '').encode()):
        abort(400, description='Form kedaluwarsa. Muat ulang halaman konfigurasi.')

def valid_tailscale_hostname(hostname):
    return re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', hostname) is not None

def get_tailscale_info():
    info = {'ips': [], 'status': 'Tidak tersedia', 'health': [], 'hostname': '',
            'dns_name': '', 'device_id': '', 'key_expiry': '', 'expired': False}
    try:
        result = subprocess.run(['tailscale', 'status', '--json'],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=5)
        if result.returncode != 0:
            info['status'] = 'Tidak dapat membaca status tailscaled'
            return info
        data = json.loads(result.stdout)
        info['ips'] = data.get('TailscaleIPs') or []
        info['status'] = data.get('BackendState') or 'Tidak diketahui'
        info['health'] = data.get('Health') or []
        node = data.get('Self') or {}
        info['hostname'] = node.get('HostName') or ''
        info['dns_name'] = (node.get('DNSName') or '').rstrip('.')
        info['device_id'] = node.get('ID') or ''
        info['key_expiry'] = node.get('KeyExpiry') or ''
        info['expired'] = bool(node.get('Expired'))
    except FileNotFoundError:
        info['status'] = 'Tailscale belum terpasang'
    except (OSError, subprocess.TimeoutExpired, ValueError, AttributeError):
        info['status'] = 'Status Tailscale tidak dapat dibaca'
    return info

def run_tailscale_admin(args, timeout=30):
    # Non-interactive sudo: never leave the web request waiting for a password.
    prefix = [] if os.geteuid() == 0 else ['sudo', '-n']
    subprocess.run(prefix + args, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                   universal_newlines=True, timeout=timeout)

def tailscale_device_api(api_token, device_id, method='GET', payload=None):
    # Fixed HTTPS destination, no redirects and no credentials in URLs or logs.
    path = '/api/v2/device/' + quote(device_id, safe='')
    if method == 'POST':
        path += '/key'
    authorization = base64.b64encode((api_token + ':').encode()).decode()
    headers = {'Authorization': 'Basic ' + authorization, 'Accept': 'application/json'}
    body = None
    if payload is not None:
        body = json.dumps(payload)
        headers['Content-Type'] = 'application/json'
    connection = http.client.HTTPSConnection('api.tailscale.com', timeout=15)
    try:
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        raw = response.read()
        if response.status in (401, 403):
            raise ValueError('API token tidak valid, kedaluwarsa, atau tidak memiliki izin mengelola perangkat ini.')
        if response.status == 404:
            raise ValueError('Node tidak ditemukan di tailnet pemilik API token.')
        if not 200 <= response.status < 300:
            raise ValueError('Tailscale API gagal merespons (HTTP %s). Coba lagi.' % response.status)
        if method == 'GET':
            try:
                data = json.loads(raw)
            except (ValueError, UnicodeError):
                raise ValueError('Respons Tailscale API tidak dapat dibaca. Cek status lagi.') from None
            if not isinstance(data, dict) or not isinstance(data.get('keyExpiryDisabled'), bool):
                raise ValueError('Status key expiry dari API tidak dapat dibaca.')
            return data
        return None
    finally:
        connection.close()

@app.route('/save_tailscale_name', methods=['POST'])
def save_tailscale_name():
    check_tailscale_csrf()
    hostname = request.form.get('hostname', '').strip().lower()
    if not valid_tailscale_hostname(hostname):
        flash('❌ Nama harus 1–63 karakter: huruf, angka, atau tanda hubung; awal dan akhir harus huruf/angka.')
        return settings_redirect('tailscale')
    if not tailscale_reset_lock.acquire(blocking=False):
        flash('⏳ Perubahan Tailscale sedang berjalan. Coba lagi setelah selesai.')
        return settings_redirect('tailscale')
    try:
        run_tailscale_admin(['tailscale', 'set', '--hostname=' + hostname])
        try:
            cfg = load_config()
            cfg.setdefault('tailscale', {})['hostname'] = hostname
            save_config(cfg)
            flash('✅ Nama Tailscale diubah menjadi ' + hostname + '.')
        except (OSError, ValueError, TypeError):
            flash('ℹ️ Nama Tailscale sudah diubah, tetapi gagal disimpan ke setting.json untuk daftar ulang berikutnya.')
    except (OSError, subprocess.SubprocessError):
        flash('❌ Nama gagal diubah. Pastikan tailscaled berjalan, CLI mendukung tailscale set, dan akses root/sudo tersedia.')
    finally:
        tailscale_reset_lock.release()
    return settings_redirect('tailscale')

@app.route('/set_tailscale_expiry', methods=['POST'])
def set_tailscale_expiry():
    check_tailscale_csrf()
    api_token = request.form.get('api_token', '').strip()
    action = request.form.get('expiry_action', '')
    if not re.fullmatch(r'tskey-api-[A-Za-z0-9_-]{10,500}', api_token):
        flash('❌ Isi API access token (tskey-api-...), bukan auth key (tskey-auth-...).')
        return settings_redirect('tailscale')
    if action not in ('check', 'disable', 'enable'):
        abort(400)
    if not tailscale_reset_lock.acquire(blocking=False):
        flash('⏳ Perubahan Tailscale sedang berjalan. Coba lagi setelah selesai.')
        return settings_redirect('tailscale')
    try:
        device_id = get_tailscale_info()['device_id']
        if not device_id:
            flash('❌ Identitas node belum tersedia. Hubungkan atau daftarkan Tailscale dahulu.')
            return settings_redirect('tailscale')
        if action != 'check':
            tailscale_device_api(api_token, device_id, 'POST', {'keyExpiryDisabled': action == 'disable'})
        data = tailscale_device_api(api_token, device_id)
        disabled = data['keyExpiryDisabled']
        if action != 'check' and disabled != (action == 'disable'):
            flash('❌ API belum mengonfirmasi pengaturan yang diminta. Periksa status lagi.')
        elif disabled:
            flash('✅ Dikonfirmasi Tailscale API: key expiry node ini dinonaktifkan.')
        else:
            flash('✅ Dikonfirmasi Tailscale API: key expiry node ini aktif. Expiry: ' + str(data.get('expires') or 'tidak tersedia'))
    except ValueError as error:
        flash('❌ ' + str(error))
    except (OSError, http.client.HTTPException):
        flash('❌ Tidak dapat menghubungi Tailscale API. Periksa internet lalu cek status lagi; perubahan mungkin sudah diterapkan.')
    finally:
        tailscale_reset_lock.release()
    return settings_redirect('tailscale')

@app.route('/reregister_tailscale', methods=['POST'])
def reregister_tailscale():
    check_tailscale_csrf()
    hostname = request.form.get('hostname', '').strip().lower()
    if hostname and not valid_tailscale_hostname(hostname):
        flash('❌ Nama node baru tidak valid. Gunakan 1–63 karakter huruf, angka, atau tanda hubung.')
        return settings_redirect('tailscale')
    auth_key = request.form.get('auth_key', '').strip()
    if not re.fullmatch(r'tskey-auth-[A-Za-z0-9_-]{10,500}', auth_key):
        flash('❌ Isi auth key Tailscale yang valid (tskey-auth-...).')
        return settings_redirect('tailscale')
    if request.form.get('confirm_reset') != 'yes':
        flash('❌ Konfirmasi penghapusan identitas Tailscale terlebih dahulu.')
        return settings_redirect('tailscale')
    if not tailscale_reset_lock.acquire(blocking=False):
        flash('⏳ Daftar ulang Tailscale sedang berjalan. Tunggu lalu muat ulang halaman.')
        return settings_redirect('tailscale')
    step = 'menyiapkan auth key'
    try:
        # Mode 0600, removed on exit; the key is never in argv, config, or logs.
        with tempfile.NamedTemporaryFile(mode='w', prefix='tailscale-auth-') as key_file:
            key_file.write(auth_key)
            key_file.flush()
            step = 'menghentikan tailscaled'
            try:
                run_tailscale_admin(['systemctl', 'stop', 'tailscaled'])
                step = 'menghapus identitas lama'
                run_tailscale_admin(['rm', '-f', '/var/lib/tailscale/tailscaled.state'])
            finally:
                # Also restore the service if removing the state fails.
                try:
                    run_tailscale_admin(['systemctl', 'start', 'tailscaled'])
                except (OSError, subprocess.SubprocessError):
                    step = 'menyalakan kembali tailscaled'
                    raise
            step = 'mendaftarkan node (periksa auth key dan koneksi internet)'
            up_args = ['tailscale', 'up', '--auth-key=file:' + key_file.name,
                       '--accept-dns=false', '--timeout=60s']
            if hostname:
                up_args.append('--hostname=' + hostname)
            run_tailscale_admin(up_args, timeout=75)
        info = get_tailscale_info()
        if info['status'] == 'Running' and info['ips']:
            flash('✅ Tailscale berhasil didaftarkan ulang. IP: ' + ', '.join(info['ips']))
        else:
            flash('ℹ️ Perintah daftar ulang selesai. Periksa status Tailscale dan persetujuan node di admin console.')
    except (OSError, subprocess.SubprocessError):
        # Do not expose subprocess output, which may contain credentials.
        flash('❌ Daftar ulang gagal saat ' + step +
              '. Pastikan layanan tersedia dan aplikasi memiliki akses root/sudo tanpa password. '
              'Jika identitas sudah dihapus, isi auth key dan coba lagi melalui IP LAN.')
    finally:
        tailscale_reset_lock.release()
    return settings_redirect('tailscale')

def subnet_to_prefix(subnet):
    return sum(bin(int(x)).count('1') for x in subnet.split('.'))

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_config(cfg):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(cfg, f, indent=4)

def get_interface_ip(interface_name):
    try:
        addresses = netifaces.ifaddresses(interface_name)
        if netifaces.AF_INET in addresses:
            return addresses[netifaces.AF_INET][0]['addr']
    except:
        return None
    return None

def get_current_timezone():
    try:
        result = subprocess.run(['timedatectl', 'show', '--property=Timezone', '--value'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            return 'UTC'
    except:
        return 'UTC'

def scan_wifi():
    try:
        output = subprocess.check_output(['nmcli', '-t', '-f', 'SSID', 'dev', 'wifi']).decode().splitlines()
        ssids = sorted(set([ssid for ssid in output if ssid.strip()]))
        return ssids
    except subprocess.CalledProcessError:
        return []

def scan_usb_input_devices():
    """Scan for USB input devices that could be QR code scanners using /dev/input/by-id/"""
    try:
        devices = []
        
        # Check if the directory exists
        by_id_path = '/dev/input/by-id/'
        if not os.path.exists(by_id_path):
            print("Directory /dev/input/by-id/ does not exist")
            return devices
            
        # Use ls command to list devices in /dev/input/by-id/
        try:
            result = subprocess.run(['ls', by_id_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, check=True)
            device_files = result.stdout.strip().split('\n')
        except subprocess.CalledProcessError:
            print("Failed to list devices in /dev/input/by-id/")
            return devices
        
        for device_file in device_files:
            if not device_file.strip():
                continue
                
            # Look for USB keyboard devices (typically contain 'usb' and 'kbd' or 'event-kbd')
            if 'usb-' in device_file and ('kbd' in device_file or 'event-kbd' in device_file):
                full_path = os.path.join(by_id_path, device_file)
                
                # Extract device information from the filename
                # Format is usually: usb-Vendor_Product_SerialNumber-event-kbd
                device_parts = device_file.replace('usb-', '').replace('-event-kbd', '').replace('_', ' ')
                
                # Clean up the device name
                device_name = device_parts.replace('-', ' ').title()
                if not device_name:
                    device_name = "USB Keyboard Device"
                
                devices.append({
                    'id': device_file,
                    'name': device_name,
                    'path': full_path
                })
                
        return devices
        
    except Exception as e:
        print(f"Error scanning USB devices: {e}")
        return []

@app.route('/')
def network():
    if 'tailscale_csrf' not in session:
        session['tailscale_csrf'] = secrets.token_urlsafe(32)
    active_tab = request.args.get('tab', 'ethernet')
    if active_tab not in dict(SETTINGS_TABS):
        active_tab = 'ethernet'
    cfg = load_config()
    eth_ip = get_interface_ip('eth0')
    wlan_ip = get_interface_ip('wlan0')
    ethernet_cfg = cfg.get('ethernet', None)
    wifi_cfg = cfg.get('wifi', None)
    qr_cfg = cfg.get('qr_device', None)
    timezone = get_current_timezone()
    usb_devices = scan_usb_input_devices()
    
    return render_template(
        'index.html',
        cfg=cfg,
        settings_tabs=SETTINGS_TABS,
        active_tab=active_tab,
        eth_ip=eth_ip,
        wlan_ip=wlan_ip,
        ethernet_cfg=ethernet_cfg,
        wifi_cfg=wifi_cfg,
        qr_cfg=qr_cfg,
        timezone=timezone,
        usb_devices=usb_devices,
        tailscale=get_tailscale_info(),
        tailscale_csrf=session['tailscale_csrf']
    )

@app.route('/save_ethernet', methods=['POST'])
def save_ethernet():
    ethernet_mode = request.form.get('ethernet_mode', 'manual')
    ip = request.form.get('ip', '')
    subnet = request.form.get('subnet', '').strip()
    gateway = request.form.get('gateway', '')

    cfg = load_config()
    subprocess.run(["nmcli", "con", "delete", ETH_CONN_NAME], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["nmcli", "con", "add", "type", "ethernet", "ifname", "eth0", "con-name", ETH_CONN_NAME], check=False)

    if ethernet_mode == "dhcp":
        subprocess.run(["nmcli", "con", "mod", ETH_CONN_NAME, "ipv4.method", "auto"], check=False)
        cfg['ethernet'] = {'mode': 'dhcp'}
    else:
        prefix = subnet_to_prefix(subnet)
        subprocess.run(["nmcli", "con", "mod", ETH_CONN_NAME, "ipv4.addresses", f"{ip}/{prefix}"], check=False)
        subprocess.run(["nmcli", "con", "mod", ETH_CONN_NAME, "ipv4.gateway", gateway], check=False)
        subprocess.run(["nmcli", "con", "mod", ETH_CONN_NAME, "ipv4.method", "manual"], check=False)
        cfg['ethernet'] = {
            'mode': 'manual',
            'ip': ip,
            'subnet': subnet,
            'gateway': gateway
        }

    subprocess.run(["nmcli", "con", "up", ETH_CONN_NAME], check=False)
    save_config(cfg)
    flash("✅ Ethernet settings saved!")
    return settings_redirect('ethernet')

@app.route('/save_wifi', methods=['POST'])
def save_wifi():
    ssid = request.form.get('ssid', '')
    password = request.form.get('password', '')
    cfg = load_config()
    if ssid:
        subprocess.run(["nmcli", "con", "delete", ssid], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if password:
            subprocess.run(["nmcli", "dev", "wifi", "connect", ssid, "password", password], check=False)
        else:
            subprocess.run(["nmcli", "dev", "wifi", "connect", ssid], check=False)
        cfg['wifi'] = {'ssid': ssid, 'password': password}
        save_config(cfg)
        flash("✅ Wi-Fi settings saved!")
    return settings_redirect('wifi')

@app.route('/save_device', methods=['POST'])
def save_device():
    machine_id = request.form.get('machine_id', '')
    api_host = request.form.get('api_host', '')

    cfg = load_config()
    if machine_id:
        cfg['machine-id'] = machine_id
    if api_host:
        cfg['api-server'] = api_host

    save_config(cfg)
    flash("✅ Device info saved!")
    return settings_redirect('device')

@app.route('/save_timezone', methods=['POST'])
def save_timezone():
    tz = request.form.get('timezone', 'UTC')
    cfg = load_config()
    try:
        subprocess.run(['timedatectl', 'set-timezone', tz], check=True)
        cfg['timezone'] = tz
        save_config(cfg)
        flash("✅ Timezone saved!")
    except subprocess.CalledProcessError:
        flash("❌ Failed to set timezone")
    return settings_redirect('timezone')

@app.route('/save_qr_device', methods=['POST'])
def save_qr_device():
    qr_device = request.form.get('qr_device', 'none')
    
    cfg = load_config()
    if qr_device == 'none':
        cfg['qr_device'] = {
            'enabled': False,
            'device_id': '',
            'device_path': '',
            'device_name': 'No QR Scanner'
        }
    else:
        # Find device name and path from the scanned devices
        devices = scan_usb_input_devices()
        device_name = 'Unknown Device'
        device_path = ''
        for device in devices:
            if device['id'] == qr_device:
                device_name = device['name']
                device_path = device['path']
                break
                
        cfg['qr_device'] = {
            'enabled': True,
            'device_id': qr_device,
            'device_path': device_path,
            'device_name': device_name
        }
    
    save_config(cfg)
    flash("✅ QR Scanner settings saved!")
    return settings_redirect('qr')

def restart_pm2_app(app_name):
    try:
        # Jalankan restart
        result = subprocess.run(
            ["pm2", "restart", app_name],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True, timeout=30
        )

        # Cek exit code
        if result.returncode == 0:
            print(f"PM2 restart '{app_name}' berhasil ✅")
            print(result.stdout)

            # Cek status proses
            status = subprocess.run(
                ["pm2", "status", app_name],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                universal_newlines=True, timeout=10
            )
            print(status.stdout)

            if "online" in status.stdout.lower():
                print(f"Aplikasi '{app_name}' sedang berjalan ONLINE ✅")
                return True
            else:
                print(f"Aplikasi '{app_name}' tidak online ❌")
                return False

        else:
            print(f"Gagal restart PM2 '{app_name}' ❌")
            print(result.stderr)
            return False

    except Exception as e:
        print("ERROR:", e)
        return False


@app.route('/restart_app', methods=['POST'])
def restart_app():
    success = restart_pm2_app(PM2_TARGET)
    flash("Aplikasi direstart." if success else "Restart gagal. Periksa log PM2.")
    return settings_redirect('application')

@app.route('/scan_ssid')
def scan_ssid():
    ssids = scan_wifi()
    return jsonify(ssids)

@app.route('/scan_usb_devices')
def scan_usb_devices():
    devices = scan_usb_input_devices()
    return jsonify(devices)

# Management routes never open SPI/I2C or drive GPIO.
from flask import render_template_string
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.exceptions import HTTPException
from datetime import timedelta
from collections import deque
import time
import fcntl
import stat

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, 'setting.json')
STATE_DIR = os.environ.get('ABSENSI_STATE_DIR', os.path.expanduser('~/.config/absensi'))
AUTH_FILE = os.path.join(STATE_DIR, 'web-auth.json')
OTA_FILE = os.environ.get('ABSENSI_OTA_FILE', os.path.join(STATE_DIR, 'ota.json'))
HARDWARE_FILE = os.environ.get('ABSENSI_HARDWARE_FILE', '/run/absensi-hardware.json')
PM2_TARGET = os.environ.get('ABSENSI_PM2_APP', '0')
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
                  PERMANENT_SESSION_LIFETIME=timedelta(hours=8), MAX_CONTENT_LENGTH=65536)
auth_lock = threading.RLock()
ota_lock = threading.RLock()
management_lock = threading.Lock()
job_lock = threading.Lock()
management_jobs = {}


def atomic_json(path, data):
    directory = os.path.dirname(path)
    os.makedirs(directory, mode=0o700, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=directory)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(data, stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def auth_record():
    with auth_lock:
        if not os.path.exists(AUTH_FILE):
            atomic_json(AUTH_FILE, {'username': 'admin',
                'password_hash': generate_password_hash('penta123', method='pbkdf2:sha256:260000'),
                'session_secret': secrets.token_hex(32), 'revision': secrets.token_hex(16)})
        with open(AUTH_FILE) as stream:
            return json.load(stream)


app.secret_key = os.environ.get('FLASK_SECRET_KEY') or auth_record()['session_secret']
AUTH_PAGE = '''<!doctype html><html lang="id"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Login Absensi</title><style>body{font-family:Arial;background:#f4f4f4}main{max-width:380px;margin:8vh auto;padding:28px;background:white;border-radius:8px}label{display:block;margin-top:16px}input,button{box-sizing:border-box;width:100%;padding:12px;margin-top:6px}button{background:#007bff;color:white;border:0}p{color:#a00}</style>
<main><h1>Login Absensi</h1>{% if error %}<p>{{ error }}</p>{% endif %}<form method="post"><input type="hidden" name="csrf_token" value="{{ token }}">
<label>Username<input name="username" autocomplete="username" required></label><label>Password<input type="password" name="password" autocomplete="current-password" required></label><button>Login</button></form></main></html>'''


def csrf_token():
    if 'tailscale_csrf' not in session:
        session['tailscale_csrf'] = secrets.token_urlsafe(32)
    return session['tailscale_csrf']


@app.before_request
def protect_management():
    if request.endpoint == 'static':
        return None
    token = csrf_token()
    if request.method not in ('GET', 'HEAD', 'OPTIONS'):
        supplied = request.headers.get('X-CSRF-Token') or request.form.get('csrf_token', '')
        if not supplied or not secrets.compare_digest(token, supplied):
            if request.path.startswith('/api/'):
                return jsonify(success=False, message='Sesi/form kedaluwarsa. Muat ulang halaman.'), 400
            abort(400, description='Form kedaluwarsa. Muat ulang halaman.')
    if request.endpoint == 'login':
        return None
    if session.get('auth_revision') != auth_record()['revision']:
        if request.path.startswith('/api/'):
            return jsonify(success=False, message='Silakan login kembali.'), 401
        return redirect(url_for('login'))


@app.after_request
def management_headers(response):
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    return response


@app.route('/login', methods=['GET', 'POST'])
def login():
    error = ''
    if request.method == 'POST':
        record = auth_record()
        if (request.form.get('username') == record['username'] and
                check_password_hash(record['password_hash'], request.form.get('password', ''))):
            session.clear()
            session['auth_revision'] = record['revision']
            session.permanent = True
            csrf_token()
            return redirect(url_for('network'))
        error = 'Username atau password salah.'
    return render_template_string(AUTH_PAGE, error=error, token=csrf_token()), (401 if error else 200)


@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/change_password', methods=['POST'])
def change_password():
    with auth_lock:
        record = auth_record()
        password = request.form.get('new_password', '')
        if not check_password_hash(record['password_hash'], request.form.get('current_password', '')):
            flash('Password saat ini salah.')
        elif not 8 <= len(password) <= 128:
            flash('Password baru harus 8–128 karakter.')
        elif password != request.form.get('confirm_password'):
            flash('Konfirmasi password tidak sama.')
        else:
            record['password_hash'] = generate_password_hash(password, method='pbkdf2:sha256:260000')
            record['revision'] = secrets.token_hex(16)
            atomic_json(AUTH_FILE, record)
            session['auth_revision'] = record['revision']
            flash('Password berhasil diubah. Sesi login lain telah diakhiri.')
    return settings_redirect('account')


def ota_settings():
    path = OTA_FILE if os.path.exists(OTA_FILE) else os.path.join(SCRIPT_DIR, 'ota.json')
    data = {}
    try:
        with open(path) as stream:
            data = json.load(stream)
    except FileNotFoundError:
        pass
    if not isinstance(data, dict):
        raise ValueError('ota.json harus objek JSON.')
    # Preserve legacy firmware URLs/version. Device overrides stay outside Git.
    raw_url = data.get('ota-version', '')
    match = re.fullmatch(r'https://raw\.githubusercontent\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/(.+)/ota\.json', raw_url)
    data.setdefault('repository', ('https://github.com/%s/%s.git' % match.group(1, 2)) if match else 'https://github.com/tonxbow/absensi.git')
    data.setdefault('branch', match.group(3) if match else 'zerolts')
    return data


def validate_repo(repository):
    if not isinstance(repository, str) or not re.fullmatch(r'(?:https://github\.com/|git@github\.com:)[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?', repository):
        raise ValueError('Gunakan URL repository GitHub HTTPS atau SSH tanpa token/password.')
    return repository


def validate_branch(branch):
    if not isinstance(branch, str) or len(branch) > 200 or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._/-]*', branch):
        raise ValueError('Nama branch tidak valid.')
    run_management(['git', 'check-ref-format', '--branch', branch])
    return branch


def run_management(args, timeout=30):
    environment = dict(os.environ, GIT_TERMINAL_PROMPT='0', GIT_ASKPASS='/bin/false',
                       GIT_SSH_COMMAND='ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=10')
    result = subprocess.run(args, cwd=SCRIPT_DIR, env=environment, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, universal_newlines=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError('%s gagal. Periksa konfigurasi, akses repository, dan log layanan.' % args[0])
    return result.stdout


@app.route('/api/ota', methods=['GET', 'POST'])
def api_ota():
    try:
        with ota_lock:
            data = ota_settings()
            if request.method == 'POST':
                patch = request.get_json(silent=True) or {}
                data['repository'] = validate_repo(patch.get('repository', data['repository']))
                data['branch'] = validate_branch(patch.get('branch', data['branch']))
                atomic_json(OTA_FILE, data)
        return jsonify(success=True, settings=data, path=OTA_FILE)
    except (ValueError, RuntimeError, OSError, subprocess.SubprocessError) as error:
        return jsonify(success=False, message=str(error)), 400


@app.route('/api/git/branches')
def api_git_branches():
    try:
        cfg = ota_settings()
        repository = validate_repo(request.args.get('repository', cfg['repository']))
        output = run_management(['git', 'ls-remote', '--heads', repository], timeout=20)
        branches = sorted({line.split('refs/heads/', 1)[1].strip() for line in output.splitlines() if 'refs/heads/' in line})
        return jsonify(success=True, branches=branches)
    except (ValueError, RuntimeError, OSError, subprocess.SubprocessError) as error:
        return jsonify(success=False, message=str(error)), 503


def pull_firmware(repository, branch):
    git = lambda *args: run_management(['git', *args], timeout=120)
    git('rev-parse', '--show-toplevel')
    if git('status', '--porcelain', '--untracked-files=no').strip():
        raise ValueError('Pull dibatalkan: ada perubahan lokal pada file Git. Simpan/commit dahulu.')
    git('fetch', '--no-tags', repository, 'refs/heads/' + branch)
    target = git('rev-parse', 'FETCH_HEAD').strip()
    if target == git('rev-parse', 'HEAD').strip():
        return 'Kode sudah terbaru.'
    git('merge-base', '--is-ancestor', 'HEAD', target)
    if git('branch', '--list', branch).strip():
        git('merge-base', '--is-ancestor', branch, target)
        git('checkout', branch)
    else:
        git('checkout', '-b', branch)
    git('merge', '--ff-only', target)
    return 'Pull berhasil. Restart aplikasi untuk memuat firmware; restart layanan web jika kode web berubah.'


def start_management_job(operation):
    if not management_lock.acquire(False):
        return jsonify(success=False, message='Operasi lain masih berjalan.'), 409
    job_id = secrets.token_hex(12)
    with job_lock:
        while len(management_jobs) >= 30:
            del management_jobs[next(iter(management_jobs))]
        management_jobs[job_id] = {'status': 'running', 'message': 'Operasi sedang berjalan...'}
    def worker():
        try:
            message = operation()
            result = {'status': 'succeeded', 'message': message}
        except Exception as error:
            result = {'status': 'failed', 'message': str(error)}
        finally:
            management_lock.release()
        with job_lock:
            management_jobs[job_id] = result
    threading.Thread(target=worker, daemon=True).start()
    return jsonify(success=True, job_id=job_id), 202


@app.route('/api/jobs/<job_id>')
def api_management_job(job_id):
    with job_lock:
        result = management_jobs.get(job_id)
        if result is None:
            return jsonify(success=False, message='Status operasi tidak ditemukan.'), 404
        return jsonify(success=True, job=result)


@app.route('/api/git/pull', methods=['POST'])
def api_git_pull():
    try:
        patch = request.get_json(silent=True) or {}
        cfg = ota_settings()
        repository = validate_repo(patch.get('repository', cfg['repository']))
        branch = validate_branch(patch.get('branch', cfg['branch']))
    except (ValueError, RuntimeError, OSError, subprocess.SubprocessError) as error:
        return jsonify(success=False, message=str(error)), 400
    return start_management_job(lambda: pull_firmware(repository, branch))


@app.route('/api/application/restart', methods=['POST'])
def api_application_restart():
    def restart():
        run_management(['pm2', 'restart', PM2_TARGET], timeout=30)
        return 'Aplikasi absensi berhasil direstart melalui PM2.'
    return start_management_job(restart)


_log_paths_cache = (0, None)
_log_paths_lock = threading.Lock()


def pm2_log_paths():
    global _log_paths_cache
    with _log_paths_lock:
        if _log_paths_cache[1] and time.monotonic() - _log_paths_cache[0] < 10:
            return dict(_log_paths_cache[1])
        entries = json.loads(run_management(['pm2', 'jlist'], timeout=10))
        for entry in entries:
            env = entry.get('pm2_env', {})
            if str(entry.get('pm_id')) == PM2_TARGET or entry.get('name') == PM2_TARGET:
                paths = {'out': env.get('pm_out_log_path'), 'error': env.get('pm_err_log_path')}
                if not all(isinstance(path, str) and os.path.isabs(path) for path in paths.values()):
                    raise ValueError('Lokasi log PM2 tidak valid.')
                _log_paths_cache = (time.monotonic(), paths)
                return dict(paths)
        raise ValueError('Proses absensi tidak ditemukan di PM2.')


def tail_log(path):
    try:
        with open(path, 'rb') as stream:
            stream.seek(0, os.SEEK_END)
            position = stream.tell()
            chunks = []
            count = 0
            while position and count <= 15 and sum(map(len, chunks)) < 262144:
                size = min(position, 8192)
                position -= size
                stream.seek(position)
                chunk = stream.read(size)
                chunks.append(chunk)
                count += chunk.count(b'\n')
            return b'\n'.join(b''.join(reversed(chunks)).replace(b'\x00', b'').splitlines()[-15:]).decode('utf-8', errors='replace')
    except FileNotFoundError:
        return ''


@app.route('/api/pm2/logs', methods=['GET', 'DELETE'])
def api_pm2_logs():
    try:
        paths = pm2_log_paths()
        if request.method == 'DELETE':
            for path in paths.values():
                try:
                    with open(path, 'r+b') as stream:
                        stream.truncate(0)
                except FileNotFoundError:
                    pass
        return jsonify(success=True, paths=paths, lines=15,
                       logs={key: tail_log(path) for key, path in paths.items()})
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        return jsonify(success=False, message=str(error)), 503


@app.route('/api/hardware')
def api_hardware():
    # Only a status snapshot written by absensi.py. Absolutely no bus probes.
    try:
        with open(HARDWARE_FILE) as stream:
            data = json.load(stream)
        stale = time.time() - data['reported_at'] > 15 or time.time() < data['reported_at'] - 5
        return jsonify(success=True, stale=stale, hardware=data)
    except (OSError, ValueError, KeyError, TypeError):
        return jsonify(success=True, stale=True, hardware=None,
                       message='Status belum tersedia. Jalankan absensi.py yang mendukung laporan hardware.')


@app.errorhandler(Exception)
def management_error(error):
    if isinstance(error, HTTPException):
        code, message = error.code, error.description
    else:
        app.logger.exception('Web configuration failed')
        code, message = 500, 'Operasi gagal. Periksa log layanan web.'
    if request.path.startswith('/api/'):
        return jsonify(success=False, message=message), code
    return message, code


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, threaded=True)
