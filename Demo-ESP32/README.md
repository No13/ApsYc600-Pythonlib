# Demo
This folder is my current 'application' for retrieving inverter stats from
the YC600 and pushing the data to Domoticz, InfluxDB and Graphite.

The current micropython version which I'm running on my ESP32 is 1.15.

# Wiring
The wiring is briefly mentioned in poll.py:
```
RX  -> GPIO09
TX  -> GPIO10
RST -> GPIO13
```
# Setup
Copy the aps_yc600.py file to this folder and fill _creds.py with actual
values.

# Not too pretty
The Graphite metric path's are static, not too pretty I know...
This goes for the IDX values for Domoticz too...

These values should be adjusted to your own needs.

