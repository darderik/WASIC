import re
import threading
import time
from typing import List, Optional, Any
from serial import Serial
from serial.tools.list_ports import comports
from serial.tools.list_ports_common import ListPortInfo
from instruments import Instrument_Entry, SCPI_Info
from easy_scpi import Instrument
from .utilities import detect_baud_rate, validate_response
from config import Config, comm_mode
import json
from dataclasses import asdict


class Connections:
    """
    The Connections class manages a collection of instruments connected via serial ports.
    It provides methods to verify the connected instruments, find a specific instrument by name,
    and fetch all instruments based on a list of aliases (that are names or even serial numbers).

    Attributes:
        _instrument_lock (threading.Lock): A lock to ensure thread-safe operations on the Instruments list.
        _file_lock (threading.Lock): A lock to ensure thread-safe file operations.
        InstrumentsList (List[Instrument_Entry]): A list of wrapped SCPI instruments.
    """

    _instrument_lock = threading.Lock()
    _file_lock = threading.Lock()
    InstrumentsList: List[Instrument_Entry] = list()

    @classmethod
    def get_instrument(cls, alias: str) -> Optional[Instrument_Entry]:
        """
        Returns an Instrument_Entry object with the given alias.

        Args:
            alias (str): The alias of the instrument to return.

        Returns:
            Optional[Instrument_Entry]: An Instrument_Entry object with the given alias, or None if no instrument with that alias is found.
        """
        with cls._instrument_lock:
            for instr in cls.InstrumentsList:
                if (
                    alias.lower() in instr.data.alias.lower()
                    or alias.lower() in instr.scpi_instrument.id.lower()
                ):
                    return instr
        return None

    @classmethod
    def get_instruments_aliases(cls, idn: bool = False) -> List[str]:
        """
        Returns a list of aliases of all instruments in the InstrumentsList.

        Returns:
            List[str]: A list of aliases of all instruments in the InstrumentsList.
        """
        with cls._instrument_lock:
            if not idn:
                return [instr.data.alias for instr in cls.InstrumentsList]
            else:
                return [instr.data.idn for instr in cls.InstrumentsList]

    @classmethod
    def is_scpi_info_busy(cls, instr_info: SCPI_Info) -> bool:
        """
        Checks if the SCPI_Info's port is currently busy (i.e., already in use by an instrument).

        Args:
            instr_info (SCPI_Info): The SCPI_Info object to check.

        Returns:
            bool: True if the SCPI_Info's port is busy, False otherwise.
        """
        with cls._instrument_lock:
            return any(
                instr.scpi_instrument.port == instr_info.port
                for instr in cls.InstrumentsList
            )

    @classmethod
    def verify_instruments(cls) -> None:
        """
        Verifies the connected instruments based on the configured communication mode.
        Removes instruments that do not respond correctly.
        """
        with cls._instrument_lock:
            if Config.communication_mode == comm_mode.pyVisa:
                valid_instruments = []
                for instr in cls.InstrumentsList:
                    try:
                        _ = instr.scpi_instrument.id  # Attempt to retrieve ID
                        valid_instruments.append(instr)  # Instrument is valid
                    except Exception as e:
                        instr.scpi_instrument.disconnect()  # Free up COM port lock
            elif Config.communication_mode == comm_mode.serial:
                valid_instruments = []
                for instr in cls.InstrumentsList:
                    try:
                        instr.com_obj.open()
                        instr.com_obj.write(b"*IDN?")  # Send identification query
                        time.sleep(instr.data.timeout)
                        response: str = instr.com_obj.read(
                            instr.com_obj.in_waiting
                        ).decode()
                        instr.com_obj.close()
                        if validate_response(response.encode()):
                            valid_instruments.append(instr)  # Instrument is valid
                        else:
                            instr.com_obj.close()
                    except Exception as e:
                        instr.com_obj.close()
                cls.InstrumentsList = valid_instruments
            cls.InstrumentsList = valid_instruments  # Update the InstrumentsList

    @classmethod
    def find_instrument(
        cls, matchingName: str, curLockedPorts: List[str]
    ) -> Optional[SCPI_Info]:
        """
        Finds an instrument connected to a serial port that matches the given name.

        Args:
            matchingName (str): The name to match against the instrument's identification string.
            curLockedPorts (List[str]): List of ports that are currently locked.

        Returns:
            Optional[SCPI_Info]: An SCPI_Info object containing the port, baud rate, and identification string of the matching instrument,
                                 or None if no matching instrument is found.
        """

        ports: List[ListPortInfo] = comports()
        instrTimeout: float = Config.default_timeout
        # Filter out locked ports
        available_ports: List[str] = [
            port.device for port in ports if port.device not in curLockedPorts
        ]
        for port in available_ports:
            detected_BR: Optional[int] = detect_baud_rate(
                port=port, timeout=instrTimeout
            )
            if detected_BR is None:
                continue  # Unable to detect baud rate, skip to next port
            try:
                with Serial(port, detected_BR, timeout=instrTimeout) as curSerial:
                    curSerial.flushInput()
                    curSerial.write(b"*IDN?")  # Send identification query
                    time.sleep(instrTimeout)
                    idn_bytes = curSerial.read(curSerial.in_waiting)
                    idn_string = idn_bytes.decode().strip()
                    # Strip special characters
                    # idn_string = re.sub(r"[^a-zA-Z0-9,-\s]", "", idn_string)
            except Exception as e:
                continue  # Skip this port if any error occurs
            if matchingName.lower() in idn_string.lower():
                return SCPI_Info(
                    port=port,
                    baud_rate=detected_BR,
                    idn=idn_string,
                    alias=matchingName,
                )
        return None

    @classmethod
    def fetch_all_instruments(cls, curAliasesList: List[str]) -> None:
        """
        Fetches all instruments based on the provided list of aliases.

        This method iterates over the provided list of instrument aliases, finds the corresponding
        SCPI instrument information, creates Instrument_Entry instances using custom_instr_handler,
        and appends them to the InstrumentsList.

        Args:
            curAliasesList (List[str]): A list of instrument aliases to fetch.
        """
        with cls._instrument_lock:
            curLockedPorts: List[str] = [
                instr.scpi_instrument.port for instr in cls.InstrumentsList
            ]
            for alias in curAliasesList:
                SCPIInfo: Optional[SCPI_Info] = cls.find_instrument(
                    alias, curLockedPorts
                )
                if SCPIInfo is not None:
                    from user_defined import custom_instr_handler

                    instrument_entry: Optional[Instrument_Entry] = custom_instr_handler(
                        SCPIInfo
                    )
                    if instrument_entry is not None:
                        cls.InstrumentsList.append(instrument_entry)
                        curLockedPorts.append(SCPIInfo.port)  # Update locked ports
                    else:
                        raise RuntimeError(
                            f"Failed to create Instrument_Entry for instrument: {alias}"
                        )

    @classmethod
    def save_config(cls) -> None:
        """
        Saves the current configuration of instruments to a JSON file.
        """
        with cls._file_lock:
            instr_info_list: List[SCPI_Info] = [
                instr.data for instr in cls.InstrumentsList
            ]
            instr_info_json: List[dict[str, Any]] = [
                asdict(item) for item in instr_info_list
            ]
            try:
                with open(Config.instrument_config_datapath, "w") as data_file:
                    json.dump(instr_info_json, data_file, indent=4)
            except Exception as e:
                # Handle file write errors if necessary
                raise RuntimeError(f"Failed to save configuration: {e}")

    @classmethod
    def load_config(cls) -> None:
        """
        Loads the configuration of instruments from a JSON file.
        If the configuration file does not exist, fetches all instruments based on the configured aliases.
        """
        with cls._file_lock:
            try:
                with open(Config.instrument_config_datapath, "r") as data_file:
                    instr_info_json: List[dict[str, Any]] = json.load(data_file)
                    instr_info_list: List[SCPI_Info] = [
                        SCPI_Info(**item) for item in instr_info_json
                    ]
                for instr_info in instr_info_list:
                    if not cls.is_scpi_info_busy(instr_info):
                        from user_defined import custom_instr_handler

                        instrument_entry: Optional[Instrument_Entry] = (
                            custom_instr_handler(instr_info)
                        )
                        if instrument_entry is not None:
                            cls.InstrumentsList.append(instrument_entry)
                        else:
                            raise RuntimeError(
                                f"Failed to create Instrument_Entry for instrument: {instr_info.alias}"
                            )
            except FileNotFoundError:
                # No previous configuration found; fetch instruments based on configured aliases
                cls.fetch_all_instruments(Config.instrAliasesList)
            except json.JSONDecodeError as e:
                # Handle JSON parsing errors if necessary
                raise RuntimeError(f"Failed to parse configuration file: {e}")
            except Exception as e:
                # Handle other unforeseen exceptions
                Connections.fetch_all_instruments(Config.instrAliasesList)
