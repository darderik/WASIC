import threading
from threading import Thread
import time
import json
from typing import List, Optional, Any, Tuple
from dataclasses import asdict
from serial import Serial
from serial.tools.list_ports import comports
from serial.tools.list_ports_common import ListPortInfo
from instruments import Instrument_Entry, SCPI_Info
from easy_scpi import Instrument
from .utilities import detect_baud_rate, validate_response, detect_baud_wrapper
from config import Config, comm_mode
from user_defined import custom_instr_handler


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
        Returns an Instrument_Entry object with similiar idn string.

        Args:
            alias (str): The match of the instrument.

        Returns:
            Optional[Instrument_Entry]: An Instrument_Entry object that matches the alias, or None if no instrument with that alias is found.
        """
        with cls._instrument_lock:
            for instr in cls.InstrumentsList:
                if alias.lower() in instr.data.idn.lower():
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
                        instr.com_obj.write(b"*IDN?\n")  # Send identification query
                        time.sleep(Config.default_timeout)
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
    def fetch_all_instruments(cls, curAliasesList: List[str]) -> None:
        """
        Fetches all instruments based on the provided list of aliases.

        This method iterates over the provided list of instrument aliases,
        iterates over all available ports with their baud rates, and when a
        matching identification string is found, creates an Instrument_Entry instance
        using custom_instr_handler and appends it to the InstrumentsList.

        Args:
            curAliasesList (List[str]): A list of instrument aliases to fetch.
        """
        with cls._instrument_lock:
            # Busy ports
            curLockedPorts: List[str] = [
                instr.scpi_instrument.port for instr in cls.InstrumentsList
            ]

            # Create a list of all comports with correct baud rates
            all_comports: list[ListPortInfo] = comports()
            available_ports: List[str] = [
                port.name for port in all_comports if port.name not in curLockedPorts
            ]
            com_idn_baud: List[Tuple[str, str, int]] = []

            # Populate with baud rates and idn strings
            threadsList: List[Thread] = []
            for port in available_ports:
                newThread: Thread = Thread(
                    target=detect_baud_wrapper,
                    args=(port, None, Config.default_timeout, com_idn_baud),
                )
                newThread.start()
                threadsList.append(newThread)
            for thread in threadsList:
                thread.join()

            for alias in curAliasesList:
                scpi_info: Optional[SCPI_Info] = None
                # Search for a matching port/IDN from the tuple list
                for port, idn_string, baud in com_idn_baud:
                    if alias.lower() in idn_string.lower():
                        scpi_info = SCPI_Info(
                            port=port,
                            baud_rate=baud,
                            idn=idn_string,
                            alias=alias,
                        )
                        break
                if scpi_info is not None:
                    instrument_entry: Optional[Instrument_Entry] = custom_instr_handler(
                        scpi_info
                    )
                    if instrument_entry is not None:
                        cls.InstrumentsList.append(instrument_entry)
                        curLockedPorts.append(scpi_info.port)  # Update locked ports
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
                        instrument_entry: Optional[Instrument_Entry] = (
                            custom_instr_handler(instr_info)
                        )
                        if instrument_entry is not None:
                            cls.InstrumentsList.append(instrument_entry)
                        else:
                            raise RuntimeError(
                                f"Failed to create Instrument_Entry for instrument: {instr_info.idn}"
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
