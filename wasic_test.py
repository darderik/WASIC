import test
from connections import Connections
from addons.instruments import TDS2012C, RelayMatrix, TBS1052C
from addons.tasks import Tasks
import logging
from config import Config
import os
import serial
from instruments import SCPI_Info

from connections.utilities import detect_baud_rate
import gc
import time
import random


def rm_test():
    # Open serial port com4
    rm = RelayMatrix(SCPI_Info("COM9", baud_rate=115200, idn="RM", name="Relay Matrix", alias="RMRM"))
    rm.connect()
    root_logger = logging.getLogger()
    # Defensive: ensure log level is always valid
    log_level = Config().get("log_level", "INFO") or "INFO"
    root_logger.setLevel(log_level)
    # Add debug logger for VISA communication
    visa_logger = logging.getLogger('pyvisa')
    visa_logger.setLevel(logging.DEBUG)
    # Create stream handler for VISA debug output
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.DEBUG)
    visa_logger.addHandler(stream_handler)
    #a-d, 1-4
    relay_comb = [
        # Movement 1 - Quick alternating pattern
        ["a1", "b1", "c1", "d1"],
        ["a2", "b2", "c2", "d2"],
        ["a3", "b3", "c3", "d3"],
        ["a4", "b4", "c4", "d4"],
        
        # Movement 2 - Diagonal pattern
        ["a1", "b2", "c3", "d4"],
        ["a4", "b3", "c2", "d1"],
        
        # Movement 3 - Wave pattern
        ["a1", "b2", "c2", "d1"],
        ["a2", "b3", "c3", "d2"],
        ["a3", "b4", "c4", "d3"],
        
        # Final movement - Grand finale
        ["a1", "b1", "c1", "d1"],
        ["a1", "b2", "c3", "d4"],
        ["a4", "b4", "c4", "d4"]
    ]
    query_count = 0
    start_time = time.time()
    last_report_time = start_time
    last_query_count = 0

    indicator = "|/-\\"
    idx = 0
    # Assume a terminal width for padding to ensure full overwrite
    terminal_width = 120  # Adjust if your terminal is different
    previous_log = ""  # Track the previous log to print only when it changes
    commands = ["SWITCH:COMMUTE:BYTE:STATUS?","*OPC?","*IDN?","SWITCH:COMMUTE:STATUS?"]
    while True:
        for cmd in commands:
            if "?" in cmd:
                response = rm.query(cmd)
                query_count += 1
            else:
                rm.write(cmd)
            idx = (idx + 1) % len(indicator)

def nv34420_test():
    from addons.instruments import NV34420
    nv = NV34420(SCPI_Info("COM15", baud_rate=9600, idn="NV34420", name="NV34420A", alias="NV34420A"))
    root_logger = logging.getLogger()
    # Defensive: ensure log level is always valid
    log_level = Config().get("log_level", "INFO") or "INFO"
    root_logger.setLevel(log_level)
    # Add debug logger for VISA communication
    visa_logger = logging.getLogger('pyvisa')
    visa_logger.setLevel(logging.DEBUG)
    # Create stream handler for VISA debug output
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.DEBUG)
    visa_logger.addHandler(stream_handler)
    voltages = []
    # Set faster integration time (0.02 NPLC = 400μs at 50Hz)
    nv.integration_time = 0.02
    # Configure voltage measurement once with fixed range
    nv.configure_voltage(-1, 1)  # Configure once before the loop
    nv.write(":CONF:VOLT")  # One-time configuration
    
    print("Starting measurements with optimized settings...")
    for _ in range(100):
        start_time = time.time_ns()
        volt = nv.read_meas()  # Direct measurement without reconfiguring
        end_time = time.time_ns()
        elapsed_time_ms = (end_time - start_time) / 1_000_000  # Convert ns to ms
        voltages.append(volt)
        print(f"Measured Voltage: {volt} V, Time Elapsed: {elapsed_time_ms:.2f} ms")
    avg_volt = sum(voltages) / len(voltages)
    print(f"Average Voltage over 100 measurements: {avg_volt} V")

if __name__ == "__main__":
    nv34420_test()