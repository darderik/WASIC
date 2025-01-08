import re
import threading
import time
from typing import List, Optional
from serial import Serial
from serial.tools.list_ports import comports
from serial.tools.list_ports_common import ListPortInfo
from instruments import Instrument_Wrapper, SCPI_Info, custom_instr_handler
from .utilities import detect_baud_rate, validate_response
from config import Config, comm_mode


class Connections:
    """
    The Connections class manages a collection of instruments connected via serial ports. It provides methods to verify the
    connected instruments, find a specific instrument by name, and fetch all instruments based on a list of aliases(that are names or even serial numbers).
    Attributes:
        _lock (threading.Lock): A lock to ensure thread-safe operations on the Instruments list.
        Instruments (List[Instrument_Wrapper]): A list of wrapped SCPI instruments.
    Methods:
        verify_instruments():
            Verifies the connected instruments by sending an identification query and validating the response.
            Removes instruments that do not respond correctly.
        find_instrument(matchingName: str) -> Optional[SCPI_Info]:
            Finds an instrument connected to a serial port that matches the given name.
        fetch_all_instruments(cls, curAliasesList: List[str]) -> None:
            Fetches all instruments based on the provided list of aliases.
    """

    _lock = threading.Lock()
    InstrumentsList: List[Instrument_Wrapper] = []

    @staticmethod
    def verify_instruments() -> None:
        if Config.communication_mode == comm_mode.pyVisa:
            for instr in Connections.InstrumentsList:
                try:
                    instr.scpi_instrument.id()
                except RuntimeError:
                    Connections.InstrumentsList.remove(instr)
        elif Config.communication_mode == comm_mode.serial:
            for instr in Connections.InstrumentsList:
                try:
                    instr.com_obj.open()
                    instr.com_obj.write(b"*IDN?")
                    time.sleep(instr.timeout)
                    response: str = instr.com_obj.read(
                        instr.com_obj.in_waiting
                    ).decode()
                    instr.com_obj.close()
                    if not validate_response(response):
                        Connections.InstrumentsList.remove(instr)
                except:
                    Connections.InstrumentsList.remove(instr)

    @staticmethod
    def find_instrument(
        matchingName: str, curLockedPorts: List[str]
    ) -> Optional[SCPI_Info]:
        """
        Finds an instrument connected to a serial port that matches the given name.
        Args:
            matchingName (str): The name to match against the instrument's identification string.
        Returns:
            Optional[SCPI_Info]: An SCPI_Info object containing the port, baud rate, and identification string of the matching instrument,
                                 or None if no matching instrument is found.
        """
        toReturn: Optional[SCPI_Info] = None

        # Obtain all ports
        ports: List[ListPortInfo] = comports()
        instrTimeout: int = 2
        # Filter
        ports_device: List[str] = [
            port[0] for port in ports if port.device not in curLockedPorts
        ]

        # Find BR for each port
        for port in ports_device:
            detected_BR: int = baudRateDetector.detect_baud_rate(port=port, timeout=1)
            if detected_BR is not None:
                # Found suitable baud rate
                with Serial(port, detected_BR) as curSerial:
                    # Send IDN query
                    curSerial.read(curSerial.in_waiting)  # flush
                    curSerial.write(b"*IDN?")
                    time.sleep(instrTimeout)
                    curIdnOput: str = curSerial.read(curSerial.in_waiting).decode()
                    # Strip special characters and "CTS" substring
                    curIdnOput = re.sub(r"[^a-zA-Z0-9,-]+|CTS", "", curIdnOput)
                    curSerial.close()

                    # Check if the name matches
                    if matchingName in curIdnOput:
                        toReturn = SCPI_Info(
                            port=port,
                            baud_rate=detected_BR,
                            idn=curIdnOput,
                            alias=matchingName,
                        )
                        break
        return toReturn

    @classmethod
    def fetch_all_instruments(cls, curAliasesList: List[str]) -> None:
        """
        Fetches all instruments based on the provided list of aliases.

        This method iterates over the provided list of instrument aliases, finds the corresponding
        SCPI instrument information, creates SCPI_Instrument instances, and wraps them in
        Instrument_Wrapper instances. The wrapped instruments are then appended to the class's
        Instruments list.

        Args:
            curAliasesList (List[str]): A list of instrument aliases to fetch.
        """
        with Connections._lock:
            curLockedPorts: List[str] = [
                instr.scpi_instrument.port() for instr in Connections.InstrumentsList
            ]
            for instr in curAliasesList:
                SCPIInfo: Optional[SCPI_Info] = cls.find_instrument(
                    instr, curLockedPorts
                )
                if SCPIInfo is not None:
                    curInstrumentWrapper: Instrument_Wrapper = custom_instr_handler(
                        SCPIInfo
                    )
                    cls.InstrumentsList.append(curInstrumentWrapper)
