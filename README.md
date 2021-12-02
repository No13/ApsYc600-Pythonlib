# Intro
This is my attempt at creating a Python library for interfacing with my APSystems YC600 inverter.
My work is based on the cc2531/cc2530 firmware created by Kadzsol (https://github.com/Koenkk/zigbee2mqtt/files/6797510/discord-11-7-2021.zip / https://github.com/Koenkk/zigbee2mqtt/issues/4221) and the ESP12 firmware created by patience4711 (https://github.com/patience4711/read-APS-inverters-YC600-QS1)

# About the cc253x firmware
As stated above, the cc253x firmware is created by Kadzsol. 
Flashing the custom firmware is mandatory to be able to communicate with APS inverters.
After flashing your module it will not be zigbee compatible until you reflash with the original firmware.

The author states that: 
 - use of this firmware for any commercial purposes is *not* allowed
 - Use at your own risk

The reason I include the firmware is specifically to have a single bundle of all required files to be able to use this library 

# Preparing a cc2531/cc2530
Flash using: https://github.com/jmichault/flash_cc2531

Connect the CC2530 module to a Raspberry Pi:
```
RPI Pin   Name    CC2530 Pin   Name
  39       GND        15        GND
  38     GPIO20        5       P2_1 (DD)
  36     GPIO16        4       P2_2 (DC)
  35     GPIO19       17      Reset
```
Check if chip is recognised:
```
./cc_chipid
```
Backup current firmware:
```
./cc_read backup.hex
```
Write custom firmware for APS connectivity:
```
./cc_write CC2530ZNP-cc2591-with-SBL.hex
```
Flashing is done using DD and DC Pin. After flashing the TX and RX pins for communication with ESP32 and/or
Raspberry PI at the cc2530 module are:
```
CC2530 Pin    Name
    21        P0_2 (RX)
    22        P0_3 (TX)
```
Communication with the cc2530 module is done using serial communication at
115200 baud.
   
# Pairing an Inverter
Before an inverter is usable it needs to be paired. After the pairing process you will get the inverter ID.
This ID is needed to communicate with the inverter.
Using a 'clean' CC2530 module without pairing (when inverter ID is already known) does not seem to work.
When paired once, the inverter ID should suffice for further communication.

# Using a Raspberry PI
## Pairing
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
    # The serial is required for pairing, inverter ID is unknown (0000)
    INDEX = INVERTER.add_inverter('123456789012', '0000', 2)
    print("Inverter ID is", INVERTER.pair_inverter(INDEX))
    # The inverter ID needs to be stored for future communications

## Polling inverter
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
    # Inverter ID in this example is 9988
    INVERTER.add_inverter('123456789012', '9988', 2)
    print(INVERTER.start_coordinator())
    print(INVERTER.ping_radio())
    print(INVERTER.poll_inverter(0))


# Using an ESP32
## Pairing
    from aps_yc600 import ApsYc600
    from machine import UART
    from machine import Pin
    import time

    # RX = GPIO09 / SD2
    # TX = GPIO10 / SD3
    # Reset pin = GPIO13

    serial = UART(1,115200) # Default pins for UART 1 are 9 / 10

    reset_pin = Pin(13,Pin.OUT)
    reset_pin.off()
    reset_pin.on()
    time.sleep(1)

    inverter = ApsYc600(serial,serial)
    # The serial is required for pairing, inverter ID is unknown (0000)
    index = inverter.add_inverter('123456789012', '0000', 2)
    print(inverter.pair_inverter(index))
    # The inverter ID needs to be stored for future communications

## Polling inverter
    from aps_yc600 import ApsYc600
    from machine import UART
    from machine import Pin
    import time

    # RX = GPIO09 / SD2
    # TX = GPIO10 / SD3
    # Reset pin = GPIO13

    serial = UART(1,115200) # Default pins for UART 1 are 9 / 10

    reset_pin = Pin(13,Pin.OUT)
    reset_pin.off()
    reset_pin.on()
    time.sleep(1)

    inverter = ApsYc600(serial,serial)
    # Inverter ID in this example is 9988
    inverter.add_inverter('123456789012', '9988', 2)
    print(inverter.start_coordinator())
    print(inverter.ping_radio())
    print(inverter.poll_inverter(0))
