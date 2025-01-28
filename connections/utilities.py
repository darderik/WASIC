# MIT License
#
# Copyright (c) 2023 Fikret Garipay
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import time
import string
import serial

DEFAULT_TIMEOUT = 3  # seconds
BAUDRATES = (
    110,
    300,
    600,
    1200,
    2400,
    4800,
    9600,
    14400,
    19200,
    115200,
    128000,
    230400,
    256000,
    460800,
    576000,
    921600,
)


def detect_baud_rate(
    port,
    data=None,
    timeout: float = DEFAULT_TIMEOUT,
    scan_all=False,
    print_response=False,
    print_all=False,
):
    baudrates = BAUDRATES if scan_all else (9600, 19200, 38400, 57600, 115200, 14400)
    data = (
        data
        if isinstance(data, bytes)
        else data.encode() if data is not None else b"*IDN?\n"
    )
    detected_baud_rate = None
    for baudrate in baudrates:
        with serial.Serial(port, timeout=timeout) as ser:
            ser.baudrate = baudrate
            ser.write(b"\n\n")  # Flush
            ser.read(ser.in_waiting)
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
            ser.close()
    return detected_baud_rate


def validate_response(response: bytes) -> bool:
    try:
        response_str = response.decode()
        return any(c in string.printable for c in response_str)
    except UnicodeDecodeError:
        return False
