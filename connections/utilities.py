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

import string
import serial
from typing import Tuple, List, Optional, Any
from config import Config
import logging

logger = logging.getLogger(__name__)
DEFAULT_TIMEOUT = 1  # seconds
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
    print_all=False,
) -> Tuple[int, str] | None:
    baudrates = BAUDRATES if scan_all else (9600, 19200, 38400, 57600, 115200, 14400)
    data = (
        data
        if isinstance(data, bytes)
        else data.encode() if data is not None else b"*IDN?\n"
    )

    detected_baud_rate: int = 0
    with serial.Serial(port) as ser:
        for baudrate in baudrates:
            logger.debug(f"Trying baudrate: {baudrate} on port {port}")
            ser.baudrate = baudrate
            ser.timeout = timeout
            ser.write(b"\n\n\n\n")  # Flush
            ser.read(ser.in_waiting)
            ser.write(data)
            response = ser.read_until(expected=b"\n")
            while ser.in_waiting != 0:
                _ = ser.read(ser.in_waiting)

            if validate_response(response):
                logger.debug(
                    f"Detected baudrate: {baudrate} on port {port} with response: {response}"
                )
                detected_baud_rate = baudrate
                current_idn = response.decode().strip()
                break
    ser.close()
    return (detected_baud_rate, current_idn) if detected_baud_rate != 0 else None


def validate_response(response: bytes) -> bool:
    try:
        response_str = response.decode()
        return any(c in string.printable for c in response_str)
    except UnicodeDecodeError:
        return False


def detect_baud_wrapper(
    port, data, timeout: float, target_list: List[Tuple[str, str, int]]
) -> None:
    config = Config()
    BR_IDN: Optional[Tuple[int, str]] = detect_baud_rate(
        port=port, timeout=config.get("default_timeout", 0.5), data=data
    )
    # PORT, IDN, BAUD
    if BR_IDN is not None:
        target_list.append((port, BR_IDN[1], BR_IDN[0]))
