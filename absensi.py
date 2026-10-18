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
import shutil
import tempfile
import fcntl
import glob
from functools import wraps

# Bus I2C untuk LCD dan RTC pada perangkat Orange Pi LTS ini.
I2C_BUS = 0

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
        "ntplib>=0.4.0",
        "netifaces>=0.11.0", 
        "mysql-connector-python>=8.0.0",
        "APScheduler>=3.8.0",
        "paho-mqtt>=1.5.0",
        "psutil>=5.8.0",
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
from urllib.parse import urlparse

# Keep the installed board-compatible MFRC522 driver.
SimpleMFRC522 = None
try:
    from mfrc522 import SimpleMFRC522
except Exception as error:
    print('[WARN] MFRC522 driver belum tersedia/cocok:', error, flush=True)

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
    from evdev import InputDevice, categorize, ecodes
except ImportError:
    if install_package("evdev"):
        from evdev import InputDevice, categorize, ecodes



#broker = "pentarium.id"   # bisa juga pakai localhost atau IP broker sendiri
broker = "100.83.195.99"   # bisa juga pakai localhost atau IP broker sendiri
port = 1883
statusInternet="OFFLINE"

def printDebug(*args):
    text = " ".join(str(a) for a in args)
    print(f"[{get_datetime()}] {text}", flush=True)

def printDebugEx(text, e):
    print(f"[{get_datetime()}] {text} {str(e)}", flush=True)
    traceback.print_exc()
# Hardware status is independent of Internet/NTP availability.
hardware_lock = threading.RLock()
hardware_status = {'lcd': False, 'rtc': False, 'rfid': False, 'gpio': False}


def set_hardware_status(name, ready):
    with hardware_lock:
        hardware_status[name] = bool(ready)


def hardware_blink_interval():
    with hardware_lock:
        return 1.0 if all(hardware_status.values()) else 0.2


############################### RTC FUNCTION #######################################
def bcd_to_dec(bcd):
    return (bcd // 16) * 10 + (bcd % 16)

def dec_to_bcd(val):
    return (val // 10) << 4 | (val % 10)

# Once NTP succeeds, keep using the synchronized system clock even offline.
ntp_synchronized = False
rtc_lock = threading.RLock()

def read_rtc_time(bus_num=I2C_BUS, address=0x68):
    """Return datetime or None; RTC failures must never break logging."""
    rtc_bus = None
    with rtc_lock:
        try:
            rtc_bus = smbus.SMBus(bus_num)
            data = rtc_bus.read_i2c_block_data(address, 0x00, 7)
            if data[0] & 0x80:  # DS1307 oscillator stopped
                set_hardware_status("rtc", False)
                return None
            second = bcd_to_dec(data[0] & 0x7F)
            minute = bcd_to_dec(data[1] & 0x7F)
            if data[2] & 0x40:  # 12-hour mode
                hour = bcd_to_dec(data[2] & 0x1F) % 12
                hour += 12 if data[2] & 0x20 else 0
            else:
                hour = bcd_to_dec(data[2] & 0x3F)
            result = datetime(2000 + bcd_to_dec(data[6]),
                            bcd_to_dec(data[5] & 0x1F),
                            bcd_to_dec(data[4]), hour, minute, second)
            set_hardware_status("rtc", True)
            return result
        except Exception:
            set_hardware_status("rtc", False)
            return None
        finally:
            if rtc_bus is not None:
                try:
                    rtc_bus.close()
                except Exception:
                    pass

def set_system_time(timestamp):
    """Linux clock update; requires root or CAP_SYS_TIME."""
    time.clock_settime(time.CLOCK_REALTIME, timestamp)

def sync_time_with_rtc():
    if ntp_synchronized:
        return False
    dt = read_rtc_time()
    if not isinstance(dt, datetime):
        return False
    try:
        set_system_time(dt.timestamp())
        return True
    except Exception as e:
        printDebug("ERROR RTC sync_time_with_rtc:", e)
        return False

def sync_rtc_with_system():
    rtc_bus = None
    with rtc_lock:
        try:
            rtc_bus = smbus.SMBus(I2C_BUS)
            now = datetime.now()
            rtc_bus.write_i2c_block_data(0x68, 0x00, [
                dec_to_bcd(now.second), dec_to_bcd(now.minute),
                dec_to_bcd(now.hour), dec_to_bcd(now.isoweekday()),
                dec_to_bcd(now.day), dec_to_bcd(now.month),
                dec_to_bcd(now.year - 2000)
            ])
            return True
        except Exception as e:
            printDebug("RTC tidak tersedia; tetap memakai jam lokal:", e)
            return False
        finally:
            if rtc_bus is not None:
                try:
                    rtc_bus.close()
                except Exception:
                    pass

def get_datetime():
    dt = None
    if not ntp_synchronized:
        try:
            dt = read_rtc_time()
        except Exception:
            pass
    if not isinstance(dt, datetime):
        dt = datetime.now()
    return dt.strftime('%Y-%m-%d %H:%M:%S')

def sync_time_with_ntp():
    global ntp_synchronized
    import ntplib
    for server in ('pool.ntp.org', 'time.google.com'):
        try:
            response = ntplib.NTPClient().request(server, version=4, timeout=3)
            if response.leap == 3 or not 1 <= response.stratum <= 15:
                raise ValueError("Server NTP belum sinkron")
            set_system_time(time.time() + response.offset)
            ntp_synchronized = True
            printDebug("Jam lokal berhasil sinkron NTP:", server)
            sync_rtc_with_system()
            return True
        except Exception as e:
            printDebug("Sinkron NTP gagal:", server, e)
    return False

def time_sync_worker():
    # Independent of API/MySQL status: NTP itself checks connectivity.
    try:
        import ntplib
    except ImportError:
        if not install_package("ntplib"):
            printDebug("NTP belum aktif. Pasang: pip3 install ntplib")
            return
    while True:
        try:
            synced = sync_time_with_ntp()
        except Exception as e:
            printDebug("ERROR NTP:", e)
            synced = False
        # Retry after reconnect within 30s; successful sync repeats hourly.
        time.sleep(3600 if synced else 30)


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


        
def get_online_version(branch="zerolts") : 
    try:
        subprocess.run(["git", "fetch"], check=True)
        
        # Bandingkan HEAD lokal dengan remote
        local = subprocess.check_output(["git", "rev-parse", branch]).strip()
        remote = subprocess.check_output(["git", "rev-parse", f"origin/{branch}"]).strip()
        
        return local != remote
    except Exception as e:
        printDebugEx("ERROR get_online_version: ", e)


def download_latest(branch="zerolts"):
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
    return download_latest("zerolts")
    # online_version = get_online_version()
    # print("VERSION ONLINE : " + str(online_version) + " = " + LOCAL_VERSION)
    # if online_version and online_version != LOCAL_VERSION:
    #     print(f"Versi baru tersedia: {online_version}")
    #     download_latest()
    #     restart_app()
    # else:
    #     print("Aplikasi sudah versi terbaru.")


############################### MYSQL FUNCTION #######################################
def init_mysql_connection():
    """Initialize MySQL connection with error handling"""
    try:
        mydb = mysql.connector.connect(
            host="localhost",
            user="scola",
            password="scolaabsen",
            database="absensi",
            autocommit=False,
            connection_timeout=10,
            auth_plugin='mysql_native_password'
        )
        mycursor = mydb.cursor()
        return mydb, mycursor
    except Exception as e:
        printDebugEx("ERROR init_mysql_connection: ", e)
        return None, None

def ensure_mysql_connection():
    """Ensure MySQL connection is alive, reconnect if needed"""
    global mydb, mycursor
    try:
        if mydb is None or not mydb.is_connected():
            printDebug("Reconnecting to MySQL...")
            mydb, mycursor = init_mysql_connection()
            if mydb is None:
                return False
        
        # Test connection with a simple query
        mycursor.execute("SELECT 1")
        mycursor.fetchone()
        return True
    except Exception as e:
        printDebugEx("ERROR ensure_mysql_connection: ", e)
        try:
            mydb, mycursor = init_mysql_connection()
            return mydb is not None
        except:
            return False

# Initialize connection
mydb, mycursor = init_mysql_connection()

def insertdata(tagRFID):
    global mycursor, mydb
    try:
        if not ensure_mysql_connection():
            printDebug("MySQL connection failed, cannot insert data")
            return None
            
        tag = tagRFID
        waktu = get_datetime()
        status = 0  # Misalnya 1 = Hadir

        # Query insert
        query = "INSERT INTO data_absen (tag, datetime, status) VALUES (%s, %s, %s)"
        values = (tag, waktu, status)

        # Eksekusi dan commit
        mycursor.execute(query, values)
        mydb.commit()
        return mycursor.lastrowid
        
    except mysql.connector.Error as e:
        printDebugEx("MySQL error in insertdata: ", e)
        # Try to reconnect and retry once
        try:
            if ensure_mysql_connection():
                mycursor.execute(query, values)
                mydb.commit()
                return mycursor.lastrowid
        except Exception as retry_e:
            printDebugEx("Retry failed in insertdata: ", retry_e)
        return None
    except Exception as e:
        printDebugEx("ERROR insertdata: ", e)
        return None

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

# Missing I2C must not prevent GPIO/RFID and recovery threads from starting.
bus = None
lcd_lock = threading.RLock()


def open_lcd_bus():
    global bus
    if bus is None:
        bus = smbus.SMBus(I2C_BUS)
    return bus

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
        set_hardware_status("lcd", True)
        return True
    except Exception as e:
        set_hardware_status("lcd", False)
        printDebugEx("ERROR lcd_init : ", e)
        return False

lcd_backlight_status = LCD_BACKLIGHT
last_scan_time = time.time()
# last_scan_time_rfid = {}
last_scan_time_qr = {}


def lcd_clear():
    lcd_byte(0x01,LCD_CMD) # 000001 Clear display

def lcd_byte(bits, mode):
    global bus
    with lcd_lock:
        try:
            open_lcd_bus()
            bits_high = mode | (bits & 0xF0) | lcd_backlight_status
            bits_low = mode | ((bits<<4) & 0xF0) | lcd_backlight_status
            # High bits
            bus.write_byte(I2C_ADDR, bits_high)
            lcd_toggle_enable(bits_high)
            # Low bits
            bus.write_byte(I2C_ADDR, bits_low)
            lcd_toggle_enable(bits_low)
            set_hardware_status('lcd', True)
        except Exception:
            set_hardware_status('lcd', False)
            if bus is not None:
                try:
                    bus.close()
                except Exception:
                    pass
            bus = None
            raise


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
        self.command = shutil.which("gpio")
        self.available = bool(self.command)
        if not self.available:
            print("⚠️ Perintah gpio tidak ditemukan. Buzzer/tombol belum aktif; pasang GPIO tool yang sesuai model board.")

    def _run(self, *args):
        if not self.available:
            return None
        try:
            return subprocess.check_output([self.command] + list(args),
                                           stderr=subprocess.STDOUT, timeout=3).decode().strip()
        except (OSError, subprocess.SubprocessError) as error:
            set_hardware_status("gpio", False)
            print("[WARN] GPIO gagal; akan dicoba lagi:", error)
            return None

    def read(self, pin_number):
        result = self._run("read", str(pin_number))
        return int(result) if result in ("0", "1") else None

    def write(self, pin_number, value):
        return self._run("write", str(pin_number), str(value)) is not None

    def mode(self, pin_number, mode):
        return self._run("mode", str(pin_number), mode) is not None

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
        # Cek apakah interface tersedia di sistem
        available_interfaces = netifaces.interfaces()
        if interface_name not in available_interfaces:
            printDebug(f"Interface '{interface_name}' tidak ditemukan. Interface tersedia: {available_interfaces}")
            return None
        
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
    Retrieves the MAC address for a specified network interface.
    Returns None if the interface or address is not found.
    """
    try:
        # Cek apakah interface tersedia di sistem
        available_interfaces = netifaces.interfaces()
        if interface_name not in available_interfaces:
            printDebug(f"Interface '{interface_name}' tidak ditemukan. Interface tersedia: {available_interfaces}")
            return None
        
        # Get addresses for the specified interface
        addresses = netifaces.ifaddresses(interface_name)
        # Check if MAC addresses exist for this interface
        if netifaces.AF_LINK in addresses:
            # Return the first MAC address found
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

def get_base_url(url):
    """Extract base URL from full URL"""
    try:
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"
    except:
        return url

# def cek_internet(url='https://www.google.com/', timeout=5):
#     """
#     Cek konektivitas internet. 
#     Jika URL adalah endpoint API, akan cek base URL terlebih dahulu.
#     """
#     try:
#         # If URL looks like an API endpoint, extract base URL for connectivity test
#         if '/foundation/' in url or '/api/' in url or len(url.split('/')) > 3:
#             base_url = get_base_url(url)
#             test_url = base_url
#             # printDebug(f"API endpoint detected: {url}")
#             # printDebug(f"Testing base URL connectivity: {test_url}")
#         else:
#             test_url = url
#             # printDebug(f"Testing direct connectivity to: {test_url}")
            
#         response = requests.get(test_url, timeout=timeout)
#         # printDebug(f"Response status code: {response.status_code}")
        
#         # For base URL connectivity test, accept more status codes
#         if test_url != url:
#             # For base URL test, any response (even 404, 403) means server is reachable
#             # Only server errors (5xx) or connection errors indicate real connectivity issues
#             is_connected = response.status_code < 500
#             # printDebug(f"Base URL connectivity: {'ONLINE' if is_connected else 'OFFLINE'}")
            
#             # If base URL is reachable, also try the original endpoint with HEAD method
#             if is_connected:
#                 try:
#                     head_response = requests.head(url, timeout=timeout/2)
#                     # printDebug(f"HEAD request to {url}: {head_response.status_code}")
#                     # If HEAD returns 405 (Method Not Allowed), the endpoint exists but doesn't support HEAD
#                     if head_response.status_code in [200, 405]:
#                         printDebug("Endpoint appears to be valid")
#                 except:
#                     printDebug("HEAD request failed, but base URL is reachable")
            
#             return is_connected
#         else:
#             is_connected = response.status_code == 200
#             printDebug(f"Direct URL connectivity: {'ONLINE' if is_connected else 'OFFLINE'}")
#             return is_connected
            
#     except (requests.exceptions.ConnectionError, 
#             requests.exceptions.Timeout, 
#             requests.exceptions.DNSLookupError,
#             requests.exceptions.RequestException) as e:
#         printDebug(f"Network connectivity failed for {url}: {str(e)}")
        
#         # Fallback: try Google DNS to confirm internet connectivity
#         try:
#             fallback_response = requests.get('https://www.google.com', timeout=3)
#             if fallback_response.status_code == 200:
#                 printDebug("Internet connection OK (Google reachable), but target server unreachable")
#             return False
#         except:
#             printDebug("No internet connection detected")
#             return False
            
#     except Exception as e:
#         printDebugEx("ERROR cek_internet: ", e)
#         return False

import requests
import socket

def cek_internet(url=None, timeout=3):
    """Test outbound Internet access independently of the attendance API.

    url remains accepted for older callers; API HTTP status is not connectivity.
    """
    for host, port in (('1.1.1.1', 443), ('8.8.8.8', 53)):
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except OSError:
            continue
    return False


def internet_status_worker():
    global statusInternet
    while True:
        try:
            current = 'ONLINE' if cek_internet(timeout=3) else 'OFFLINE'
            if current != statusInternet:
                printDebug('[INTERNET]', current)
            statusInternet = current
        except Exception as error:
            statusInternet = 'OFFLINE'
            printDebugEx('[INTERNET] Pemeriksaan gagal: ', error)
        time.sleep(5)


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

def get_cpu_temperature():
    """Baca suhu CPU Orange Pi dalam Celsius; None jika sensor tidak tersedia."""
    try:
        with open('/sys/class/thermal/thermal_zone0/temp', 'r') as sensor:
            return round(int(sensor.read().strip()) / 1000.0, 2)
    except (OSError, ValueError):
        return None


# Fungsi ambil data sistem
threadStatus=[0,0,0,0]
def get_system_info():
    global threadStatus
    return {
        "app_version": LOCAL_VERSION,
        "machine_id": MACHINE_ID,
        "api_server": API_HOST,
        "mac_address": get_mac().replace(":", ""),  # Bisa juga tetap pakai ":"
        "ip_address_wlan": (wlan_ip if wlan_ip else "-"),
        "ip_address_eth": (eth_ip if eth_ip else "-"),
        "ip_address_vpn": (vpn_ip if vpn_ip else "-"),
        "cpu_percent": psutil.cpu_percent(interval=1),
        "cpu_temperature": get_cpu_temperature(),
        "memory_percent": psutil.virtual_memory().percent,
        "storage_percent": psutil.disk_usage('/').percent,
        "uptime": get_uptime(),
        "device": platform.node(),  # nama host/device
        "gpio_available": gpio_control.available,
        "rfid_available": reader is not None,
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
LOCAL_VERSION = "2.1.4"
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
RFID_RST = 13  # Orange Pi Zero wPi 13 = physical 22, reader RST.
# LED follows schematic connector position: physical pin 12 = wPi 6.
# This is PC11 on Zero 3; PA7 on this device's Orange Pi Zero/H2.
# PC11 (SoC pin name) must never be interpreted as wPi 11 (SPI MOSI).
_led_setting = os.environ.get('ABSENSI_LED_PIN', '6').strip()
LED = int(_led_setting) if _led_setting.isdigit() else None
if LED in (0, 1, 5, 7, 11, 12, 13, 14, 15):
    print('[WARN] LED dinonaktifkan: pin bentrok dengan I2C/SPI/buzzer/tombol.', flush=True)
    LED = None
button_pressed_time = 0  # buat catat kapan ditekan


buzzer_lock = threading.RLock()


def buzzer_beep(count=1, duration=0.15, delay=0.15):
    with buzzer_lock:
        try:
            for index in range(count):
                if not gpio_control.write(BUZZER, 1):
                    return False
                time.sleep(duration)
                if not gpio_control.write(BUZZER, 0):
                    return False
                if index < count - 1:
                    time.sleep(delay)
            return True
        finally:
            gpio_control.write(BUZZER, 0)


def restart_pm2_app():
    printDebug('[BUTTON] Tombol ditahan 5 detik; pm2 restart 0')
    gpio_control.write(BUZZER, 0)
    subprocess.run(['pm2', 'restart', '0'], check=True, timeout=20)


def button_worker():
    global last_scan_time, lcd_backlight_status, displayPage
    pressed_at = None
    last_beep_second = 0
    restart_requested = False
    while True:
        try:
            state = gpio_control.read(BUTTON)
            now = time.monotonic()
            if state == 1:
                last_scan_time = time.time()
                lcd_backlight_status = LCD_BACKLIGHT
                if pressed_at is None:
                    pressed_at = now
                seconds = int(now - pressed_at)
                if seconds > last_beep_second:
                    last_beep_second = seconds
                    buzzer_beep()
                if seconds >= 5 and not restart_requested:
                    restart_requested = True
                    restart_pm2_app()
            elif state == 0:
                if pressed_at is not None and not restart_requested:
                    displayPage = (displayPage + 1) % (displayMaxPage + 1)
                pressed_at = None
                last_beep_second = 0
                restart_requested = False
            else:
                pressed_at = None
                last_beep_second = 0
        except Exception as error:
            printDebugEx('[BUTTON] Pemantauan gagal: ', error)
        time.sleep(0.05)


def publish_hardware_snapshot():
    """Publish status only; no attendance identifiers are included."""
    path = os.environ.get('ABSENSI_HARDWARE_FILE', '/run/absensi-hardware.json')
    with hardware_lock:
        states = dict(hardware_status)
    gpio_ready = states.get('gpio', False)
    def entry(ready, good, bad):
        return {'ready': bool(ready), 'message': good if ready else bad}
    payload = {'reported_at': time.time(), 'pid': os.getpid(), 'devices': {
        'led': {'ready': gpio_ready if LED is not None else None,
                'message': ('GPIO siap; interval %g detik' % hardware_blink_interval()) if LED is not None and gpio_ready else ('GPIO belum siap' if LED is not None else 'Nonaktif; pin LED belum dipilih')},
        'buzzer': entry(gpio_ready, 'GPIO buzzer siap', 'GPIO buzzer bermasalah'),
        'rfid': entry(states.get('rfid'), 'Driver siap / menunggu kartu', 'Reader belum siap; mencoba koneksi ulang'),
        'rtc': entry(states.get('rtc'), 'RTC terbaca dan waktu valid', 'RTC tidak terbaca / waktu tidak valid'),
        'lcd': entry(states.get('lcd'), 'Penulisan LCD berhasil', 'LCD tidak terbaca; mencoba ulang'),
    }}
    directory = os.path.dirname(path)
    fd, temporary = tempfile.mkstemp(prefix='.absensi-hardware-', dir=directory)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(payload, stream)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def hardware_status_worker():
    led_on = False
    last_toggle = time.monotonic()
    next_check = 0.0
    next_report = 0.0
    while True:
        try:
            now = time.monotonic()
            if now >= next_check:
                read_rtc_time()
                # GPIO can recover after a transient subprocess failure.
                ready = True
                if LED is not None:
                    ready = gpio_control.mode(LED, 'out')
                ready = gpio_control.mode(BUZZER, 'out') and ready
                ready = gpio_control.mode(BUTTON, 'in') and ready
                set_hardware_status('gpio', ready)
                next_check = time.monotonic() + 5.0
            if LED is not None and time.monotonic() - last_toggle >= hardware_blink_interval():
                led_on = not led_on
                if not gpio_control.write(LED, int(led_on)):
                    set_hardware_status('gpio', False)
                last_toggle = time.monotonic()
            if time.monotonic() >= next_report:
                publish_hardware_snapshot()
                next_report = time.monotonic() + 2.0
        except Exception as error:
            printDebugEx('[HEALTH] Pemeriksaan hardware gagal: ', error)
        time.sleep(0.02)


def on_connect(client, userdata, flags, rc, properties=None):
    if rc != 0:
        printDebug("MQTT connection rejected:", rc)
        return
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
    
def on_disconnect(client, userdata, *args):
    # Paho's network loop handles reconnection; never block its callback thread.
    printDebug("MQTT terputus; network loop akan mencoba menghubungkan kembali.")

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


clientMQTT = None

def create_mqtt_client():
    options = {"client_id": "absensi-client-" + get_mac().replace(":", "")}
    if hasattr(mqtt, 'CallbackAPIVersion'):
        options['callback_api_version'] = mqtt.CallbackAPIVersion.VERSION2
    client = mqtt.Client(**options)
    client.username_pw_set(username="penta", password="penta123")
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    client.reconnect_delay_set(min_delay=1, max_delay=30)
    client.connect_async(broker, port)
    return client

def publish_mqtt(topic, payload):
    # Attendance is saved separately in MySQL even when MQTT is unavailable.
    if clientMQTT is None:
        return False
    try:
        result = clientMQTT.publish(topic, payload)
        return result.rc == mqtt.MQTT_ERR_SUCCESS
    except Exception as error:
        printDebug("MQTT publish gagal:", error)
        return False

# Initialize shared state before any optional hardware operation can fail.
wlan_ip = eth_ip = vpn_ip = None
ssid = None
reader = None
tagRFID = ""
statusInsert = 0
eth_mac = get_mac().replace(":", "")
topicPublish = "scola/absensi/" + eth_mac
topicSubscribe = topicPublish + "/subs"
topicSubscribeAll = "scola/absensi/subscribe"

# Menjadwalkan fungsi setiap hari jam 23:30

try :
    # eth_mac = str(get_interface_mac('eth0'))
    eth_mac = get_mac().replace(":","")
    printDebug("VERSION     : " + LOCAL_VERSION)
    printDebug("API SERVER  : " + API_HOST)
    printDebug("BASE URL    : " + get_base_url(API_HOST))
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

gpio_control = GPIOControl()
try :
    gpio_control.mode(BUZZER, "out")
    gpio_control.write(BUZZER, 0)
    if LED is not None:
        gpio_control.mode(LED, "out")
        gpio_control.write(LED, 0)
    gpio_control.mode(BUTTON, "in")
    buzzer_beep(count=3)
    lcd_init()
    lcd_clear()
    
   
    

    if cek_internet(API_HOST,3):
        statusInternet = "ONLINE"
        lcd_string("CHECK UPDATE ....", LCD_LINE_1)
        lcd_string("LOADING ...", LCD_LINE_2)
        lcd_string(check_for_update() or "", LCD_LINE_3)
except Exception as e:
    printDebugEx("ERROR START 1: ", e)

def refresh_network_addresses():
    global wlan_ip, eth_ip, vpn_ip
    # Take a fresh snapshot, including link state, so removed IPs are cleared.
    wifi = ethernet = tailscale = None
    try:
        stats = psutil.net_if_stats()
        for name, addresses in psutil.net_if_addrs().items():
            if name in stats and not stats[name].isup:
                continue
            ipv4 = next((a.address for a in addresses
                         if a.family == socket.AF_INET), None)
            if not ipv4:
                continue
            if name.startswith('tailscale'):
                tailscale = ipv4
            elif name.startswith(('wlan', 'wl')) or name == 'Wi-Fi':
                wifi = wifi or ipv4
            elif name.startswith(('eth', 'en')) or name == 'Ethernet':
                ethernet = ethernet or ipv4
    except Exception:
        pass  # A failed snapshot displays '-' and retries next second.
    wlan_ip, eth_ip, vpn_ip = wifi, ethernet, tailscale

refresh_network_addresses()

def initialize_rfid():
    if SimpleMFRC522 is None:
        set_hardware_status('rfid', False)
        printDebug('[WARN] Driver MFRC522 belum tersedia; periksa error import saat startup')
        return None
    try:
        # Driver opens SPI but does not drive NRSTPD; reset and release it here.
        if not gpio_control.mode(RFID_RST, 'out'):
            raise RuntimeError('Tidak dapat mengatur pin reset RFID')
        if not gpio_control.write(RFID_RST, 0):
            raise RuntimeError('Reset RFID LOW gagal')
        time.sleep(0.1)
        if not gpio_control.write(RFID_RST, 1):
            raise RuntimeError('Reset RFID HIGH gagal')
        time.sleep(0.1)
        device = SimpleMFRC522()
        time.sleep(0.05)
        set_hardware_status('rfid', True)
        printDebug('[OK] MFRC522 siap; polling UID tanpa membaca blok kartu')
        return device
    except Exception as error:
        set_hardware_status('rfid', False)
        printDebugEx('[WARN] MFRC522 init gagal; mencoba lagi dalam 5 detik: ', error)
        if isinstance(error, FileNotFoundError):
            printDebug('[RFID] SPI tersedia:', sorted(glob.glob('/dev/spidev*')))
    return None


def close_rfid(device):
    # Close SPI without GPIO.cleanup(), preserving LED/buzzer/button setup.
    low_level = getattr(device, 'READER', None)
    spi = getattr(low_level, 'spi', None)
    if spi is not None:
        try:
            spi.close()
        except Exception:
            pass


def check_rfid_chip(device):
    """Check the SPI link, allowing board-specific chip versions such as 0x82."""
    low = device.READER
    version = low.Read_MFRC522(0x37)
    if version in (0x00, 0xFF):
        raise RuntimeError('Reader tidak merespons SPI (VersionReg=0x%02X)' % version)
    if low.Read_MFRC522(0x01) & 0x10:
        raise RuntimeError('Reader masih power-down; diperlukan reset RST')
    if low.Read_MFRC522(0x14) & 0x03 != 0x03:
        low.AntennaOn()
        time.sleep(0.01)
        if low.Read_MFRC522(0x14) & 0x03 != 0x03:
            raise RuntimeError('Antena reader mati dan gagal diaktifkan kembali')
        printDebug('[RFID] Antena sempat mati; sudah diaktifkan kembali')


def rearm_rfid(device):
    """Release authentication and reset the chip after every scan transaction."""
    low = device.READER
    low.MFRC522_StopCrypto1()
    low.MFRC522_Init()
    deadline = time.monotonic() + 0.5
    time.sleep(0.05)
    while low.Read_MFRC522(0x01) & 0x10 and time.monotonic() < deadline:
        time.sleep(0.02)
    check_rfid_chip(device)


def read_rfid_id(device):
    """Read UID only: no block reads, MIFARE keys, or infinite read() loop."""
    low = device.READER
    low.MFRC522_StopCrypto1()
    status, _ = low.MFRC522_Request(low.PICC_REQALL)
    if status != low.MI_OK:
        return None
    status, uid = low.MFRC522_Anticoll()
    if status != low.MI_OK:
        return None
    return device.uid_to_num(uid)


displayPage=0
displayMaxPage=1
jumlahDataNotSend=0

siswaNis = ""
siswaNama = ""

def display_once():
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
        next_network_refresh = 0.0
        
        while True:
            if time.monotonic() >= next_network_refresh:
                refresh_network_addresses()
                next_network_refresh = time.monotonic() + 1.0
            now = datetime.now()

            # Cek sleep backlight
            if time.time() - last_scan_time > 60:
                lcd_backlight_status = LCD_BACKLIGHT_OFF
            else:
                lcd_backlight_status = LCD_BACKLIGHT

            # print(threadStatus[1])
            if displayPage==0 :
                lcd_string(str(get_datetime()),LCD_LINE_1)
                message1 = " SILAHKAN TAP KARTU  "
                message2 = " "
                if QR_ENABLED:
                    message1 = " SILAHKAN  TAP/SCAN "
                    message2 = " KARTU RFID/QR CODE "
                if reader is None:
                    message1 = "  RFID BELUM SIAP  "
                    message2 = " PERIKSA SPI/DRIVER "
                    if QR_ENABLED and QR_DEVICE_PATH:
                        message1 = " SILAHKAN SCAN QR "
                        message2 = " RFID BELUM SIAP "
                if tick :
                    lcd_string(message1,LCD_LINE_2)
                    lcd_string(message2,LCD_LINE_3)
                else :
                    lcd_string("           ",LCD_LINE_2)
                    lcd_string("           ",LCD_LINE_3)

                lcd_string("I:"+statusInternet+" D:"+str(jumlahDataNotSend),LCD_LINE_4)
                

            if displayPage==1 :
                lcd_string("FW V." + LOCAL_VERSION + " " + MACHINE_ID, LCD_LINE_1)
                lcd_string("TS: " + (vpn_ip or "-"),LCD_LINE_2)  
                lcd_string("W : " + (wlan_ip or "-"),LCD_LINE_3)  
                lcd_string("E : " + (eth_ip or "-"),LCD_LINE_4)  
            
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
def display():
    while True:
        try:
            if lcd_init():
                display_once()
        except Exception as error:
            set_hardware_status('lcd', False)
            printDebugEx('[LCD] Display gagal; mencoba ulang: ', error)
        time.sleep(5)


statusSend=0
last_scan_time_rfid = {}
def rfid():
    global reader, tagRFID, statusInsert, lcd_backlight_status, last_scan_time
    next_check = 0.0
    last_reset = time.monotonic()
    held_uid = None
    absent_since = None
    while True:
        try:
            threadStatus[2] = get_datetime()
            if reader is None:
                reader = initialize_rfid()
                if reader is None:
                    set_hardware_status('rfid', False)
                    time.sleep(5)
                    continue
                check_rfid_chip(reader)
                next_check = time.monotonic() + 5
                last_reset = time.monotonic()
                held_uid = None
                absent_since = None
            now_monotonic = time.monotonic()
            if now_monotonic >= next_check:
                check_rfid_chip(reader)
                next_check = now_monotonic + 5
            if now_monotonic - last_reset >= 30:
                rearm_rfid(reader)
                last_reset = time.monotonic()
            card_id = read_rfid_id(reader)
            if card_id is None:
                now_monotonic = time.monotonic()
                if absent_since is None:
                    absent_since = now_monotonic
                elif now_monotonic - absent_since >= 0.3:
                    held_uid = None
                time.sleep(0.05)
                continue
            absent_since = None
            set_hardware_status('rfid', True)
            if isinstance(card_id, bool) or not isinstance(card_id, int):
                raise ValueError('ID RFID tidak valid')
            current_tag = card_id.to_bytes(8, 'big')[3:7].hex()
            if current_tag == held_uid:
                time.sleep(0.1)
                continue
            held_uid = current_tag
        except Exception as error:
            set_hardware_status('rfid', False)
            printDebugEx('[RFID] Baca/status SPI gagal; reopen dan reset RST: ', error)
            close_rfid(reader)
            reader = None
            held_uid = None
            time.sleep(5)
            continue

        try:
            now = datetime.now()
            previous = last_scan_time_rfid.get(current_tag)
            if previous and now - previous < timedelta(minutes=1):
                tagRFID = 'xxx'
                printDebug('[RFID] Kartu sama ditolak: jeda absen belum 1 menit')
                buzzer_beep(count=1, duration=0.5)
                continue
            printDebug('[RFID] UID terbaca; menyimpan absen')
            inserted = insertdata(current_tag)
            if inserted is None:
                printDebug('[RFID] Absen gagal disimpan')
                buzzer_beep(count=1, duration=0.5)
                continue
            statusInsert = inserted
            tagRFID = current_tag
            last_scan_time_rfid[current_tag] = now
            last_scan_time = time.time()
            lcd_backlight_status = LCD_BACKLIGHT
            buzzer_beep(count=2)
            publish_mqtt(topicPublish + '/tag', current_tag)
            printDebug('[RFID] Absen tersimpan')
        except Exception as error:
            printDebugEx('[RFID] Pemrosesan absen gagal: ', error)
        finally:
            try:
                rearm_rfid(reader)
                last_reset = time.monotonic()
            except Exception as error:
                set_hardware_status('rfid', False)
                printDebugEx('[RFID] Reset setelah scan gagal; reopen SPI: ', error)
                close_rfid(reader)
                reader = None
        time.sleep(0.1)


def send():
    try:
        global tagRFID,MACHINE_ID,API_HOST,statusInternet,jumlahDataNotSend,threadStatus,statusSend,siswaNis,siswaNama
        while True:
            threadStatus[3]=get_datetime()
            
            # Ensure MySQL connection before executing queries
            if not ensure_mysql_connection():
                printDebug("MySQL connection failed in send thread")
                time.sleep(5)
                continue
                
            try:
                query = "SELECT COUNT(*) FROM data_absen where status=0"
                mycursor.execute(query)
                result = mycursor.fetchone()
                jumlahData = result[0] if result else 0
                jumlahDataNotSend = jumlahData
                
            except Exception as e:
                printDebugEx("ERROR counting unsent data: ", e)
                jumlahDataNotSend = 0

            if statusInternet == "ONLINE":
                #check data yang belum ke kirim di database
                try:
                    if not ensure_mysql_connection():
                        time.sleep(5)
                        continue
                        
                    mycursor.execute("SELECT * FROM data_absen WHERE status=0 ORDER BY id ASC LIMIT 1")
                    row = mycursor.fetchone()
                except Exception as e:
                    printDebugEx("ERROR fetching data for send: ", e)
                    row = None
    
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
                    printDebug(f"Sending POST request to: {API_HOST}")
                    printDebug(f"Payload: {payload}")
                    printDebug(f"Headers: {headers}")
                    
                    response = requests.request("POST", API_HOST, headers=headers, data=payload, timeout=10)
                    
                    printDebug(f"Response status code: {response.status_code}")
                    printDebug(f"Response headers: {dict(response.headers)}")
                    printDebug(f"Response text: {response.text}")
                    
                    if response.status_code == 404:
                        printDebug("❌ ERROR 404: API endpoint not found!")
                        printDebug("⚠️  Check if the API_HOST URL is correct in setting.json")

                    try:
                        if response.status_code == 404:
                            printDebug("❌ API endpoint returns 404 - endpoint tidak ditemukan")
                            # Handle 404 as API error, not network error
                            siswaNama = "ENDPOINT TIDAK DITEMUKAN"
                            statusSend = 2
                            
                            # Mark data as error instead of retrying
                            try:
                                if ensure_mysql_connection():
                                    query = "UPDATE data_absen SET status = 2, keterangan = %s WHERE id = %s"
                                    mycursor.execute(query, ("API endpoint not found (404)", id))
                                    mydb.commit()
                                    printDebug(f"Data ID {id} marked as API error (404)")
                            except Exception as e:
                                printDebugEx("ERROR updating data for 404: ", e)
                            continue  # Skip to next iteration
                            
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
                            try:
                                if ensure_mysql_connection():
                                    query = "DELETE FROM data_absen WHERE id = %s"
                                    mycursor.execute(query, (id,))
                                    mydb.commit()
                                    printDebug(f"Data dengan ID {id} berhasil dihapus.")
                            except Exception as e:
                                printDebugEx("ERROR deleting data: ", e)
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
                                try:
                                    if ensure_mysql_connection():
                                        query = "UPDATE data_absen SET status = 2,keterangan = %s WHERE id = %s"
                                        mycursor.execute(query, (message, id))
                                        mydb.commit()
                                except Exception as e:
                                    printDebugEx("ERROR updating data: ", e)
                                
                            

                    except ValueError:
                        printDebug("⚠️ Response bukan format JSON yang valid:")
                        printDebug(f"Status code: {response.status_code}")
                        printDebug(f"Response text: {response.text}")
                        
                        # Handle non-JSON responses
                        if response.status_code == 404:
                            siswaNama = "API ENDPOINT NOT FOUND"
                            statusSend = 2
                            try:
                                if ensure_mysql_connection():
                                    query = "UPDATE data_absen SET status = 2, keterangan = %s WHERE id = %s"
                                    mycursor.execute(query, (f"HTTP {response.status_code}: {response.text[:100]}", id))
                                    mydb.commit()
                            except:
                                pass
                        elif response.status_code >= 500:
                            printDebug("Server error (5xx) - will retry later")
                        else:
                            printDebug(f"Unexpected response code: {response.status_code}")
                #else:
                    #print("Data tidak ditemukan.")

                #jika sukses maka di delete
                
            printDebug("JUMLAH DATA NOT SEND : " + str(jumlahDataNotSend))
            printDebug("STATUS : " + str(statusInternet))
            
            time.sleep(5)
    except Exception as e:
        printDebugEx("ERROR SEND : ", e)

def heartBeat():
    while True:
        try:
            dataSystem = get_system_info()
            payload = json.dumps(dataSystem)
            publish_mqtt(topicPublish + "/heart", payload)
        except Exception as e:
            printDebugEx("ERROR HeartBeat : ", e)
        finally:
            time.sleep(30)

def mqttThread():
    global clientMQTT
    while True:
        try:
            if clientMQTT is None:
                clientMQTT = create_mqtt_client()
            clientMQTT.loop_forever(retry_first_connection=True)
        except Exception as e:
            printDebugEx("ERROR MQTT : ", e)
        time.sleep(5)


statusQRScanner=True
def qrScannerThread():
    try:
        global tagRFID,statusInsert, last_scan_time_qr, lcd_backlight_status, last_scan_time, statusQRScanner
        
        # Check if QR scanner is enabled
        if not QR_ENABLED or not QR_DEVICE_PATH:
            printDebug("QR Scanner disabled in configuration")
            statusQRScanner = False
            return
            
        # ganti dengan device QR reader kamu
        # dev = InputDevice('/dev/input/by-id/usb-YuRiot_ScanCode_Box_00000000011C-event-kbd')
        try:
            dev = InputDevice(QR_DEVICE_PATH)
            printDebug(f"QR Scanner initialized: {QR_DEVICE_PATH}")
        except Exception as e:
            printDebugEx(f"Failed to initialize QR device {QR_DEVICE_PATH}: ", e)
            statusQRScanner = False
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
                                buzzer_beep(count=1, duration=0.5)
                                buffer = ''
                                continue  # skip ke loop berikutnya

                        statusInsert = insertdata(qr_data)
                        if statusInsert is None:
                            tagRFID = ''
                            buffer = ''
                            buzzer_beep(count=1, duration=0.5)
                            continue
                        last_scan_time_qr[qr_data] = now
                        last_scan_time = time.time()
                        lcd_backlight_status = LCD_BACKLIGHT
                        buzzer_beep(count=2)
                        publish_mqtt(topicPublish + "/tag", qr_data)
                        buffer = ''
                    elif key.startswith('KEY_'):
                        # ambil karakter terakhir dari keycode, simple mapping
                        char = key.replace('KEY_', '')
                        if len(char) == 1:
                            buffer += char.lower()  # sesuaikan jika huruf besar/kecil

    except KeyboardInterrupt:
        printDebug("🛑 QR scanner berhenti")
    except Exception as e:
        printDebugEx("ERROR QR Scanner: ", e)

# APScheduler 3.x on Python 3.6 needs a real pytz zone, not a tzlocal shim.
from pytz import timezone as pytz_timezone
from tzlocal import get_localzone
scheduler_timezone = pytz_timezone(str(get_localzone()))
scheduler = BackgroundScheduler(timezone=scheduler_timezone)
scheduler.add_job(restart_computer, 'cron', hour=23, minute=30)
scheduler.start()

if __name__ == '__main__':
  # Create requirements.txt file if it doesn't exist
  if not os.path.exists("requirements.txt"):
      create_requirements_file()
  
  try:
    # main()
    print("🚀 Starting Absensi Application...")
    print("📦 Aplikasi mulai; periksa log/status untuk ketersediaan RFID, GPIO, dan MQTT.")
    
    threading.Thread(target=hardware_status_worker, name='hardware-status', daemon=True).start()
    threading.Thread(target=button_worker, name='button', daemon=True).start()

    t1 = threading.Thread(target=display, args=())
    t2 = threading.Thread(target=rfid, args=())
    t3 = threading.Thread(target=send, args=())
    t4 = threading.Thread(target=mqttThread, args=())
    t5 = threading.Thread(target=heartBeat, args=())
    t6 = threading.Thread(target=qrScannerThread, args=())

    threading.Thread(target=internet_status_worker, name="internet-status", daemon=True).start()
    threading.Thread(target=time_sync_worker, name="ntp-sync", daemon=True).start()

    t1.start()
    t2.start()
    t3.start()
    t4.start()
    t5.start()

    # Only start QR scanner thread if enabled in configuration
    try:
        if QR_ENABLED and QR_DEVICE_PATH:
            printDebug(f"Starting QR Scanner thread with device: {QR_DEVICE_PATH}")
            t6.start()
        else:
            printDebug("QR Scanner disabled - qrScannerThread will not start")
            statusQRScanner = False
    except NameError:
        printDebug("QR configuration not found - qrScannerThread will not start")
        statusQRScanner = False
    
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
            if 'QR_ENABLED' in globals() and 'QR_DEVICE_PATH' in globals():
                if QR_ENABLED and QR_DEVICE_PATH and 't6' in locals() and not t6.is_alive():
                    printDebug("QR Scanner Thread Mati")
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
    print("   pip3 install mfrc522 smbus2")
    sys.exit(1)
  except Exception as e:
    printDebugEx("ERROR MAIN: ", e)
