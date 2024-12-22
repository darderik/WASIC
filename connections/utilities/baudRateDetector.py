
#!/usr/bin/env python3
# Script authored by erd0spy MIT License
import argparse
import serial
import time
import string

DEFAULT_TIMEOUT = 3  # seconds
BAUDRATES = (110, 300, 600, 1200, 2400, 4800, 9600, 14400, 19200, 38400, 57600, 115200, 128000, 230400, 256000, 460800, 576000, 921600)

def detect_baud_rate(port, data=None, timeout=DEFAULT_TIMEOUT, scan_all=False, print_response=False, print_all=False):
    baudrates = BAUDRATES if scan_all else (9600, 19200, 38400, 57600, 115200, 14400)
    detected_baud_rate = None
    for baudrate in baudrates:
        with serial.Serial(port, timeout=timeout) as ser:
            ser.baudrate = baudrate
            if data is not None:
                ser.write(data)
                time.sleep(timeout)
            response = ser.read(ser.in_waiting)
            if validate_response(response):
                if print_response or print_all:
                    print(f"Response at {baudrate} baud rate: {response}")
                detected_baud_rate = baudrate
                if not print_all:
                    break

def validate_response(response):
    try:
        response_str = response.decode()
        return any(c in string.printable for c in response_str)
    except UnicodeDecodeError:
        return False