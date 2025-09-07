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


def test_function():
    # Open serial port com4
    rm = RelayMatrix(SCPI_Info("COM4", baud_rate=115200, idn="RM", name="Relay Matrix", alias="RMRM"))
    rm.connect()
    root_logger = logging.getLogger()
    # Defensive: ensure log level is always valid
    log_level = Config().get("log_level", "INFO") or "INFO"
    root_logger.setLevel(log_level)
    # Add debug logger for VISA communication
    #visa_logger = logging.getLogger('pyvisa')
    #visa_logger.setLevel(logging.DEBUG)
    # Create stream handler for VISA debug output
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.DEBUG)
    #visa_logger.addHandler(stream_handler)
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

    while True:
        commands = [
            lambda: rm.opc(),
            lambda: rm.query("*IDN?"),
            lambda: rm.query("*OPC?"),
            lambda: rm.query("SYS:LOG?")
        ]

        # Randomly select and execute a command
        command = random.choice(commands)
        result = command()
        query_count += 1

        # If the last command was "SYS:LOG?", store the result in last_log
        if command == commands[3]:  # Corresponds to "SYS:LOG?"
            last_log = result

        # Removed separate log print; the log is now included in the overwriting status line below

        current_time = time.time()
        if current_time - last_report_time >= 1.0:
            queries_this_second = query_count - last_query_count
            status_msg = f"{indicator[idx % len(indicator)]} Queries/s: {queries_this_second} | Total queries: {query_count} | Last log: {last_log.strip() if last_log else 'N/A'}"
            # Clear the terminal and print the status
            os.system('cls')
            print(status_msg)
            idx += 1
            last_report_time = current_time
            last_query_count = query_count
        else:
            # Optionally clear if needed, but since we're not printing, maybe not
            pass

if __name__ == "__main__":
    test_function()