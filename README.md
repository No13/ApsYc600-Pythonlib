# Intro
This is my attempt at creating a Python library for interfacing with my APSystems YC600 inverter.
My work is based on the cc2531/cc2530 firmware created by Kadzsol (https://github.com/Koenkk/zigbee2mqtt/files/6797510/discord-11-7-2021.zip / https://github.com/Koenkk/zigbee2mqtt/issues/4221) and the ESP12 firmware created by patience4711 (https://github.com/patience4711/read-APS-inverters-YC600-QS1)

# About the cc253x firmware
As stated above, the cc253x firmware is created by Kadzsol. 
Flashing the custom firmware is mandatory to be able to communicate with APS inverters.
After flashing your module it will not be zigbee compatible until you reflash with the original firmware.

The author states that: 
 - use of this firmware for any commercial puposes is *not* allowed
 - Use at your own risk

The reason I include the firmware is specifically to have a single bundle of all required files to be able to use this library 

# Preparing a cc2531/cc2530
Flash using: https://github.com/jmichault/flash_cc2531
More information to follow...

# Using a Raspberry PI
    import time
    import serial
    import RPi.GPIO as GPIO
    from aps_yc600 import ApsYc600

    SER_PORT = serial.serial_for_url('/dev/ttyS0')
    SER_PORT.baudrate = 115200

    RESET_PIN = 22
    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(RESET_PIN, GPIO.OUT)

    def reset_modem():
        '''
        Reset modem by toggling reset pin
        '''
        GPIO.output(RESET_PIN, 0)
        time.sleep(1)
        GPIO.output(RESET_PIN, 1)

    reset_modem()
    time.sleep(1)
    INVERTER = ApsYc600(SER_PORT, SER_PORT)
    # The serial is required for pairing only, which is not implemented yet
    # The inverter ID is retrieved by pairing (used the firmware of Patience4711 for now)
    INVERTER.add_inverter('123456789012', '9988', 2)
    print(INVERTER.start_coordinator())
    print(INVERTER.ping_radio())
    print(INVERTER.poll_inverter(0))


# Using an ESP32
    from aps_yc600 import ApsYc600
    from machine import UART
    from machine import Pin
    import time

    # RX = GPIO09 / SD2
    # TX = GPIO10 / SD3
    # Reset pin = GPIO13

    serial = UART(1,115200)

    reset_pin = Pin(13,Pin.OUT)
    reset_pin.off()
    reset_pin.on()
    time.sleep(1)

    inverter = ApsYc600(serial,serial)
    # The serial is required for pairing only, which is not implemented yet
    # The inverter ID is retrieved by pairing (used the firmware of Patience4711 for now)
    inverter.add_inverter('123456789012', '9988', 2)
    print(inverter.start_coordinator())
    print(inverter.ping_radio())
    print(inverter.poll_inverter(0))
