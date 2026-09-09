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
                 ('qr', 'QR Scanner'), ('application', 'Aplikasi')]

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
    print (ssid + "- " +password )
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
            universal_newlines=True
        )

        # Cek exit code
        if result.returncode == 0:
            print(f"PM2 restart '{app_name}' berhasil ✅")
            print(result.stdout)

            # Cek status proses
            status = subprocess.run(
                ["pm2", "status", app_name],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                universal_newlines=True
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
    restart_pm2_app("scola-absen")
    flash("✅ APP RESTART!")
    return settings_redirect('application')

@app.route('/scan_ssid')
def scan_ssid():
    ssids = scan_wifi()
    return jsonify(ssids)

@app.route('/scan_usb_devices')
def scan_usb_devices():
    devices = scan_usb_input_devices()
    return jsonify(devices)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
