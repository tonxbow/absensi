from flask import Flask, render_template, request, redirect, url_for, flash
import json, os, subprocess, netifaces

app = Flask(__name__)
app.secret_key = "scola-secret-key"  # untuk flash message

CONFIG_FILE = "setting.json"
ETH_CONN_NAME = "eth0-static"

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

def subnet_to_prefix(subnet):
    return sum(bin(int(x)).count('1') for x in subnet.split('.'))

@app.route('/')
def network():
    cfg = load_config()
    eth_ip = get_interface_ip('eth0')
    wlan_ip = get_interface_ip('wlan0')
    return render_template('network.html', cfg=cfg, eth_ip=eth_ip, wlan_ip=wlan_ip)

@app.route('/save_all', methods=['POST'])
def save_all():
    ip = request.form.get('ip', '')
    subnet = request.form.get('subnet', '')
    gateway = request.form.get('gateway', '')
    ssid = request.form.get('ssid', '')
    password = request.form.get('password', '')
    machine_id = request.form.get('machine_id', '')
    api_host = request.form.get('api_host', '')

    cfg = load_config()

    # --- Simpan Ethernet ---
    if ip and subnet and gateway:
        prefix = subnet_to_prefix(subnet)
        subprocess.run(["nmcli", "con", "add", "type", "ethernet", "ifname", "eth0", "con-name", ETH_CONN_NAME], check=False)
        subprocess.run(["nmcli", "con", "mod", ETH_CONN_NAME, "ipv4.addresses", f"{ip}/{prefix}"], check=False)
        subprocess.run(["nmcli", "con", "mod", ETH_CONN_NAME, "ipv4.gateway", gateway], check=False)
        subprocess.run(["nmcli", "con", "mod", ETH_CONN_NAME, "ipv4.method", "manual"], check=False)
        subprocess.run(["nmcli", "con", "up", ETH_CONN_NAME], check=False)
        cfg['ethernet'] = {'ip': ip, 'subnet': subnet, 'gateway': gateway}

    # --- Simpan WiFi ---
    if ssid:
        subprocess.run(["nmcli", "con", "delete", ssid], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if password:
            subprocess.run(["nmcli", "dev", "wifi", "connect", ssid, "password", password], check=False)
        else:
            subprocess.run(["nmcli", "dev", "wifi", "connect", ssid], check=False)
        cfg['wifi'] = {'ssid': ssid, 'password': password}

    # --- Simpan Device Info ---
    if machine_id:
        cfg['machine-id'] = machine_id
    if api_host:
        cfg['api-server'] = api_host

    save_config(cfg)
    flash("✅ Setting berhasil disimpan dan diterapkan!")
    return redirect(url_for('network'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
