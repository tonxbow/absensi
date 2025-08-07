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


try:
    import smbus2 as smbus
except ImportError:
    import smbus

import time
import threading
from datetime import datetime
from time import sleep
import sys, os
from mfrc522 import SimpleMFRC522
import socket
import netifaces
import requests
import json
import subprocess

import mysql.connector
from apscheduler.schedulers.background import BackgroundScheduler

import paho.mqtt.client as mqtt
import psutil
import uuid
import platform
from datetime import datetime, timedelta
import traceback 

import cv2
from pyzbar.pyzbar import decode

broker = "pentarium.id"   # bisa juga pakai localhost atau IP broker sendiri
port = 1883



############################### RTC FUNCTION #######################################
def bcd_to_dec(bcd):
    return (bcd // 16) * 10 + (bcd % 16)

def read_rtc_time():
    try:
        with smbus.SMBus(3) as bus:
            data = bus.read_i2c_block_data(0x68, 0x00, 7)
            second = bcd_to_dec(data[0])
            minute = bcd_to_dec(data[1])
            hour = bcd_to_dec(data[2])
            day = bcd_to_dec(data[4])
            month = bcd_to_dec(data[5] & 0x1F)  # Mask century bit if present
            year = bcd_to_dec(data[6]) + 2000
            dt = datetime(year, month, day, hour, minute, second)
            return str(dt.strftime('%Y-%m-%d %H:%M:%S'))
    except Exception as e:
        print("ERROR read_rtc_time:", e)
        return None

def sync_time_with_rtc():
    if statusInternet == "ONLINE" : 
        dt = read_rtc_time()
        if dt:
            try:
                date_str = dt.strftime('%m%d%H%M%Y.%S')
                subprocess.run(['sudo', 'date', date_str])
                print("Waktu sistem disinkronisasi dengan RTC:", dt)
            except Exception as e:
                print("ERROR RTC sync_time_with_rtc:", e)

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
        print("ERROR get_online_version: ", e)


def download_latest(branch="master"):
    try:
        if get_online_version(branch):
            print("Remote has changes, pulling...")
            subprocess.run(["git", "pull"], check=True)
            restart_app()
        else:
            print("No remote changes.")
            return "TIDAK ADA UPDATE"
    except Exception as e:
        print("ERROR download_latest: ", e)



# def download_latest():
#     print("Mengunduh versi terbaru...")
#     response = requests.get(MAIN_FILE_URL)
#     with open(LOCAL_FILE, 'wb') as f:
#         f.write(response.content)

def restart_app():
    print("Menjalankan ulang aplikasi...")
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
        print("ERROR lcd_init : ", e)

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



############################### GPIO FUNCTION #######################################
class GPIOControl:
    def __init__(self):
        pass

    def read(self, pin_number):
        command = f"gpio read {pin_number}"
        result = os.system(command)

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
                print(f"Pin {pin_number} value: {value}")
            else:
                print(f"Invalid pin number: {pin_number}")



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
        print("ERROR get_interface_ip : ", e)
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
        print("ERROR get_interface_mac : ", e)
    return None

def get_ssid_nmcli():
    try:
        output = subprocess.check_output("nmcli -t -f active,ssid dev wifi", shell=True, encoding="utf-8")
        for line in output.strip().split("\n"):
            if line.startswith("yes:"):
                return line.split(":")[1]
        return None
    except Exception as e:
        print("ERROR get_ssid_nmcli: ", e)

def cek_internet(url='https://www.google.com/', timeout=5):
    try:
        _ = requests.get(url, timeout=timeout)
        return True
    except Exception as e:
        print("ERROR START 3: ", e)
    
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
LOCAL_VERSION = "1.1.3"
LOCAL_FILE = 'absensi.py'
MACHINE_ID = dataSetting['machine-id']
API_HOST = dataSetting['api-server']

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
    print("Menjalankan ulang aplikasi...")
    python = sys.executable
    os.execl(python, python, *sys.argv)

# Fungsi: Restart komputer (Linux)
def restart_computer():
    print("Merestart komputer...")
    subprocess.run(["sudo", "reboot"])

# Fungsi: Update aplikasi dari repo Git
def update_app():
    print("Melakukan update aplikasi...")
    check_for_update()

# Mapping perintah ke fungsi
command_map = {
    "reload": restart_app,
    "reboot": restart_computer,
    "update": update_app
}

def on_disconnect(client, userdata, rc):
    print("⚠️ Terputus dari broker (rc={}), mencoba reconnect...".format(rc))
    while True:
        try:
            clientMQTT.reconnect()
            print("🔁 Reconnected!")
            break
        except:
            print("⏳ Gagal reconnect, coba lagi 5 detik...")
            time.sleep(5)

def on_message(client, userdata, msg):
    try:
        cmd = msg.payload.decode().strip().lower()
        print(f"Perintah diterima: {cmd}")

        if cmd in command_map:
            command_map[cmd]()  # Jalankan fungsi sesuai perintah
        else:
            print("Perintah tidak dikenali.")
    except Exception as e:
        print("Error saat menjalankan perintah:", e)


try :
    # clientMQTT = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, "123")
    clientMQTT = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,client_id="test-client")
    clientMQTT.on_connect = on_connect
    clientMQTT.on_disconnect = on_disconnect
    clientMQTT.on_message = on_message
    clientMQTT.connect(broker, port)
except Exception as e:
    print("Error MQTT:", e)   


# Menjadwalkan fungsi setiap hari jam 23:30

try :
    # eth_mac = str(get_interface_mac('eth0'))
    eth_mac = get_mac().replace(":","")
    print("VERSION     : " + LOCAL_VERSION)
    print("API SERVER  : " + API_HOST)
    print("MACHINE ID  : " + MACHINE_ID)
    print("MACADDRESS  : " + eth_mac)
    print("OTA VERSION : " + VERSION_FILE_URL)
    print("OTA APP     : " + MAIN_FILE_URL)
    print("VER HARD    : " + "1.0.1")

    tagRFID=""
    statusInsert=0
    statusInternet="OFFLINE"

    topicPublish = "scola/absensi/"+eth_mac
    topicSubscribe = "scola/absensi/"+eth_mac+"/subs"
    topicSubscribeAll = "scola/absensi/subscribe"
except Exception as e:
    print("Error MQTT:", e)   

try :
    gpio_control = GPIOControl()
    gpio_control.mode(BUZZER, "out") #pin 11 PC6
    gpio_control.mode(BUTTON, "in") #pin13 PC5
    gpio_control.mode(BUTTON, "up") #pin13 PC5
    lcd_init()
    lcd_clear()
    lcd_string("CHECK UPDATE ....", LCD_LINE_1)
    lcd_string("LOADING ...", LCD_LINE_2)
    lcd_string(check_for_update(), LCD_LINE_3)
    sync_time_with_rtc()
    

    ssid = get_ssid_nmcli()
    print("SSID:", ssid if ssid else "Tidak terhubung")
except Exception as e:
    print("ERROR START 1: ", e)   
    
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
    print("ERROR START 2: ", e)   

try : 
    reader = SimpleMFRC522()
except Exception as e:
    print("ERROR START 3: ", e)

displayPage=0
displayMaxPage=3
jumlahDataNotSend=0



def display():
    try:
        global tagRFID,statusInternet,statusInsert,displayPage,displayMaxPage,threadStatus,last_scan_time,lcd_backlight_status,button_pressed_time
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
            # button_state = gpio_control.read(BUTTON)
            # if button_state == "0":  # ditekan
            #     print("tombol ditekan")
            #     if button_pressed_time == 0:
            #         button_pressed_time = time.time()
            #     else:
            #         held_time = time.time() - button_pressed_time
            #         if held_time >= 5:
            #             lcd_clear()
            #             lcd_string("TOMBOL DITEKAN", LCD_LINE_2)
            #             lcd_string("RESTARTING....", LCD_LINE_3)
            #             time.sleep(2)
            #             restart_computer()
            # else:
            #     if button_pressed_time != 0:
            #         held_time = time.time() - button_pressed_time
            #         if held_time < 5:
            #             # Tombol dilepas cepat ➜ ganti page
            #             displayPage += 1
            #             if displayPage > displayMaxPage:
            #                 displayPage = 0
            #         button_pressed_time = 0
            
            # print(threadStatus[1])
            if displayPage==0 :
                lcd_string(str(get_datetime()),LCD_LINE_1)
                if tick :
                    lcd_string(" SILAHKAN TAP KARTU  ",LCD_LINE_2)
                else :
                    lcd_string("           ",LCD_LINE_2)

                lcd_string("I:"+statusInternet+" D:"+str(jumlahDataNotSend),LCD_LINE_4)
                

            if displayPage==1 :
                lcd_string("S : " + str(ssid),LCD_LINE_1)  
                lcd_string("W : " + str(wlan_ip),LCD_LINE_2)  
                lcd_string("E : " + str(eth_ip),LCD_LINE_3)  
            
            time.sleep(0.5)
            tick = not tick
            countTick += 1

            if countTick>10 :
                lcd_clear()
                #displayPage +=1
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
               lcd_string("NO RFID :" + tagRFID,LCD_LINE_1)  
               lcd_string("   BERHASIL ABSEN",LCD_LINE_2) 
               lcd_string("ID " + str(statusInsert),LCD_LINE_3) 
               tagRFID=""
               time.sleep(2)
               lcd_clear()
            
               
            threadStatus[1]= get_datetime()
            # if gpio_control.read(BUTTON)=='0' :
            #     displayPage = displayPage + 1
            #     print("PAGE " + displayPage)
            # #     if displayPage > displayMaxPage:
            # #         displayPage=0
            #     time.sleep(1)
            
    except Exception as e:
        print("ERROR display : ", e)
        traceback.print_exc()

last_scan_time_rfid = {}
def rfid():
    try:
        global tagRFID,statusInsert,threadStatus,last_scan_time_rfid,lcd_backlight_status,last_scan_time
        while True:
            threadStatus[2]=get_datetime()
            print("Hold a tag near the reader")
            id, text = reader.read()
            uid_bytes = id.to_bytes(8, 'big')
            uid_4bytes = uid_bytes[3:7]
            tag_hex = ''.join(f'{b:02x}' for b in uid_4bytes)
            tagRFID = str(tag_hex)
            print("ID: %s\nText: %s" % (tagRFID))
    

            now = datetime.now()
            last_time = last_scan_time_rfid.get(tagRFID)
            print(last_scan_time_rfid)
            # Jika tag pernah di scan
            if last_time:
                elapsed = now - last_time
                if elapsed < timedelta(minutes=1):
                    print(f"Tag {tagRFID} baru di-scan {elapsed} lalu. Abaikan.")
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
        print("ERROR RFID : ", e) 

def send():
    try:
        global tagRFID,MACHINE_ID,API_HOST,statusInternet,jumlahDataNotSend,threadStatus
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
                    print(payload)
                    print(response.text)

                    try:
                        res_json = response.json()
                        status = res_json.get("status", False)
                        message = res_json.get("message", "")
                        jadwal = res_json.get("data", {}).get("jadwal", "")

                        if status:
                            print("✅ Status: Berhasil")
                            print("Pesan:", message)
                            print("Jadwal:", jadwal)
                            query = "DELETE FROM data_absen WHERE id = %s"
                            mycursor.execute(query, (id,))
                            mydb.commit()
                            print(f"Data dengan ID {id} berhasil dihapus.")
                        else:
                            print("❌ Status: Gagal")
                            print("Pesan:", message)
                            print("Jadwal:", jadwal)
                            message = message.replace("'", "").replace('"', "")
                            query = "UPDATE data_absen SET status = 2,keterangan = '"+message+"' WHERE id = %s"
                            mycursor.execute(query, (id,))
                            mydb.commit()

                    except ValueError:
                        print("⚠️ Response bukan format JSON yang valid:")
                        print(response.text)
                #else:
                    #print("Data tidak ditemukan.")

                #jika sukses maka di delete
                
            else :
                statusInternet = "OFFLINE"

            
            time.sleep(5)
    except Exception as e:
        print("ERROR SEND : ", e)

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
            print("ERROR HeartBeat : ", e)

def mqttThread():
    try:
        clientMQTT.loop_forever()  # listen terus
    except Exception as e:
        print("ERROR MQTT : ", e)

def camThread():
    global statusInsert, last_scan_time_qr, lcd_backlight_status, last_scan_time
    cap = cv2.VideoCapture(1)
    if not cap.isOpened():
        print("❌ Tidak bisa membuka kamera QR Code.")
        return

    print("📡 QR Code scanner aktif...")
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                sleep(0.5)
                continue

            decoded_objects = decode(frame)
            for obj in decoded_objects:
                qr_data = obj.data.decode("utf-8")
                now = datetime.now()

                last_time = last_scan_time_qr.get(qr_data)
                if last_time and now - last_time < timedelta(minutes=1):
                    continue

                print(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] QR Code: {qr_data}")
                statusInsert = insertdata(qr_data)
                last_scan_time_qr[qr_data] = now
                last_scan_time = time.time()
                lcd_backlight_status = LCD_BACKLIGHT
                gpio_control.write(5, 1)
                sleep(1)
                gpio_control.write(5, 0)
                clientMQTT.publish(topicPublish + "/tag", qr_data)

            sleep(0.1)

    except KeyboardInterrupt:
        print("🛑 QR scanner berhenti")
    finally:
        cap.release()

scheduler = BackgroundScheduler()
scheduler.add_job(restart_computer, 'cron', hour=23, minute=30)
scheduler.start()

if __name__ == '__main__':
  try:
    # main()
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
    t6.start()
    statusThread = True
    while True:
        if not t1.is_alive():
            statusThread=False
            print("display Mati")
        if not t2.is_alive():
            statusThread=False
            print("rfid Mati")
        if not t3.is_alive():
            # statusThread=False
            print("send Mati")
        if not t4.is_alive():
            # statusThread=False
            print("mqtt Mati")
        if not t5.is_alive():
            statusThread=False
            print("heartbeat Mati")
        if not t6.is_alive():
            statusThread=False
            print("CamThread Mati")
            #threads.remove(t)
            #start_thread(i)
        time.sleep(30)
        if statusThread==False :
            statusThread=True
            restart_app()
  except Exception as e:
    print("ERROR MAIN: ", e)

