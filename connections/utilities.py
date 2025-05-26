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
from time import sleep
from threading import Lock
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
    sbits=1,
) -> Tuple[int, str] | None:
    baudrates = BAUDRATES if scan_all else (9600, 19200, 38400, 57600, 115200, 14400)
    data = (
        data
        if isinstance(data, bytes)
        else data.encode() if data is not None else b"*IDN?\n"
    )
    detected_baud_rate = 0
    try:
        with serial.Serial(port, timeout=0.5, write_timeout=0.5) as ser:
            ser.timeout = timeout
            ser.stopbits = sbits
            for baudrate in baudrates:
                logger.debug(
                    f"Trying baudrate: {baudrate} on port {port} with sbits {sbits}"
                )
                ser.baudrate = baudrate
                ser.write(b"syst:rem\n")  # Explicitly switch in remote
                ser.write(b"\n\n\n\n")  # Flush
                sleep(10e-3)
                ser.read_all()
                ser.write(data)
                sleep(10e-3)
                response = ser.read_until(expected=b"\n")
                while ser.in_waiting != 0:
                    _ = ser.read(ser.in_waiting)

                if validate_response(response):
                    detected_baud_rate = baudrate
                    current_idn = response.decode().strip()
                    break
        ser.close()
        # Recursive call
        if detected_baud_rate != 0:
            return (detected_baud_rate, current_idn)
        elif sbits != 2:  # Wrong stop bits?
            return detect_baud_rate(port, timeout=timeout, sbits=2)
        else:
            return None
    except (serial.SerialException, serial.SerialTimeoutException) as e:
        logger.error(f"Serial exception on port {port}: {e}")
        return None


def validate_response(response: bytes) -> bool:
    try:
        response_str = response.decode()
        return any(c in string.printable for c in response_str)
    except UnicodeDecodeError:
        return False


def detect_baud_wrapper(
    port,
    target: List[Tuple[str, str, int]],
    target_lock: Lock,
) -> None:
    config = Config()
    BR_IDN: Optional[Tuple[int, str]] = detect_baud_rate(
        port=port, timeout=config.get("default_timeout", 0.5)
    )
    # PORT, IDN, BAUD
    if BR_IDN is not None:
        result_tuple: Tuple[str, str, int] = (port, BR_IDN[1], BR_IDN[0])
        logger.debug(
            f"BR Detection on port {result_tuple[0]} with Baud {result_tuple[2]} and IDN {result_tuple[1]}"
        )
        with target_lock:
            target.append(result_tuple)
    else:
        logger.debug(f"Failed to detect baud rate for port {port}")


def is_instrument_in_aliases(idn: str) -> Optional[str]:
    for alias in Config().get("instr_aliases"):
        if alias.lower() in idn.lower():
            return alias
    return None
