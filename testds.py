import smbus
from datetime import datetime

# Fungsi konversi BCD ke decimal
def bcd_to_dec(bcd):
    return (bcd // 16) * 10 + (bcd % 16)

# Fungsi baca waktu dari DS1307
def read_rtc(bus_num=3, address=0x68):
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
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except Exception as e:
        return f"ERROR membaca RTC: {e}"

if __name__ == "__main__":
    waktu = read_rtc()
    print("Waktu DS1307:", waktu)
