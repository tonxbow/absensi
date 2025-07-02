import smbus
import time
from datetime import datetime

# I2C address of the DS1307
DS1307_ADDRESS = 0x68

# Registers for time and date
SECONDS_REG = 0x00
MINUTES_REG = 0x01
HOURS_REG = 0x02
DAY_REG = 0x04
MONTH_REG = 0x05
YEAR_REG = 0x06

def bcd_to_decimal(bcd):
    """Convert Binary Coded Decimal to Decimal."""
    return ((bcd >> 4) * 10) + (bcd & 0x0F)

def decimal_to_bcd(decimal):
    """Convert decimal to BCD."""
    return ((decimal // 10) << 4) | (decimal % 10)

def set_rtc_from_system():
    try:
        now = datetime.now()  # Ambil waktu sistem (sudah sinkron ke NTP kalau ntp aktif)
        bus = smbus.SMBus(3)

        # Tulis waktu ke DS1307
        bus.write_byte_data(DS1307_ADDRESS, SECONDS_REG, decimal_to_bcd(now.second))
        bus.write_byte_data(DS1307_ADDRESS, MINUTES_REG, decimal_to_bcd(now.minute))
        bus.write_byte_data(DS1307_ADDRESS, HOURS_REG, decimal_to_bcd(now.hour))
        bus.write_byte_data(DS1307_ADDRESS, DAY_REG, decimal_to_bcd(now.day))
        bus.write_byte_data(DS1307_ADDRESS, MONTH_REG, decimal_to_bcd(now.month))
        bus.write_byte_data(DS1307_ADDRESS, YEAR_REG, decimal_to_bcd(now.year % 100))  # Ambil dua digit terakhir

        bus.close()
        print("RTC successfully updated from system time.")
    
    except Exception as e:
        print(f"Error setting RTC: {e}")

def read_rtc():
    """Reads the time and date from the DS1307."""
    try:
        bus = smbus.SMBus(3)  # Use I2C bus 1

        # Read the time and date registers
        seconds = bcd_to_decimal(bus.read_byte_data(DS1307_ADDRESS, SECONDS_REG))
        minutes = bcd_to_decimal(bus.read_byte_data(DS1307_ADDRESS, MINUTES_REG))
        hours = bcd_to_decimal(bus.read_byte_data(DS1307_ADDRESS, HOURS_REG))
        day = bcd_to_decimal(bus.read_byte_data(DS1307_ADDRESS, DAY_REG))
        month = bcd_to_decimal(bus.read_byte_data(DS1307_ADDRESS, MONTH_REG))
        year = bcd_to_decimal(bus.read_byte_data(DS1307_ADDRESS, YEAR_REG))
        
        bus.close() # Close the I2C bus
        
        return seconds, minutes, hours, day, month, year

    except Exception as e:
        print(f"Error reading from RTC: {e}")
        return None

if __name__ == "__main__":
    # set_rtc_from_system()
    rtc_data = read_rtc()

    if rtc_data:
        seconds, minutes, hours, day, month, year = rtc_data
        print(f"Current time: {hours:02d}:{minutes:02d}:{seconds:02d}")
        print(f"Current date: 20{year:02d}-{month:02d}-{day:02d}")
