#!/usr/bin/env python3

import npyscreen
import subprocess
import json
import os
from smbus2 import SMBus
from datetime import datetime
import ntplib 
import time
NTP_SERVER = "time.google.com"

CONFIG_FILE = "setting.json"
I2C_BUS = 3
DS1307_ADDR = 0x68

def run_cmd(cmd):
    try:
        return subprocess.check_output(cmd, shell=True, text=True).strip()
    except subprocess.CalledProcessError:
        return ""

def load_config():
    # Default config jika file belum ada
    default_config = {
        "api-server": "https://api-absensi.scola.id/foundation/kehadiran",
        "kode_mesin": "12345"
    }

    if not os.path.exists(CONFIG_FILE):
        save_config(default_config)
        return default_config

    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def save_config(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=4)

def dec2bcd(val):
    return (val // 10) << 4 | (val % 10)

def bcd2dec(val):
    return ((val >> 4) * 10) + (val & 0x0F)

def read_ds1307():
    with SMBus(I2C_BUS) as bus:
        data = bus.read_i2c_block_data(DS1307_ADDR, 0x00, 7)
        seconds = bcd2dec(data[0] & 0x7F)
        minutes = bcd2dec(data[1])
        hours = bcd2dec(data[2] & 0x3F)
        day = bcd2dec(data[4])
        month = bcd2dec(data[5])
        year = bcd2dec(data[6]) + 2000
    return f"{year:04d}-{month:02d}-{day:02d} {hours:02d}:{minutes:02d}:{seconds:02d}"

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


class RTCForm(npyscreen.ActionForm):
    def create(self):
        self.add(npyscreen.TitleFixedText, name="=== Atur & Cek RTC DS1307 ===")
        self.rtc_time = self.add(npyscreen.TitleFixedText, name="Waktu RTC:", value=read_ds1307())
        self.ntp_time = self.add(npyscreen.TitleFixedText, name="Waktu NTP:", value="")

        self.date_input = self.add(npyscreen.TitleText, name="Tanggal (YYYY-MM-DD):")
        self.time_input = self.add(npyscreen.TitleText, name="Jam (HH:MM:SS):")

        self.sync_btn = self.add(npyscreen.ButtonPress, name="Sync RTC ke NTP", when_pressed_function=self.sync_rtc)

        self.ntp_last_update = 0
        self.ntp_value = None

    def while_waiting(self):
        self.rtc_time.value = read_ds1307()
        self.rtc_time.display()

        if time.time() - self.ntp_last_update > 10:
            self.ntp_value = get_ntp_time()
            self.ntp_last_update = time.time()

        if self.ntp_value:
            self.ntp_time.value = self.ntp_value.strftime("%Y-%m-%d %H:%M:%S")
        else:
            self.ntp_time.value = "NTP gagal"
        self.ntp_time.display()

    def sync_rtc(self):
        ntp = get_ntp_time()
        if ntp:
            write_ds1307(ntp)
            npyscreen.notify_confirm("RTC disinkron dengan NTP!", title="RTC Sync")
        else:
            npyscreen.notify_confirm("Gagal ambil waktu NTP.", title="RTC Sync")

    def on_ok(self):
        try:
            dt = datetime.strptime(f"{self.date_input.value} {self.time_input.value}", "%Y-%m-%d %H:%M:%S")
            write_ds1307(dt)
            npyscreen.notify_confirm("Waktu RTC berhasil diset!", title="RTC")
        except Exception as e:
            npyscreen.notify_confirm(f"Format salah: {e}", title="Error")

        self.parentApp.setNextForm("MAIN")  # BALIK KE MENU

    def on_cancel(self):
        self.parentApp.setNextForm("MAIN")  # BALIK KE MENU

class WifiForm(npyscreen.ActionForm):
    def create(self):
        self.add(npyscreen.TitleFixedText, name="=== Wi-Fi Setup ===")
        self.ssid = self.add(npyscreen.TitleSelectOne, max_height=5, name="Pilih SSID:", values=self.scan_ssids(), scroll_exit=True)
        self.passwd = self.add(npyscreen.TitleText, name="Password:")

    def scan_ssids(self):
        result = run_cmd("nmcli -t -f SSID dev wifi | grep -v '^$' | sort | uniq")
        ssids = result.split("\n") if result else ["Tidak ada SSID terdeteksi"]
        return ssids

    def on_ok(self):
        if not self.ssid.get_selected_objects():
            npyscreen.notify_confirm("Pilih SSID terlebih dahulu!", title="Error")
            return

        selected_ssid = self.ssid.get_selected_objects()[0]
        password = self.passwd.value

        if not password:
            npyscreen.notify_confirm("Password tidak boleh kosong!", title="Error")
            return

        cmd = f"nmcli dev wifi connect '{selected_ssid}' password '{password}'"
        output = run_cmd(cmd)
        npyscreen.notify_confirm(f"Hasil:\n{output}", title="Hasil Wi-Fi")

        self.parentApp.setNextForm("MAIN")

    def on_cancel(self):
        self.parentApp.setNextForm("MAIN")

class EthernetForm(npyscreen.ActionForm):
    def create(self):
        self.add(npyscreen.TitleFixedText, name="=== Ethernet Setup ===")
        self.mode = self.add(npyscreen.TitleSelectOne, max_height=3, name="Mode:", values=["DHCP", "Static"], scroll_exit=True)
        self.ip = self.add(npyscreen.TitleText, name="Static IP (192.168.1.100/24):")
        self.gw = self.add(npyscreen.TitleText, name="Gateway:")
        self.dns = self.add(npyscreen.TitleText, name="DNS:")

    def on_ok(self):
        mode = self.mode.get_selected_objects()
        if not mode:
            npyscreen.notify_confirm("Pilih mode DHCP atau Static!", title="Error")
            return

        if mode[0] == "DHCP":
            run_cmd("nmcli con mod 'Wired connection 1' ipv4.method auto && nmcli con up 'Wired connection 1'")
            npyscreen.notify_confirm("Ethernet diatur ke DHCP & direstart.", title="Ethernet")
        else:
            if not self.ip.value or not self.gw.value:
                npyscreen.notify_confirm("IP dan Gateway tidak boleh kosong!", title="Error")
                return

            cmd = f"nmcli con mod 'Wired connection 1' ipv4.addresses {self.ip.value} ipv4.gateway {self.gw.value} ipv4.dns {self.dns.value} ipv4.method manual && nmcli con up 'Wired connection 1'"
            output = run_cmd(cmd)
            npyscreen.notify_confirm(f"Hasil:\n{output}", title="Hasil Ethernet")

        self.parentApp.setNextForm("MAIN")

    def on_cancel(self):
        self.parentApp.setNextForm("MAIN")

class ConfigForm(npyscreen.ActionForm):
    def create(self):
        self.add(npyscreen.TitleFixedText, name="=== Konfigurasi API & Kode Mesin ===")
        config = load_config()
        self.api_server = self.add(npyscreen.TitleText, name="URL API:", value=config.get("api-server", ""))
        self.machine_id = self.add(npyscreen.TitleText, name="Kode Mesin:", value=config.get("machine-id", ""))

    def on_ok(self):
        new_config = {
            "api-server": self.api_server.value,
            "machine-id": self.machine_id.value
        }
        save_config(new_config)
        npyscreen.notify_confirm(f"Konfigurasi disimpan ke {CONFIG_FILE}", title="Config Saved")
        self.parentApp.setNextForm("MAIN")

    def on_cancel(self):
        self.parentApp.setNextForm("MAIN")

def get_ntp_time():
    try:
        output = subprocess.check_output("ntpdate -q time.google.com", shell=True, text=True)
        for line in output.splitlines():
            if "offset" in line:
                # Kita percaya local clock update
                return datetime.now()
        return None
    except Exception as e:
        print(f"NTP Error: {e}")
        return None

class MainMenu(npyscreen.FormBaseNew):
    def create(self):
        self.add(npyscreen.FixedText, value="=== Config ===\n")
        
        # Tampilkan jam RTC & NTP
        self.rtc_clock = self.add(npyscreen.FixedText, value="RTC: ")
        self.ntp_clock = self.add(npyscreen.FixedText, value="NTP: ")

        self.add(npyscreen.ButtonPress, name="1. Set Wi-Fi", when_pressed_function=self.open_wifi)
        self.add(npyscreen.ButtonPress, name="2. Set Ethernet", when_pressed_function=self.open_eth)
        self.add(npyscreen.ButtonPress, name="3. Set API and Kode Mesin", when_pressed_function=self.open_config)
        self.add(npyscreen.ButtonPress, name="4. Set Datetime", when_pressed_function=self.open_rtc)
        self.add(npyscreen.ButtonPress, name="5. Keluar", when_pressed_function=self.exit_program)


        self.ntp_last_update = 0
        self.ntp_time = None

    def while_waiting(self):
        # Baca RTC
        try:
            rtc_now = read_ds1307()
        except:
            rtc_now = "RTC Error"

        self.rtc_clock.value = f"Waktu RTC: {rtc_now}"
        self.rtc_clock.display()

        # Baca NTP setiap 10 detik saja
        if time.time() - self.ntp_last_update > 10:
            self.ntp_time = get_ntp_time()
            self.ntp_last_update = time.time()

        if self.ntp_time:
            self.ntp_clock.value = f"Waktu NTP: {self.ntp_time.strftime('%Y-%m-%d %H:%M:%S')}"
        else:
            self.ntp_clock.value = "Waktu NTP: (Error)"

        self.ntp_clock.display()

    def open_wifi(self):
        self.parentApp.setNextForm("WIFI")
        self.editing = False

    def open_eth(self):
        self.parentApp.setNextForm("ETH")
        self.editing = False

    def open_config(self):
        self.parentApp.setNextForm("CONFIG")
        self.editing = False

    def open_rtc(self):
        self.parentApp.setNextForm("RTC")
        self.editing = False
    
    def exit_program(self):
        self.parentApp.setNextForm(None)
        self.editing = False


class NetworkWizardApp(npyscreen.NPSAppManaged):
    def onStart(self):
        self.addForm("MAIN", MainMenu)
        self.addForm("WIFI", WifiForm)
        self.addForm("ETH", EthernetForm)
        self.addForm("CONFIG", ConfigForm)
        self.addForm("RTC", RTCForm)

if __name__ == "__main__":
    app = NetworkWizardApp()
    app.run()
