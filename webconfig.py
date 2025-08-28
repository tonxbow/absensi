from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import json, os, subprocess, netifaces
import ipaddress


app = Flask(__name__)
app.secret_key = "scola-secret-key"

CONFIG_FILE = "setting.json"
ETH_CONN_NAME = "eth0-static"

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
        result = subprocess.run(['timedatectl', 'show', '--property=Timezone', '--value'], capture_output=True, text=True)
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

@app.route('/')
def network():
    cfg = load_config()
    eth_ip = get_interface_ip('eth0')
    wlan_ip = get_interface_ip('wlan0')
    ethernet_cfg = cfg.get('ethernet', None)
    wifi_cfg = cfg.get('wifi', None)
    timezone = get_current_timezone()
    return render_template(
        'index.html',
        cfg=cfg,
        eth_ip=eth_ip,
        wlan_ip=wlan_ip,
        ethernet_cfg=ethernet_cfg,
        wifi_cfg=wifi_cfg,
        timezone=timezone
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
    return redirect(url_for('network'))

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
    return redirect(url_for('network'))

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
    return redirect(url_for('network'))

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
    return redirect(url_for('network'))

def restart_pm2_app(app_name):
    try:
        # Jalankan restart
        result = subprocess.run(
            ["pm2", "restart", app_name],
            capture_output=True,
            text=True
        )

        # Cek exit code
        if result.returncode == 0:
            print(f"PM2 restart '{app_name}' berhasil ✅")
            print(result.stdout)

            # Cek status proses
            status = subprocess.run(
                ["pm2", "status", app_name],
                capture_output=True,
                text=True
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
    return redirect(url_for('network'))

@app.route('/scan_ssid')
def scan_ssid():
    ssids = scan_wifi()
    return jsonify(ssids)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
