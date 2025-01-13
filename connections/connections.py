import re
import threading
import time
from typing import List, Optional, Any
from serial import Serial
from serial.tools.list_ports import comports
from serial.tools.list_ports_common import ListPortInfo
from instruments import Instrument_Entry, SCPI_Info, custom_instr_handler
from easy_scpi import Instrument
from .utilities import detect_baud_rate, validate_response
from config import Config, comm_mode
import json
from dataclasses import asdict


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

    _instrument_lock = threading.Lock()
    _file_lock = threading.Lock()
    InstrumentsList: List[Instrument_Entry] = []

    @classmethod
    def get_instrument(cls, alias: str) -> Optional[Instrument_Entry]:
        """
        Returns an Instrument_Entry object with the given alias.
        Args:
            alias (str): The alias of the instrument to return.
        Returns:
            Optional[Instrument_Entry]: An Instrument_Entry object with the given alias, or None if no instrument with that alias is found.
        """
        toReturn: Optional[Instrument_Entry] = None
        with cls._instrument_lock:
            for instr in cls.InstrumentsList:
                if alias.lower() in instr.data.alias.lower():
                    toReturn = instr
        return toReturn

    @classmethod
    def get_instruments_aliases(cls) -> List[str]:
        """
        Returns a list of aliases of all instruments in the InstrumentsList.
        Returns:
            List[str]: A list of aliases of all instruments in the InstrumentsList.
        """
        with cls._instrument_lock:
            return [instr.data.alias for instr in cls.InstrumentsList]

    @classmethod
    def is_scpi_info_busy(cls, instr_info: SCPI_Info):
        """
        Returns True if the SCPI info is busy, False otherwise.
        """
        info_com_port = instr_info.port
        if info_com_port in [
            instr.scpi_instrument.port for instr in cls.InstrumentsList
        ]:
            return True
        return False

    @classmethod
    def verify_instruments(cls) -> None:
        with cls._instrument_lock:
            if Config.communication_mode == comm_mode.pyVisa:
                for instr in Connections.InstrumentsList:
                    try:
                        instr.scpi_instrument.id
                    except Exception as e:
                        Connections.InstrumentsList.remove(instr)
                        instr.scpi_instrument.disconnect()  # needed for freeing up com port lock
            elif Config.communication_mode == comm_mode.serial:
                for instr in Connections.InstrumentsList:
                    try:
                        instr.com_obj.open()
                        instr.com_obj.write(b"*IDN?")
                        time.sleep(instr.data.timeout / 1000)
                        response: str = instr.com_obj.read(
                            instr.com_obj.in_waiting
                        ).decode()
                        instr.com_obj.close()
                        if not validate_response(response.encode()):
                            Connections.InstrumentsList.remove(instr)
                    except:
                        Connections.InstrumentsList.remove(instr)

    @classmethod
    def find_instrument(
        cls, matchingName: str, curLockedPorts: List[str]
    ) -> Optional[SCPI_Info]:
        """
        Finds an instrument connected to a serial port that matches the given name.
        Args:
            matchingName (str): The name to match against the instrument's identification string.
        Returns:
            Optional[SCPI_Info]: An SCPI_Info object containing the port, baud rate, and identification string of the matching instrument,
                                 or None if no matching instrument is found.
        """
        with cls._instrument_lock:
            toReturn: Optional[SCPI_Info] = None

            # Obtain all ports
            ports: List[ListPortInfo] = comports()
            instrTimeout: int = 2
            # Filter
            ports_device: List[str] = [
                port[0] for port in ports if port.device not in curLockedPorts
            ]

            idn_string: str = ""
            # Find BR for each port
            for port in ports_device:
                detected_BR: int = detect_baud_rate(port=port, timeout=instrTimeout)
                if detected_BR is not None:
                    with Serial(port, detected_BR) as curSerial:
                        # Send IDN query
                        curSerial.read(curSerial.in_waiting)  # flush
                        curSerial.write(b"*IDN?")
                        time.sleep(instrTimeout)
                        idn_string = curSerial.read(curSerial.in_waiting).decode()
                        # Strip special characters and "CTS" substring
                        idn_string = re.sub(r"[^a-zA-Z0-9,-]+|CTS", "", idn_string)
                        curSerial.close()
                    # Check if the name matches
                    if matchingName in idn_string:
                        toReturn = SCPI_Info(
                            port=port,
                            baud_rate=detected_BR,
                            idn=idn_string,
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
        with cls._instrument_lock:
            curLockedPorts: List[str] = [
                instr.scpi_instrument.port for instr in cls.InstrumentsList
            ]
            for instr in curAliasesList:
                SCPIInfo: Optional[SCPI_Info] = cls.find_instrument(
                    instr, curLockedPorts
                )
                if SCPIInfo is not None:
                    curInstrumentWrapper: Optional[Instrument_Entry] = (
                        custom_instr_handler(SCPIInfo)
                    )
                    if curInstrumentWrapper is not None:
                        cls.InstrumentsList.append(curInstrumentWrapper)
                    else:
                        raise Exception(
                            RuntimeError(
                                f"Failed to create Instrument_Entry for instrument: {instr}"
                            )
                        )

    @classmethod
    def save_config(cls) -> None:
        with cls._file_lock:
            # Create array of SCPI_Info
            instr_info_list: List[SCPI_Info] = []
            for instr in cls.InstrumentsList:
                instr_info_list.append(instr.data)
            # Serialize to JSON
            instr_info_json: List[dict[str, Any]] = [
                asdict(item) for item in instr_info_list
            ]
            with open(Config.instrument_config_datapath, "w") as data_file:
                json.dump(instr_info_json, data_file, indent=4)

    @classmethod
    def load_config(cls):
        with cls._file_lock:
            try:
                with open(Config.instrument_config_datapath, "r") as data_file:
                    instr_info_json: List[dict[str, Any]] = json.load(data_file)
                    instr_info_list: List[SCPI_Info] = [
                        SCPI_Info(**item) for item in instr_info_json
                    ]
                    for instr_info in instr_info_list:
                        if not cls.is_scpi_info_busy(instr_info):
                            curInstrumentWrapper: Optional[Instrument_Entry] = (
                                custom_instr_handler(instr_info)
                            )
                            if curInstrumentWrapper is not None:
                                cls.InstrumentsList.append(curInstrumentWrapper)
                            else:
                                raise Exception(
                                    RuntimeError(
                                        f"Failed to create Instrument_Entry for instrument: {instr.alias}"
                                    )
                                )
            except FileNotFoundError:
                # No previous configuration found
                cls.fetch_all_instruments(Config.instrAliasesList)
                pass
