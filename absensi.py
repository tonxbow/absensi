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



############################### OTA FUNCTION #######################################
def get_online_version():
    try:
        response = requests.get(VERSION_FILE_URL)
        dataVersion = response.json()
        print (dataVersion)
        print (dataVersion['version'])
        return str(dataVersion['version'])
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
    print("VERSION ONLINE : " +online_version + " = " + LOCAL_VERSION)
    if online_version and online_version != LOCAL_VERSION:
        print(f"Versi baru tersedia: {online_version}")
        download_latest()
        restart_app()
    else:
        print("Aplikasi sudah versi terbaru.")


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
    waktu = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
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
#LCD_BACKLIGHT = 0x00  # Off

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
        time.sleep(E_DELAY)
    except :
        print ("ERROR LCD")


def lcd_clear():
    lcd_byte(0x01,LCD_CMD) # 000001 Clear display

def lcd_byte(bits, mode):
  bits_high = mode | (bits & 0xF0) | LCD_BACKLIGHT
  bits_low = mode | ((bits<<4) & 0xF0) | LCD_BACKLIGHT

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
    except ValueError:
        # Handle cases where the interface name is not found
        return None
    return None

def get_ssid_nmcli():
    try:
        output = subprocess.check_output("nmcli -t -f active,ssid dev wifi", shell=True, encoding="utf-8")
        for line in output.strip().split("\n"):
            if line.startswith("yes:"):
                return line.split(":")[1]
        return None
    except subprocess.CalledProcessError:
        return None

def cek_internet(url='https://www.google.com/', timeout=5):
    try:
        _ = requests.get(url, timeout=timeout)
        return True
    except requests.ConnectionError:
        return False



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
LOCAL_VERSION = dataOTA['version']
LOCAL_FILE = 'absensi.py'
MACHINE_ID = dataSetting['machine-id']
API_HOST = dataSetting['api-server']

BUZZER = 5
BUTTON = 7

scheduler = BackgroundScheduler()


# Menjadwalkan fungsi setiap hari jam 23:30


print("VERSION     : " + LOCAL_VERSION)
print("API SERVER  : " + API_HOST)
print("MACHINE ID  : " + MACHINE_ID)
print("OTA VERSION : " + VERSION_FILE_URL)
print("OTA APP     : " + MAIN_FILE_URL)
print("VER HARD    : " + "1.0.1")

tagRFID=""
statusInsert=0
statusInternet="OFFLINE"

try :
    scheduler.add_job(check_for_update, 'cron', hour=23, minute=30)
    scheduler.start()
    check_for_update()
    lcd_init()
    gpio_control = GPIOControl()
    reader = SimpleMFRC522()
    gpio_control.mode(BUZZER, "out") #pin 11 PC6
    gpio_control.mode(BUTTON, "in") #pin13 PC5

    ssid = get_ssid_nmcli()
    print("SSID:", ssid if ssid else "Tidak terhubung")

    wlan_ip = get_interface_ip('wlan0')  # Common on Linux/Raspberry Pi
    if not wlan_ip:
        wlan_ip = get_interface_ip('Wi-Fi') # Common on Windows

    # Get IP for Ethernet (common names: eth0, Ethernet)
    eth_ip = get_interface_ip('eth0')  # Common on Linux/Raspberry Pi
    if not eth_ip:
        eth_ip = get_interface_ip('Ethernet') # Common on Windows

except Exception as e:
    print("ERROR : ", e)

displayPage=0
displayMaxPage=3
jumlahDataNotSend=0

def display():
    try:
        global tagRFID,statusInternet,statusInsert,displayPage,displayMaxPage
        lcd_clear()
        lcd_string("    SCOLA ABSEN",LCD_LINE_2)
        lcd_string("  FIRMWARE V."+LOCAL_VERSION,LCD_LINE_3)
        time.sleep(2)
        lcd_clear()
        tick=True
        countTick=0
        while True:
            
            now = datetime.now()
            formatted_datetime_1 = now.strftime("%Y-%m-%d  %H:%M:%S")

            if displayPage==0 :
                lcd_string(formatted_datetime_1,LCD_LINE_1)
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

            if tagRFID != "" :
               lcd_clear()
               lcd_string("NO RFID :" + tagRFID,LCD_LINE_1)  
               lcd_string("   BERHASIL ABSEN",LCD_LINE_2) 
               lcd_string("ID " + str(statusInsert),LCD_LINE_3) 
               tagRFID=""
               time.sleep(2)
               lcd_clear()

            # if gpio_control.read(BUTTON)=='0' :
            #     displayPage = displayPage + 1
            #     print("PAGE " + displayPage)
            # #     if displayPage > displayMaxPage:
            # #         displayPage=0
            #     time.sleep(1)
            
    except Exception as e:
        print("ERROR : ", e)

def rfid():
    try:
        global tagRFID,statusInsert
        while True:
            print("Hold a tag near the reader")
            id, text = reader.read()
            tagRFID = str(id);
            print("ID: %s\nText: %s" % (id,text))
            statusInsert = insertdata(tagRFID)
            gpio_control.write(5, 1)
            sleep(1)
            gpio_control.write(5, 0)
            #tidak bisa tap lagi jika kartu belum di angkat atau dalam 1 jam 

    except Exception as e:
        print("ERROR : ", e) 

def send():
    try:
        global tagRFID,MACHINE_ID,API_HOST,statusInternet,jumlahDataNotSend
        while True:
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
        print("ERROR : ", e)

if __name__ == '__main__':
  try:
    # main()
    t1 = threading.Thread(target=display, args=())
    t2 = threading.Thread(target=rfid, args=())
    t3 = threading.Thread(target=send, args=())

    t1.start()
    t2.start()
    t3.start()
  except Exception as e:
    print("ERROR : ", e)

