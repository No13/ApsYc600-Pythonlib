'''
Pair APS inverter and retrieve Inverter ID
'''
import time
# pylint: disable=E0401
from machine import UART
from machine import Pin
from aps_yc600 import ApsYc600
from _creds import secrets

# RX = GPIO09 / SD2
# TX = GPIO10 / SD3
# Reset pin = GPIO13

serial = UART(1, 115200)

# Reset cc2530 module
reset_pin = Pin(13, Pin.OUT)
reset_pin.off()
reset_pin.on()
time.sleep(1)

# Start pairing
inverter = ApsYc600(serial, serial)
INV_INDEX = inverter.add_inverter(secrets['inv_serial'], '0000', 2)
inverter_id = inverter.pair_inverter(INV_INDEX)

# Echo information and store in object
print("Inverter ID found:", inverter_id)
inverter.set_inverter_id(INV_INDEX, inverter_id)
