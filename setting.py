#!/usr/bin/env python3

from rich.console import Console
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from datetime import datetime
import subprocess
import json
import os
import time
from smbus2 import SMBus

console = Console()
CONFIG_FILE = "setting.json"
I2C_BUS = 3
DS1307_ADDR = 0x68
NTP_SERVER = "time.google.com"

def run(cmd):
    try:
        return subprocess.check_output(cmd, shell=True, text=True).strip()
    except subprocess.CalledProcessError:
        return ""

def dec2bcd(val): return (val // 10) << 4 | (val % 10)
def bcd2dec(val): return ((val >> 4) * 10) + (val & 0x0F)

def read_ds1307():
    with SMBus(I2C_BUS) as bus:
        data = bus.read_i2c_block_data(DS1307_ADDR, 0x00, 7)
    seconds = bcd2dec(data[0] & 0x7F)
    minutes = bcd2dec(data[1])
    hours = bcd2dec(data[2] & 0x3F)
    day = bcd2dec(data[4])
    month = bcd2dec(data[5])
    year = bcd2dec(data[6]) + 2000
    return datetime(year, month, day, hours, minutes, seconds)

def write_ds1307(dt: datetime):
    with SMBus(I2C_BUS) as bus:
        bus.write_i2c_block_data(DS1307_ADDR, 0x00, [
            dec2bcd(dt.second),
            dec2bcd(dt.minute),
            dec2bcd(dt.hour),
            dec2bcd(dt.isoweekday()),
            dec2bcd(dt.day),
            dec2bcd(dt.month),
            dec2bcd(dt.year - 2000)
        ])

def get_ntp_time():
    try:
        output = run(f"ntpdate -q {NTP_SERVER}")
        for line in output.splitlines():
            if "offset" in line:
                return datetime.now()
    except:
        pass
    return None

def load_config():
    default = {
        "api-server": "https://api-absensi.scola.id/foundation/kehadiran",
        "machine-id": "12345"
    }
    if not os.path.exists(CONFIG_FILE):
        save_config(default)
    with open(CONFIG_FILE) as f:
        user_conf = json.load(f)
    for k, v in default.items():
        if k not in user_conf:
            user_conf[k] = v
    save_config(user_conf)
    return user_conf

def save_config(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=4)

def show_dashboard(config, rtc_time, ntp_time):
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="body", ratio=1)
    )

    table = Table(expand=True)
    table.add_column("Info")
    table.add_column("Value")
    table.add_row("RTC", rtc_time.strftime("%Y-%m-%d %H:%M:%S") if rtc_time else "RTC Error")
    table.add_row("NTP", ntp_time.strftime("%Y-%m-%d %H:%M:%S") if ntp_time else "NTP Error")
    table.add_row("API URL", config.get("api-server", "-"))
    table.add_row("Kode Mesin", config.get("machine-id", "-"))

    layout["header"].update(Panel("=== NETWORK WIZARD ==="))
    layout["body"].update(table)

    return layout

def wifi_setup():
    console.print("\n=== Wi-Fi Setup ===")
    console.print(run("nmcli dev wifi"))
    ssid = console.input("SSID: ")
    passwd = console.input("Password: ")
    cmd = f"nmcli dev wifi connect '{ssid}' password '{passwd}'"
    output = run(cmd)
    console.print(output)

def ethernet_setup():
    console.print("\n=== Ethernet Setup ===")
    mode = console.input("Mode (dhcp/static): ")
    if mode == "dhcp":
        run("nmcli con mod 'Wired connection 1' ipv4.method auto && nmcli con up 'Wired connection 1'")
        console.print("Ethernet diatur DHCP.")
    else:
        ip = console.input("Static IP (e.g., 192.168.1.100/24): ")
        gw = console.input("Gateway: ")
        dns = console.input("DNS: ")
        cmd = f"nmcli con mod 'Wired connection 1' ipv4.addresses {ip} ipv4.gateway {gw} ipv4.dns {dns} ipv4.method manual && nmcli con up 'Wired connection 1'"
        output = run(cmd)
        console.print(output)

def edit_config(config):
    console.print("\n=== Edit Config ===")
    old_api = config.get("api-server", "kosong")
    old_kode = config.get("machine-id", "kosong")

    console.print(f"API URL sekarang : {old_api}")
    console.print(f"Kode Mesin sekarang : {old_kode}")

    new_api = console.input(f"API URL baru (ENTER jika tetap): ")
    new_kode = console.input(f"Kode Mesin baru (ENTER jika tetap): ")

    config["api-server"] = new_api or old_api
    config["machine-id"] = new_kode or old_kode

    save_config(config)
    console.print("✅ Config disimpan.")

def sync_rtc_ntp():
    ntp = get_ntp_time()
    if ntp:
        write_ds1307(ntp)
        console.print("RTC disinkron ke NTP.")
    else:
        console.print("Gagal sync NTP.")

def main():
    config = load_config()
    ntp_time = None
    last_ntp = 0

    while True:
        rtc_time = None
        try:
            rtc_time = read_ds1307()
        except:
            pass

        if time.time() - last_ntp > 10:
            ntp_time = get_ntp_time()
            last_ntp = time.time()

        with Live(show_dashboard(config, rtc_time, ntp_time), refresh_per_second=1, screen=True):
            time.sleep(2)

        console.print("""
[1] Wi-Fi Setup
[2] Ethernet Setup
[3] Sync RTC-NTP
[4] Edit Config
[5] Keluar
""")
        choice = console.input("Pilih: ")

        if choice == "1":
            wifi_setup()
        elif choice == "2":
            ethernet_setup()
        elif choice == "3":
            sync_rtc_ntp()
        elif choice == "4":
            edit_config(config)
        elif choice == "5":
            console.print("Keluar.")
            break

if __name__ == "__main__":
    main()
