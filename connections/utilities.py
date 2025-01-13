# Script authored by erd0spy MIT License
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
    timeout=DEFAULT_TIMEOUT,
    scan_all=False,
    print_response=False,
    print_all=False,
):
    baudrates = BAUDRATES if scan_all else (9600, 19200, 38400, 57600, 115200, 14400)
    data = (
        data
        if isinstance(data, bytes)
        else data.encode() if data is not None else b"AT"
    )
    detected_baud_rate = None
    with serial.Serial(port, timeout=timeout) as ser:
        for baudrate in baudrates:
            ser.baudrate = baudrate
            if data is not None:
                ser.write(data)
                time.sleep(timeout / 1000)
            response = ser.read(ser.in_waiting)
            if validate_response(response):
                if print_response or print_all:
                    print(f"Response at {baudrate} baud rate: {response}")
                detected_baud_rate = baudrate
                if not print_all:
                    break
    return detected_baud_rate


def validate_response(response: bytes) -> bool:
    try:
        response_str = response.decode()
        return any(c in string.printable for c in response_str)
    except UnicodeDecodeError:
        return False
