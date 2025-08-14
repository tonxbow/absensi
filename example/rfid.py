from time import sleep
import sys, os
from mfrc522 import SimpleMFRC522
reader = SimpleMFRC522()

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


gpio_control = GPIOControl()

# Set pins as output
# physical pin 11 > 5 = red
# physical pin 13 > 7 = yellow
# physical pin 15 > 8 = green
# or change to yours
gpio_control.mode(5, "out")
gpio_control.mode(7, "out")
gpio_control.mode(8, "out")
# test led
pins = [5,7,8]
for pin in pins:
  gpio_control.write(pin, 1)
  sleep(0.5)
  gpio_control.write(pin, 0)

# Change this for your card ID
Good_card = 12345678901
            
# dont forget to do - source env/bin/activate

try:
    while True:
        print("Hold a tag near the reader")
        id, text = reader.read()
        print("ID: %s\nText: %s" % (id,text))
        if id == Good_card:
          print("Card OK!")
          gpio_control.write(8, 1)
          sleep(0.5)
          gpio_control.write(8, 0)
        else: 
          print("Card not recognised!")
          gpio_control.write(5, 1)
          sleep(0.5)
          gpio_control.write(5, 0)
        sleep(2)
except KeyboardInterrupt:
    print("Exit!")
    raise
