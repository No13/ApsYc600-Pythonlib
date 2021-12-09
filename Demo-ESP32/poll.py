'''
Poll inverter from ESP32
'''
# Prevent errors from uPython modules
# pylint: disable=E0401
import time
import gc
import _thread
import network
from machine import UART
from machine import Pin
import ntptime
from aps_yc600 import ApsYc600
from influxdb import InfluxDBClient
from graphite import Graphite
from domoticz import Domoticz
from _creds import secrets
# RX = GPIO09 / SD2
# TX = GPIO10 / SD3
# Reset pin = GPIO13

# Enable WiFi
sta = network.WLAN(network.STA_IF)
sta.active(True)
time.sleep(0.5)
try:
    sta.connect(secrets['ssid'], secrets['psk'])
except:
    pass

# Enable serial UART for communication with cc2530
serial = UART(1, 115200)

# Reset cc2530 module
reset_pin = Pin(13, Pin.OUT)
reset_pin.off()
reset_pin.on()
time.sleep(1)

# Init inverter
inverter = ApsYc600(serial, serial)
inverter.add_inverter(secrets['inv_serial'], secrets['inv_id'], 2)
print("Coordinator starting", inverter.start_coordinator())

# Graphite logger
graphite_client = Graphite(secrets['graphite_host'], secrets['graphite_port'])

domo_client = Domoticz(
    secrets['domoticz_url'],
    secrets['domoticz_user'],
    secrets['domoticz_pass'])

influx_client = InfluxDBClient(
    secrets['influx_url'],
    secrets['influx_db'],
    secrets['influx_user'],
    secrets['influx_pass'])

# Send data to all destinations
def push_data(data):
    '''
    Send data out
    '''
    result = []
    # Influx output
    data_xlate = {
        'acv': data['voltage_ac'],
        'dcc0': data['current_dc1'],
        'dcc1': data['current_dc2'],
        'dcv0': data['voltage_dc1'],
        'dcv1': data['voltage_dc2'],
        'energy': round((data['energy_panel1'] + data['energy_panel2']) / 1000, 3),
        'freqac': data['freq_ac'],
        'pow_p0': data['watt_panel1'],
        'pow_p1': data['watt_panel2'],
        'power': round(data['watt_panel1'] + data['watt_panel2'], 2),
        'temp': data['temperature']}
    result.append(influx_client.write(secrets['influx_bucket'], data_xlate))
    gc.collect()

    # Domoticz output
    data_energy = str(round(data['watt_panel1'] + data['watt_panel2'], 2))
    data_energy += ';'
    data_energy += str(data['energy_panel1'] + data['energy_panel2'])
    data_xlate = {
        '217': data_energy,
        '218': data['voltage_dc1'],
        '219': data['voltage_dc2'],
        '220': data['watt_panel1'],
        '221': data['watt_panel2'],
        '222': data['temperature'],
        '223': data['voltage_ac']}
    result.append(domo_client.send_data(data_xlate))
    gc.collect()

    # Graphite output
    data_xlate = {
        'energy.data.aps.acv': data['voltage_ac'],
        'energy.data.aps.dcc0': data['current_dc1'],
        'energy.data.aps.dcc1': data['current_dc2'],
        'energy.data.aps.dcv0': data['voltage_dc1'],
        'energy.data.aps.dcv1': data['voltage_dc2'],
        'energy.data.kwh.aps': round((data['energy_panel1'] + data['energy_panel2']) / 1000, 3),
        'energy.data.aps.freq': data['freq_ac'],
        'energy.data.aps.pow0': data['watt_panel1'],
        'energy.data.aps.pow1': data['watt_panel2'],
        'energy.data.solar_aps': round(data['watt_panel1'] + data['watt_panel2'], 2),
        'energy.data.aps.temp': data['temperature']}
    result.append(graphite_client.send_data(data_xlate))
    gc.collect()

    return result

def reset_data():
    '''
    Send all zeros to reset stats for new day
    '''
    # check if time is correct!
    if time.time() < 692284226:
        raise Exception('Time not set!')

    push_data({
        'voltage_ac': 0,
        'freq_ac': 0,
        'temperature': 0,
        'current_dc1': 0,
        'current_dc2': 0,
        'voltage_dc1': 0,
        'voltage_dc2': 0,
        'energy_panel1': 0,
        'energy_panel2': 0,
        'watt_panel1': 0,
        'watt_panel2': 0})

def ntp_update():
    '''
    Do ntp update
    '''
    update = False
    while not update:
        try:
            print("Updating NTP")
            ntptime.settime()
            update = True
        except Exception as ntp_error:
            print('NTP not updated!', ntp_error)
            time.sleep(5)

def do_poll():
    '''
    Poll inverter and write to influx client
    '''
    current_day = -1
    last_ntp_update = time.time()
    while True:
        # Do we need to update via NTP?
        if last_ntp_update + 7200 < time.time() or time.time() < 692284226:
            print("NTP Update needed")
            ntp_update()
            last_ntp_update = time.time()
            # Was this the initial ntp update?
            if current_day == -1:
                # If so; set current_day without resetting counters
                current_day = time.gmtime()[2]

        try:
            if inverter.ping_radio():
                success = False
                tries = 5
                while not success and tries > 0:
                    result = inverter.poll_inverter(0)
                    if not 'error' in result:
                        success = True
                    tries = tries - 1
                if success:
                    if result['crc']:
                        print("Data written:", push_data(result['data']))
                else:
                    print("No reading", result)
            else:
                print('radio not healthy')
            # If day changed, reset counters
            if current_day != time.gmtime()[2] and current_day > 0:
                reset_data()
                current_day = time.gmtime()[2]
        except Exception as global_error:
            print("Oh noes", global_error)
        gc.collect()
        time.sleep(30)

# Start poll thread
_thread.start_new_thread(do_poll, ())
