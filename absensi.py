#install
# aktifkan spi dan i2c
# install Python3, pip3
# install lib spidev
# install LCD https://forum.armbian.com/topic/4377-using-16x2-1602-lcd-with-i2c-connector-with-orange-pi-pc/
# install RFID https://github.com/SecurityPhoton/OrangePi/blob/main/sensors/RFID-RC522/README.md
# pm2 start absensi.py | pm2 save  https://www.baeldung.com/linux/pm2-automatic-process-startup
# install mysql server + connector python
# sudo apt install default-mysql-server
# buat database "absensi" dan table absen dan setting

import sys
import subprocess
import os

def install_package(package_name, pip_name=None):
    """
    Automatically install a Python package using pip3
    package_name: the name used in import statement
    pip_name: the name used for pip3 install (if different from package_name)
    """
    if pip_name is None:
        pip_name = package_name
    
    try:
        print(f"🔄 Installing missing module: {pip_name}")
        
        # Special handling for certain packages
        if pip_name == "smbus":
            # Try different smbus packages for different systems
            smbus_packages = ["smbus", "smbus2", "smbus-cffi"]
            for pkg in smbus_packages:
                try:
                    # Try pip3 first, then fallback to python -m pip
                    try:
                        subprocess.check_call(["pip3", "install", pkg])
                    except (subprocess.CalledProcessError, FileNotFoundError):
                        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])
                    print(f"✅ Successfully installed: {pkg}")
                    return True
                except subprocess.CalledProcessError:
                    continue
            print("❌ Failed to install any smbus package")
            return False
        
        elif pip_name == "evdev":
            # evdev might need system packages on some systems
            try:
                # Try pip3 first
                try:
                    subprocess.check_call(["pip3", "install", "evdev"])
                except (subprocess.CalledProcessError, FileNotFoundError):
                    subprocess.check_call([sys.executable, "-m", "pip", "install", "evdev"])
                print(f"✅ Successfully installed: {pip_name}")
                return True
            except subprocess.CalledProcessError:
                print("❌ evdev installation failed. You might need to install system packages:")
                print("   sudo apt-get install python3-dev python3-pip")
                print("   sudo apt-get install linux-headers-$(uname -r)")
                return False
        
        else:
            # Try pip3 first, then fallback to python -m pip
            try:
                subprocess.check_call(["pip3", "install", pip_name])
            except (subprocess.CalledProcessError, FileNotFoundError):
                subprocess.check_call([sys.executable, "-m", "pip", "install", pip_name])
            print(f"✅ Successfully installed: {pip_name}")
            return True
            
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install {pip_name}: {e}")
        print(f"💡 Try installing manually: pip3 install {pip_name}")
        return False

def create_requirements_file():
    """Create requirements.txt file with all required packages for pip3 installation"""
    requirements = [
        "requests>=2.25.0",
        "netifaces>=0.11.0", 
        "mysql-connector-python>=8.0.0",
        "APScheduler>=3.8.0",
        "paho-mqtt>=1.5.0",
        "psutil>=5.8.0",
        "opencv-python>=4.5.0",
        "pyzbar>=0.1.8",
        "evdev>=1.4.0",
        "mfrc522>=0.0.7",
        "smbus2>=0.4.0"
    ]
    
    try:
        with open("requirements.txt", "w") as f:
            for req in requirements:
                f.write(req + "\n")
        print("📝 Created requirements.txt file")
        print("💡 You can install all packages with: pip3 install -r requirements.txt")
        print("💡 Or install individually: pip3 install <package_name>")
    except Exception as e:
        print(f"❌ Failed to create requirements.txt: {e}")

def try_import(module_name, pip_name=None, from_module=None):
    """
    Try to import a module, install it if missing, then import again
    module_name: name of the module to import
    pip_name: pip package name (if different from module_name)
    from_module: if it's a 'from X import Y' statement, specify X
    """
    try:
        if from_module:
            exec(f"from {from_module} import {module_name}")
        else:
            exec(f"import {module_name}")
        return True
    except ImportError:
        package_to_install = pip_name if pip_name else (from_module if from_module else module_name)
        if install_package(module_name, package_to_install):
            try:
                if from_module:
                    exec(f"from {from_module} import {module_name}")
                else:
                    exec(f"import {module_name}")
                return True
            except ImportError:
                print(f"❌ Still unable to import {module_name} after installation")
                return False
        return False

# Core imports (usually available)
try:
    import smbus
except ImportError:
    if install_package("smbus"):
        try:
            import smbus
        except ImportError:
            try:
                import smbus2 as smbus
                print("✅ Using smbus2 as smbus alternative")
            except ImportError:
                print("❌ Unable to import any smbus module")

import time
import threading
from datetime import datetime
from time import sleep
import json
import socket
import uuid
import platform
from datetime import datetime, timedelta
import traceback 
from typing import Any, Dict, Optional

# Try to import modules with auto-install
try:
    from mfrc522 import SimpleMFRC522
except ImportError:
    if install_package("mfrc522", "mfrc522"):
        from mfrc522 import SimpleMFRC522

try:
    import netifaces
except ImportError:
    if install_package("netifaces"):
        import netifaces

try:
    import requests
except ImportError:
    if install_package("requests"):
        import requests

try:
    import mysql.connector
except ImportError:
    if install_package("mysql.connector", "mysql-connector-python"):
        import mysql.connector

try:
    from apscheduler.schedulers.background import BackgroundScheduler
except ImportError:
    if install_package("apscheduler"):
        from apscheduler.schedulers.background import BackgroundScheduler

try:
    import paho.mqtt.client as mqtt
except ImportError:
    if install_package("paho.mqtt", "paho-mqtt"):
        import paho.mqtt.client as mqtt

try:
    import psutil
except ImportError:
    if install_package("psutil"):
        import psutil

try:
    import cv2
except ImportError:
    if install_package("cv2", "opencv-python"):
        import cv2

try:
    from pyzbar.pyzbar import decode
except ImportError:
    if install_package("pyzbar"):
        from pyzbar.pyzbar import decode

try:
    from evdev import InputDevice, categorize, ecodes
except ImportError:
    if install_package("evdev"):
        from evdev import InputDevice, categorize, ecodes



broker = "pentarium.id"   # bisa juga pakai localhost atau IP broker sendiri
port = 1883
statusInternet=False

def printDebug(*args):
    text = " ".join(str(a) for a in args)
    print(f"[{get_datetime()}] {text}")

def printDebugEx(text, e):
    print(f"[{get_datetime()}] {text} {str(e)}")
    traceback.print_exc()
############################### RTC FUNCTION #######################################
def bcd_to_dec(bcd):
    return (bcd // 16) * 10 + (bcd % 16)

def dec_to_bcd(val):
    return (val // 10) << 4 | (val % 10)

def read_rtc_time(bus_num=3, address=0x68):
    try:
        bus = smbus.SMBus(bus_num)
        data = bus.read_i2c_block_data(address, 0x00, 7)

        second = bcd_to_dec(data[0] & 0x7F)  # bit 7 disable oscillator
        minute = bcd_to_dec(data[1])
        hour = bcd_to_dec(data[2] & 0x3F)    # 24h format
        day = bcd_to_dec(data[4])
        month = bcd_to_dec(data[5] & 0x1F)
        year = bcd_to_dec(data[6]) + 2000

        dt = datetime(year, month, day, hour, minute, second)
        return dt
    except Exception as e:
        return f"ERROR membaca RTC: {e}"

def sync_time_with_rtc():
    printDebug("Masuk Sync")
    printDebug(statusInternet)
    if statusInternet == "ONLINE" : 
        dt = read_rtc_time()
        print(dt)
        if dt:
            try:
                date_str = dt.strftime('%m%d%H%M%Y.%S')
                subprocess.run(['sudo', 'date', date_str])
                printDebug("Waktu sistem disinkronisasi dengan RTC:", dt)
            except Exception as e:
                printDebugEx("ERROR RTC sync_time_with_rtc:", e)

def sync_rtc_with_system():
    try:
        bus = smbus.SMBus(3)  # Sesuaikan dengan I2C bus kamu
        now = datetime.now()  # Waktu dari sistem (NTP)

        bus.write_i2c_block_data(0x68, 0x00, [
            dec_to_bcd(now.second),
            dec_to_bcd(now.minute),
            dec_to_bcd(now.hour),
            0,  # Day of week (optional, bisa 0)
            dec_to_bcd(now.day),
            dec_to_bcd(now.month),
            dec_to_bcd(now.year - 2000)
        ])
        bus.close()

        printDebug(f"RTC berhasil disinkronisasi: {now.strftime('%Y-%m-%d %H:%M:%S')}")
        return True
    except Exception as e:
        printDebugEx("ERROR sync_rtc_with_system:", e)
        return False

def get_datetime():
    if statusInternet=="ONLINE" :
        waktu = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    else :
        waktu = read_rtc_time()
    return waktu



############################### OTA FUNCTION #######################################
# def get_online_version():
#     try:
#         # print ("xxx")
#         response = requests.get(VERSION_FILE_URL)
#         dataVersion = response.json()
#         print (dataVersion)
#         print (dataVersion['version'])
#         return str(dataVersion['version'])
#     except Exception as e:
#         print("ERROR get_online_version: ", e)


        
def get_online_version(branch="master") : 
    try:
        subprocess.run(["git", "fetch"], check=True)
        
        # Bandingkan HEAD lokal dengan remote
        local = subprocess.check_output(["git", "rev-parse", branch]).strip()
        remote = subprocess.check_output(["git", "rev-parse", f"origin/{branch}"]).strip()
        
        return local != remote
    except Exception as e:
        printDebugEx("ERROR get_online_version: ", e)


def download_latest(branch="master"):
    try:
        if get_online_version(branch):
            printDebug("Remote has changes, pulling...")
            subprocess.run(["git", "pull"], check=True)
            restart_app()
        else:
            printDebug("No remote changes.")
            return "TIDAK ADA UPDATE"
    except Exception as e:
        printDebugEx("ERROR download_latest: ", e)



# def download_latest():
#     print("Mengunduh versi terbaru...")
#     response = requests.get(MAIN_FILE_URL)
#     with open(LOCAL_FILE, 'wb') as f:
#         f.write(response.content)

def restart_app():
    printDebug("Menjalankan ulang aplikasi...")
    os.execv(sys.executable, ['python'] + sys.argv)

def check_for_update():
    return download_latest("master")
    # online_version = get_online_version()
    # print("VERSION ONLINE : " + str(online_version) + " = " + LOCAL_VERSION)
    # if online_version and online_version != LOCAL_VERSION:
    #     print(f"Versi baru tersedia: {online_version}")
    #     download_latest()
    #     restart_app()
    # else:
    #     print("Aplikasi sudah versi terbaru.")


############################### MYSQL FUNCTION #######################################
mydb = mysql.connector.connect(
  host="localhost",
  user="scola",
  password="scolaabsen",
  database="absensi"
)
mycursor = mydb.cursor()

def insertdata(tagRFID):
    global mycursor,mydb
    tag = tagRFID
    waktu = get_datetime()#datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    status = 0  # Misalnya 1 = Hadir

    # Query insert
    query = "INSERT INTO data_absen (tag, datetime, status) VALUES (%s, %s, %s)"
    values = (tag, waktu, status)

    # Eksekusi dan commit
    mycursor.execute(query, values)
    mydb.commit()
    return mycursor.lastrowid
    # print("Data berhasil disimpan, ID:", mycursor.lastrowid)

############################### LCD FUNCTION #######################################
I2C_ADDR  = 0x27 # I2C device address
LCD_WIDTH = 20   # Maximum characters per line

# Define some device constants
LCD_CHR = 1 # Mode - Sending data
LCD_CMD = 0 # Mode - Sending command

LCD_LINE_1 = 0x80 # LCD RAM address for the 1st line
LCD_LINE_2 = 0xC0 # LCD RAM address for the 2nd line
LCD_LINE_3 = 0x94 # LCD RAM address for the 3rd line
LCD_LINE_4 = 0xD4 # LCD RAM address for the 4th line

LCD_BACKLIGHT  = 0x08  # On
LCD_BACKLIGHT_OFF = 0x00  # Off



ENABLE = 0b00000100 # Enable bit

# Timing constants
E_PULSE = 0.0005
E_DELAY = 0.0005

#Open I2C interface
#bus = smbus.SMBus(0)  # Rev 1 Pi uses 0
bus = smbus.SMBus(3) # Rev 2 Pi uses 1

def lcd_init():
    try :
        # Initialise display
        lcd_byte(0x33,LCD_CMD) # 110011 Initialise
        lcd_byte(0x32,LCD_CMD) # 110010 Initialise
        lcd_byte(0x06,LCD_CMD) # 000110 Cursor move direction
        lcd_byte(0x0C,LCD_CMD) # 001100 Display On,Cursor Off, Blink Off 
        lcd_byte(0x28,LCD_CMD) # 101000 Data length, number of lines, font size
        lcd_byte(0x01,LCD_CMD) # 000001 Clear display
        time.sleep(1)
    except Exception as e:
        printDebugEx("ERROR lcd_init : ", e)

lcd_backlight_status = LCD_BACKLIGHT
last_scan_time = time.time()
# last_scan_time_rfid = {}
last_scan_time_qr = {}


def lcd_clear():
    lcd_byte(0x01,LCD_CMD) # 000001 Clear display

def lcd_byte(bits, mode):
  bits_high = mode | (bits & 0xF0) | lcd_backlight_status
  bits_low = mode | ((bits<<4) & 0xF0) | lcd_backlight_status

  # High bits
  bus.write_byte(I2C_ADDR, bits_high)
  lcd_toggle_enable(bits_high)

  # Low bits
  bus.write_byte(I2C_ADDR, bits_low)
  lcd_toggle_enable(bits_low)

def lcd_toggle_enable(bits):
  # Toggle enable
  time.sleep(E_DELAY)
  bus.write_byte(I2C_ADDR, (bits | ENABLE))
  time.sleep(E_PULSE)
  bus.write_byte(I2C_ADDR,(bits & ~ENABLE))
  time.sleep(E_DELAY)

def lcd_string(message,line):
  message = message.ljust(LCD_WIDTH," ")
  lcd_byte(line, LCD_CMD)
  for i in range(LCD_WIDTH):
    lcd_byte(ord(message[i]),LCD_CHR)


# ...existing code...
def post_to_localhost(endpoint: str, payload: Dict[str, Any], timeout: float = 5.0) -> Optional[Dict[str, Any]]:
    """
    Kirim POST JSON ke localhost.
    - endpoint: full URL (mis. 'http://localhost:8000/attendance') atau path ('/attendance').
    - payload: dict yang dikirim sebagai JSON.
    - timeout: detik.
    Mengembalikan dict hasil JSON atau None jika gagal.
    """
    if not endpoint.startswith("http"):
        endpoint = endpoint if endpoint.startswith("/") else "/" + endpoint
        endpoint = f"http://localhost:8080{endpoint}" if ":8080" not in endpoint else f"http://localhost{endpoint}"

    headers = {"Content-Type": "application/json"}
    try:
        resp = requests.post(endpoint, json=payload, headers=headers, timeout=timeout)
        resp.raise_for_status()
        try:
            return resp.json()
        except ValueError:
            return {"status_code": resp.status_code, "text": resp.text}
    except requests.RequestException as exc:
        print(f"[post_to_localhost] request error: {exc}")
        return None

def send_network_config(
    ethernet_mode: str = "dhcp",
    ip: str = "",
    subnet: str = "",
    gateway: str = "",
    endpoint: str = "/network/settings",
    timeout: float = 5.0,
) -> Optional[Dict[str, Any]]:
    """
    Kirim POST form-urlencoded ke localhost dengan payload:
      ethernet_mode=dhcp&ip=&subnet=&gateway=
    - endpoint: path (mis. '/network/settings') atau full URL.
    - mengembalikan JSON response sebagai dict, atau None jika gagal.
    """
    if not endpoint.startswith("http"):
        endpoint = endpoint if endpoint.startswith("/") else "/" + endpoint
        endpoint = f"http://localhost:8080{endpoint}"

    data = {
        "ethernet_mode": ethernet_mode,
        "ip": ip,
        "subnet": subnet,
        "gateway": gateway,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    try:
        resp = requests.post(endpoint, data=data, headers=headers, timeout=timeout)
        resp.raise_for_status()
        try:
            return resp.json()
        except ValueError:
            return {"status_code": resp.status_code, "text": resp.text}
    except requests.RequestException as exc:
        print(f"[send_network_config] request error: {exc}")
        return None

############################### GPIO FUNCTION #######################################
class GPIOControl:
    def __init__(self):
        pass

    def read(self, pin_number):
        command = ["gpio", "read", str(pin_number)]
        result = subprocess.check_output(command).decode().strip()
        return int(result)

    def write(self, pin_number, value):
        command = f"gpio write {pin_number} {value}"
        result = os.system(command)

    def mode(self, pin_number, mode):
        command = f"gpio mode {pin_number} {mode}"
        result = os.system(command)

    def readm(self, pin_numbers):
        for pin_number in pin_numbers:
            if 0 <= pin_number <= 20: # Ensure the pin number is within the valid range
                value = self.read(pin_number)
                printDebug(f"Pin {pin_number} value: {value}")
            else:
                printDebug(f"Invalid pin number: {pin_number}")



############################### NETWORK FUNCTION #######################################
def get_interface_ip(interface_name):
    """
    Retrieves the IPv4 address for a specified network interface.
    Returns None if the interface or address is not found.
    """
    try:
        # Get addresses for the specified interface
        addresses = netifaces.ifaddresses(interface_name)
        # Check if IPv4 addresses exist for this interface
        if netifaces.AF_INET in addresses:
            # Return the first IPv4 address found
            return addresses[netifaces.AF_INET][0]['addr']
    except Exception as e:
        printDebugEx("ERROR get_interface_ip : ", e)
    return None

def get_interface_mac(interface_name):
    """
    Retrieves the IPv4 address for a specified network interface.
    Returns None if the interface or address is not found.
    """
    try:
        # Get addresses for the specified interface
        addresses = netifaces.ifaddresses(interface_name)
        # Check if IPv4 addresses exist for this interface
        if netifaces.AF_INET in addresses:
            # Return the first IPv4 address found
            return addresses[netifaces.AF_LINK][0]['addr']
    except Exception as e:
        printDebugEx("ERROR get_interface_mac : ", e)
    return None

def get_ssid_nmcli():
    try:
        output = subprocess.check_output("nmcli -t -f active,ssid dev wifi", shell=True, encoding="utf-8")
        for line in output.strip().split("\n"):
            if line.startswith("yes:"):
                return line.split(":")[1]
        return None
    except Exception as e:
        printDebugEx("ERROR get_ssid_nmcli: ", e)

def cek_internet(url='https://www.google.com/', timeout=5):
    try:
        _ = requests.get(url, timeout=timeout)
        return True
    except Exception as e:
        printDebugEx("ERROR START 3: ", e)
    
# Fungsi ambil MAC address
def get_mac():
    mac = uuid.getnode()
    return ':'.join(['{:02x}'.format((mac >> ele) & 0xff) for ele in range(40, -1, -8)])

# Fungsi ambil uptime
def get_uptime():
    boot_time = datetime.fromtimestamp(psutil.boot_time())
    now = datetime.now()
    uptime = now - boot_time
    return str(uptime).split('.')[0]  # Hapus microseconds

# Fungsi ambil data sistem
threadStatus=[0,0,0,0]
def get_system_info():
    global threadStatus
    return {
        "app_version": LOCAL_VERSION,
        "mac_address": get_mac().replace(":", ""),  # Bisa juga tetap pakai ":"
        "ip_address_wlan": (wlan_ip if wlan_ip else "-"),
        "ip_address_eth": (eth_ip if eth_ip else "-"),
        "cpu_percent": psutil.cpu_percent(interval=1),
        "memory_percent": psutil.virtual_memory().percent,
        "storage_percent": psutil.disk_usage('/').percent,
        "uptime": get_uptime(),
        "device": platform.node(),  # nama host/device
        "thread_display" : threadStatus[1],
        "thread_rfid" : threadStatus[2],
        "thread_send" : threadStatus[3]
    }


############################### CONFIG FUNCTION #######################################
script_dir = os.path.dirname(os.path.abspath(__file__))
file_name = 'setting.json' 
file_path = os.path.join(script_dir, file_name)       
with open(file_path, 'r') as file:
    dataSetting= json.load(file)

file_name = 'ota.json'
file_path = os.path.join(script_dir, file_name)       
with open(file_path, 'r') as file:
    dataOTA= json.load(file)

VERSION_FILE_URL = dataOTA['ota-version']
MAIN_FILE_URL = dataOTA['ota-app']
LOCAL_VERSION = "1.1.7"
LOCAL_FILE = 'absensi.py'
MACHINE_ID = dataSetting['machine-id']
API_HOST = dataSetting['api-server']

# QR Device configuration
QR_CONFIG = dataSetting.get('qr_device', {'enabled': False, 'device_id': '', 'device_path': '', 'device_name': 'No QR Scanner'})
QR_ENABLED = QR_CONFIG.get('enabled', False)
QR_DEVICE_ID = QR_CONFIG.get('device_id', '')
QR_DEVICE_PATH = QR_CONFIG.get('device_path', '')

BUZZER = 5
BUTTON = 7
button_pressed_time = 0  # buat catat kapan ditekan


def on_connect(client, userdata, flags, rc, properties):
    now = datetime.now()
    formatted_datetime_1 = now.strftime("%Y-%m-%d  %H:%M:%S")
    client.publish(topicPublish, "STARTING " + formatted_datetime_1)
    client.subscribe(topicSubscribe)
    client.subscribe(topicSubscribeAll)

# Fungsi: Jalankan ulang aplikasi Python saat ini
def restart_app():
    printDebug("Menjalankan ulang aplikasi...")
    python = sys.executable
    os.execl(python, python, *sys.argv)

# Fungsi: Restart komputer (Linux)
def restart_computer():
    printDebug("Merestart komputer...")
    subprocess.run(["sudo", "reboot"])

# Fungsi: Update aplikasi dari repo Git
def update_app():
    printDebug("Melakukan update aplikasi...")
    check_for_update()

# Mapping perintah ke fungsi
command_map = {
    "reload": restart_app,
    "reboot": restart_computer,
    "update": update_app
}
    
def on_disconnect(client, userdata, rc, properties=None):
    print("⚠️ Terputus dari broker (rc={}), mencoba reconnect...".format(rc))
    while True:
        try:
            clientMQTT.reconnect()
            printDebug("🔁 Reconnected!")
            break
        except:
            printDebug("⏳ Gagal reconnect, coba lagi 5 detik...")
            time.sleep(5)

def on_message(client, userdata, msg):
    try:
        cmd = msg.payload.decode().strip().lower()
        printDebug(f"Perintah diterima: {cmd}")

        if cmd in command_map:
            command_map[cmd]()  # Jalankan fungsi sesuai perintah
        else:
            printDebug("Perintah tidak dikenali.")
    except Exception as e:
        printDebugEx("Error saat menjalankan perintah:", e)


try :
    # clientMQTT = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, "123")
    clientMQTT = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,client_id="test-client")
    clientMQTT.on_connect = on_connect
    clientMQTT.on_disconnect = on_disconnect
    clientMQTT.on_message = on_message
    clientMQTT.connect(broker, port)
except Exception as e:
    printDebug("Error MQTT:", e)   


# Menjadwalkan fungsi setiap hari jam 23:30

try :
    # eth_mac = str(get_interface_mac('eth0'))
    eth_mac = get_mac().replace(":","")
    printDebug("VERSION     : " + LOCAL_VERSION)
    printDebug("API SERVER  : " + API_HOST)
    printDebug("MACHINE ID  : " + MACHINE_ID)
    printDebug("MACADDRESS  : " + eth_mac)
    printDebug("OTA VERSION : " + VERSION_FILE_URL)
    printDebug("OTA APP     : " + MAIN_FILE_URL)
    printDebug("VER HARD    : " + "1.0.1")

    tagRFID=""
    statusInsert=0
    statusInternet="OFFLINE"

    topicPublish = "scola/absensi/"+eth_mac
    topicSubscribe = "scola/absensi/"+eth_mac+"/subs"
    topicSubscribeAll = "scola/absensi/subscribe"
except Exception as e:
    printDebugEx("Error MQTT:", e)   

try :
    gpio_control = GPIOControl()
    gpio_control.mode(BUZZER, "out") #pin 11 PC6
    gpio_control.mode(BUTTON, "in") #pin13 PC5
    #gpio_control.mode(BUTTON, "up") #pin13 PC5
    lcd_init()
    lcd_clear()
    
   
    

    ssid = get_ssid_nmcli()
    printDebug("SSID:", ssid if ssid else "Tidak terhubung")
    if cek_internet(API_HOST,3) : 
        statusInternet = "ONLINE"
        lcd_string("CHECK UPDATE ....", LCD_LINE_1)
        lcd_string("LOADING ...", LCD_LINE_2)
        lcd_string(check_for_update(), LCD_LINE_3)
        sync_rtc_with_system()
except Exception as e:
    printDebugEx("ERROR START 1: ", e)   
    
try : 
    reader = SimpleMFRC522()
    wlan_ip = get_interface_ip('wlan0')  # Common on Linux/Raspberry Pi
    if not wlan_ip:
        wlan_ip = get_interface_ip('Wi-Fi') # Common on Windows

    # Get IP for Ethernet (common names: eth0, Ethernet)
    eth_ip = get_interface_ip('eth0')  # Common on Linux/Raspberry Pi
    
    if not eth_ip:
        eth_ip = get_interface_ip('Ethernet') # Common on Windows
except Exception as e:
    printDebugEx("ERROR START 2: ", e)   

try : 
    reader = SimpleMFRC522()
except Exception as e:
    printDebugEx("ERROR START 3: ", e)

displayPage=0
displayMaxPage=1
jumlahDataNotSend=0

siswaNis = ""
siswaNama = ""

def display():
    try:
        global tagRFID,statusInternet,statusInsert,displayPage,displayMaxPage,threadStatus,last_scan_time,lcd_backlight_status,button_pressed_time,statusSend,siswaNis,siswaNama
        lcd_clear()
        lcd_string("   SCOLA ABSEN", LCD_LINE_1)
        lcd_string("FW V." + LOCAL_VERSION + " " + MACHINE_ID, LCD_LINE_2)
        lcd_string("W:" + (wlan_ip if wlan_ip else "-"), LCD_LINE_3)
        lcd_string("E:" + (eth_ip if eth_ip else "-"), LCD_LINE_4)
        # lcd_string("SSID: " + (ssid if ssid else "-"), LCD_LINE_4)
        time.sleep(2)
        lcd_clear()
        tick=True
        countTick=0
        
        while True:
            now = datetime.now()

            # Cek sleep backlight
            if time.time() - last_scan_time > 60:
                lcd_backlight_status = LCD_BACKLIGHT_OFF
            else:
                lcd_backlight_status = LCD_BACKLIGHT

            # Cek tombol
            button_state = gpio_control.read(BUTTON)
            if button_state == 1:  # ditekan
                last_scan_time=  time.time()        # Catat waktu scan display
                lcd_backlight_status = LCD_BACKLIGHT
                if button_pressed_time == 0:
                    button_pressed_time = time.time()
                else:
                    held_time = time.time() - button_pressed_time
                    if held_time >= 5:
                        lcd_clear()
                        lcd_string("TOMBOL DITEKAN", LCD_LINE_1)
                        lcd_string("SETTING DEFAULT", LCD_LINE_2)
                        lcd_string("RESTARTING....", LCD_LINE_3)
                        lcd_string("TUNGGU +-3 MENIT", LCD_LINE_4)
                        print(send_network_config(ethernet_mode="dhcp", ip="", subnet="", gateway="", endpoint="/save_ethernet"))
                        time.sleep(2)
                        #setdafault
                        restart_computer()
            else:
                if button_pressed_time != 0:
                    held_time = time.time() - button_pressed_time
                    if held_time < 5:
                        # Tombol dilepas cepat ➜ ganti page
                        lcd_clear()
                        displayPage += 1
                        if displayPage > displayMaxPage:
                            displayPage = 0
                    button_pressed_time = 0
            
            # print(threadStatus[1])
            if displayPage==0 :
                lcd_string(str(get_datetime()),LCD_LINE_1)
                message1 = " SILAHKAN TAP KARTU  "
                if QR_ENABLED:
                    message1 = " SILAHKAN  TAP/SCAN "
                    message2 = " KARTU RFID/QR CODE "
                if tick :
                    lcd_string(message1,LCD_LINE_2)
                    lcd_string(message2,LCD_LINE_3)
                else :
                    lcd_string("           ",LCD_LINE_2)
                    lcd_string("           ",LCD_LINE_3)

                lcd_string("I:"+statusInternet+" D:"+str(jumlahDataNotSend),LCD_LINE_4)
                

            if displayPage==1 :
                lcd_string("FW V." + LOCAL_VERSION + " " + MACHINE_ID, LCD_LINE_1)
                lcd_string("S : " + str(ssid),LCD_LINE_2)  
                lcd_string("W : " + str(wlan_ip),LCD_LINE_3)  
                lcd_string("E : " + str(eth_ip),LCD_LINE_4)  
            
            time.sleep(0.5)
            tick = not tick
            countTick += 1

            if countTick>10 :
                lcd_clear()
                # displayPage +=1
                countTick=0

            if displayPage > displayMaxPage:
                displayPage=0

            if tagRFID == "xxx" :
               lcd_clear()
               lcd_string(" ANDA SUDAH ABSEN ", LCD_LINE_2)
               lcd_string("  TUNGGU 5 MENIT ", LCD_LINE_3)
               tagRFID=""
               time.sleep(2)
               lcd_clear()
            elif tagRFID != "" :
               lcd_clear()
               lcd_string("NO : " + tagRFID,LCD_LINE_2)  
               lcd_string("   BERHASIL ABSEN",LCD_LINE_1) 
               lcd_string("ID : " + str(statusInsert),LCD_LINE_3) 
               tagRFID=""
               time.sleep(2)
               lcd_clear()
            
            if statusSend == 1 :
                statusSend=0
                lcd_clear()
                lcd_string("INFORMASI ",LCD_LINE_1) 
                lcd_string("NIS  :" + siswaNis,LCD_LINE_2)  
                lcd_string("NAMA :" + siswaNama,LCD_LINE_3) 
                time.sleep(1.5)
                lcd_clear()
            
            if statusSend == 2 :
                statusSend=0
                lcd_clear()
                lcd_string("INFORMASI ",LCD_LINE_1) 
                lcd_string("ERROR :" + siswaNama,LCD_LINE_2)  
                time.sleep(1.5)
                lcd_clear()
               
            threadStatus[1]= get_datetime()
            # if gpio_control.read(BUTTON)=='0' :
            #     displayPage = displayPage + 1
            #     print("PAGE " + displayPage)
            # #     if displayPage > displayMaxPage:
            # #         displayPage=0
            #     time.sleep(1)
            
    except Exception as e:
        printDebugEx("ERROR display : ", e)
        traceback.print_exc()
statusSend=0
last_scan_time_rfid = {}
def rfid():
    try:
        global tagRFID,statusInsert,threadStatus,last_scan_time_rfid,lcd_backlight_status,last_scan_time
        while True:
            threadStatus[2]=get_datetime()
            printDebug("Hold a tag near the reader")
            id,text = reader.read()
            printDebug("ID: %s" % (tagRFID))
            uid_bytes = id.to_bytes(8, 'big')
            uid_4bytes = uid_bytes[3:7]
            tag_hex = ''.join(f'{b:02x}' for b in uid_4bytes)
            tagRFID = str(tag_hex)
            printDebug("ID: %s" % (tagRFID))
    

            now = datetime.now()
            last_time = last_scan_time_rfid.get(tagRFID)
            printDebug(last_scan_time_rfid)
            # Jika tag pernah di scan
            if last_time:
                elapsed = now - last_time
                if elapsed < timedelta(minutes=1):
                    printDebug(f"Tag {tagRFID} baru di-scan {elapsed} lalu. Abaikan.")
                    tagRFID = "xxx"
                    gpio_control.write(5, 1)
                    sleep(1)
                    gpio_control.write(5, 0)
                    continue  # skip ke loop berikutnya
                      
            statusInsert = insertdata(tagRFID)
            last_scan_time_rfid[tagRFID] = now        # Catat waktu scan
            last_scan_time=  time.time()        # Catat waktu scan display
            lcd_backlight_status = LCD_BACKLIGHT  # Hidupkan backlight kalau scan

            gpio_control.write(5, 1)
            sleep(1)
            gpio_control.write(5, 0)
            clientMQTT.publish(topicPublish+"/tag", tagRFID)
            #tidak bisa tap lagi jika kartu belum di angkat atau dalam 1 jam 

    except Exception as e:
        printDebugEx("ERROR RFID : ", e) 

def send():
    try:
        global tagRFID,MACHINE_ID,API_HOST,statusInternet,jumlahDataNotSend,threadStatus,statusSend,siswaNis,siswaNama
        while True:
            threadStatus[3]=get_datetime()
            query = "SELECT COUNT(*) FROM data_absen where status=0"
            mycursor.execute(query)
            jumlahData = mycursor.fetchone()[0]
            jumlahDataNotSend = jumlahData

            if cek_internet(API_HOST,3) : 
                statusInternet = "ONLINE"
                #check data yang belum ke kirim di database
                mycursor.execute("SELECT * FROM data_absen WHERE status=0 ORDER BY id ASC LIMIT 1")
                row = mycursor.fetchone()
    
                if row:
                    id = row[0]
                    kartu = row[1]
                    waktu = row[2]

                    payload = json.dumps({
                    "mesin": str(MACHINE_ID),
                    "kartu": str(kartu),
                    "waktu": str(waktu)
                    })
                    headers = {
                    'Content-Type': 'application/json'
                    }
                    response = requests.request("POST", API_HOST, headers=headers, data=payload)
                    printDebug(payload)
                    printDebug(response.text)

                    try:
                        res_json = response.json()
                        status = res_json.get("status", False)
                        message = res_json.get("message", "")
                        jadwal = res_json.get("data", {}).get("jadwal", "")
                        siswaNama = res_json.get("data", {}).get("nama", "")
                        siswaNis = res_json.get("data", {}).get("no", "")
                        jadwal = jadwal or ""
                        siswaNama = siswaNama or ""
                        siswaNis = siswaNis or ""
                        if status:
                            printDebug("✅ Status: Berhasil")
                            printDebug("Pesan  : " + message)
                            printDebug("Jadwal : " + jadwal)
                            query = "DELETE FROM data_absen WHERE id = %s"
                            mycursor.execute(query, (id,))
                            mydb.commit()
                            printDebug(f"Data dengan ID {id} berhasil dihapus.")
                            statusSend=1
                        else:
                            StatusError = res_json.get("error", "")
                            # siswaNis = res_json.get("statusCode","")
                            printDebug("❌ Status: Gagal")
                            printDebug("Pesan : " +  message)
                            printDebug("Error : " +  StatusError)
                            statusSend=2
                            siswaNama = "API URL SALAH"
                            
                            if StatusError!="Not Found" :
                                siswaNama = message
                                message = message.replace("'", "").replace('"', "")
                                query = "UPDATE data_absen SET status = 2,keterangan = '"+message+"' WHERE id = %s"
                                mycursor.execute(query, (id,))
                                mydb.commit()
                                
                            

                    except ValueError:
                        printDebug("⚠️ Response bukan format JSON yang valid:")
                        printDebug(response.text)
                #else:
                    #print("Data tidak ditemukan.")

                #jika sukses maka di delete
                
            else :
                statusInternet = "OFFLINE"

            
            time.sleep(5)
    except Exception as e:
        printDebugEx("ERROR SEND : ", e)

def heartBeat():
    while True:
        try:
            # print ("kirim heart")
            dataSystem = get_system_info()
            payload = json.dumps(dataSystem)
            clientMQTT.publish(topicPublish+"/heart", payload)
            # print ("kirim heartx")
            time.sleep(30)
            # print ("kirim heartxx")
        except Exception as e:
            printDebugEx("ERROR HeartBeat : ", e)

def mqttThread():
    try:
        clientMQTT.loop_forever()  # listen terus
    except Exception as e:
        printDebugEx("ERROR MQTT : ", e)


statusCamera=True
def camThread():
    try:
        global tagRFID,statusInsert, last_scan_time_qr, lcd_backlight_status, last_scan_time, statusCamera
        
        # Check if QR scanner is enabled
        if not QR_ENABLED or not QR_DEVICE_PATH:
            printDebug("QR Scanner disabled in configuration")
            statusCamera = False
            return
            
        # ganti dengan device QR reader kamu
        # dev = InputDevice('/dev/input/by-id/usb-YuRiot_ScanCode_Box_00000000011C-event-kbd')
        try:
            dev = InputDevice(QR_DEVICE_PATH)
            printDebug(f"QR Scanner initialized: {QR_DEVICE_PATH}")
        except Exception as e:
            printDebugEx(f"Failed to initialize QR device {QR_DEVICE_PATH}: ", e)
            statusCamera = False
            return
            
        buffer = ''

        for event in dev.read_loop():
            if event.type == ecodes.EV_KEY:
                data = categorize(event)
                if data.keystate == 1:  # key down
                    key = data.keycode
                    if key == 'KEY_ENTER':
                        print("QR Code scanned:", buffer)
                        now = datetime.now()
                        qr_data = buffer
                        last_time = last_scan_time_qr.get(qr_data)
                        printDebug(last_scan_time_qr)
                        tagRFID = qr_data
                        if last_time :
                            elapsed = now - last_time
                            if elapsed < timedelta(minutes=1):
                                print(f"Tag {tagRFID} baru di-scan {elapsed} lalu. Abaikan.")
                                tagRFID = "xxx"
                                gpio_control.write(5, 1)
                                sleep(1)
                                gpio_control.write(5, 0)
                                continue  # skip ke loop berikutnya

                        statusInsert = insertdata(qr_data)
                        last_scan_time_qr[qr_data] = now
                        last_scan_time = time.time()
                        lcd_backlight_status = LCD_BACKLIGHT
                        gpio_control.write(5, 1)
                        sleep(1)
                        gpio_control.write(5, 0)
                        clientMQTT.publish(topicPublish + "/tag", qr_data)
                        buffer = ''
                    elif key.startswith('KEY_'):
                        # ambil karakter terakhir dari keycode, simple mapping
                        char = key.replace('KEY_', '')
                        if len(char) == 1:
                            buffer += char.lower()  # sesuaikan jika huruf besar/kecil
    # global tagRFID,statusInsert, last_scan_time_qr, lcd_backlight_status, last_scan_time, statusCamera
    # cap = cv2.VideoCapture(1)
    # if not cap.isOpened():
    #     statusCamera=False
    #     printDebug("❌ Tidak bisa membuka kamera QR Code.")
    #     return

    # printDebug("📡 QR Code scanner aktif...")
    # try:
    #     while True:
    #         ret, frame = cap.read()
    #         if not ret:
    #             sleep(0.5)
    #             continue

    #         decoded_objects = decode(frame)
    #         for obj in decoded_objects:
    #             qr_data = obj.data.decode("utf-8")
    #             now = datetime.now()

    #             last_time = last_scan_time_qr.get(qr_data)
    #             printDebug(last_scan_time_qr)
    #             tagRFID = qr_data
    #             if last_time :
    #                 elapsed = now - last_time
    #                 if elapsed < timedelta(minutes=1):
    #                     print(f"Tag {tagRFID} baru di-scan {elapsed} lalu. Abaikan.")
    #                     tagRFID = "xxx"
    #                     gpio_control.write(5, 1)
    #                     sleep(1)
    #                     gpio_control.write(5, 0)
    #                     continue  # skip ke loop berikutnya

    #             statusInsert = insertdata(qr_data)
    #             last_scan_time_qr[qr_data] = now
    #             last_scan_time = time.time()
    #             lcd_backlight_status = LCD_BACKLIGHT
    #             gpio_control.write(5, 1)
    #             sleep(1)
    #             gpio_control.write(5, 0)
    #             clientMQTT.publish(topicPublish + "/tag", qr_data)

    #         sleep(0.1)

    except KeyboardInterrupt:
        printDebug("🛑 QR scanner berhenti")
    except Exception as e:
        printDebugEx("ERROR QR Scanner: ", e)

scheduler = BackgroundScheduler()
scheduler.add_job(restart_computer, 'cron', hour=23, minute=30)
scheduler.start()

if __name__ == '__main__':
  # Create requirements.txt file if it doesn't exist
  if not os.path.exists("requirements.txt"):
      create_requirements_file()
  
  try:
    # main()
    print("🚀 Starting Absensi Application...")
    print("📦 All required modules loaded successfully!")
    
    t1 = threading.Thread(target=display, args=())
    t2 = threading.Thread(target=rfid, args=())
    t3 = threading.Thread(target=send, args=())
    t4 = threading.Thread(target=mqttThread, args=())
    t5 = threading.Thread(target=heartBeat, args=())
    t6 = threading.Thread(target=camThread, args=())

    t1.start()
    t2.start()
    t3.start()
    t4.start()
    t5.start()

    # Only start QR scanner thread if enabled in configuration
    if QR_ENABLED and QR_DEVICE_PATH:
        printDebug(f"Starting QR Scanner thread with device: {QR_DEVICE_PATH}")
        t6.start()
    else:
        printDebug("QR Scanner disabled - camThread will not start")
        statusCamera = False
    
    statusThread = True
    while True:
        if not t1.is_alive():
            statusThread=False
            printDebug("display Mati")
        if not t2.is_alive():
            statusThread=False
            printDebug("rfid Mati")
        if not t3.is_alive():
            # statusThread=False
            printDebug("send Mati")
        if not t4.is_alive():
            # statusThread=False
            printDebug("mqtt Mati")
        if not t5.is_alive():
            statusThread=False
            printDebug("heartbeat Mati")
        # Only check QR thread if it was started
        try:
            if QR_ENABLED and QR_DEVICE_PATH and not t6.is_alive():
                #statusThread=False
                printDebug("CamThread Mati")
        except (NameError, UnboundLocalError):
            # QR variables not defined, skip check
            pass
        time.sleep(30)
        read_rtc_time()
        if statusThread==False :
            statusThread=True
            restart_app()
  except Exception as e:
    printDebugEx("ERROR START: ", e)
  except ImportError as e:
    print(f"❌ Import Error: {e}")
    print("🔧 Some required modules are missing!")
    print("📋 Try installing with:")
    print("   pip3 install -r requirements.txt")
    print("🔧 Or install individual packages:")
    print("   pip3 install evdev paho-mqtt mysql-connector-python")
    print("   pip3 install requests netifaces psutil APScheduler")
    print("   pip3 install opencv-python pyzbar mfrc522 smbus2")
    sys.exit(1)
    t5 = threading.Thread(target=heartBeat, args=())
    t6 = threading.Thread(target=camThread, args=())

    t1.start()
    t2.start()
    t3.start()
    t4.start()
    t5.start()

    # Only start QR scanner thread if enabled in configuration
    if QR_ENABLED and QR_DEVICE_PATH:
        printDebug(f"Starting QR Scanner thread with device: {QR_DEVICE_PATH}")
        t6.start()
    else:
        printDebug("QR Scanner disabled - camThread will not start")
        statusCamera = False
    
    statusThread = True
    while True:
        if not t1.is_alive():
            statusThread=False
            printDebug("display Mati")
        if not t2.is_alive():
            statusThread=False
            printDebug("rfid Mati")
        if not t3.is_alive():
            # statusThread=False
            printDebug("send Mati")
        if not t4.is_alive():
            # statusThread=False
            printDebug("mqtt Mati")
        if not t5.is_alive():
            statusThread=False
            printDebug("heartbeat Mati")
        # Only check QR thread if it was started
        if QR_ENABLED and QR_DEVICE_PATH and not t6.is_alive():
            #statusThread=False
            printDebug("CamThread Mati")
            #threads.remove(t)
            #start_thread(i)
        time.sleep(30)
        read_rtc_time()
        if statusThread==False :
            statusThread=True
            restart_app()
  except Exception as e:
    printDebugEx("ERROR MAIN: ", e)

