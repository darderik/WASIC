import threading
from threading import Thread, Lock
import time
import json
from typing import List, Optional, Any, Tuple, Dict
from dataclasses import asdict
from serial import Serial
from serial.tools.list_ports import comports
from serial.tools.list_ports_common import ListPortInfo
from instruments import Instrument_Entry, SCPI_Info
from easy_scpi import Instrument
from .utilities import detect_baud_rate, validate_response, detect_baud_wrapper
from config import Config
from user_defined import custom_instr_handler
import logging

logger = logging.getLogger(__name__)


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
    _instance = None
    instruments_list: List[Instrument_Entry] = []

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(Connections, cls).__new__(cls, *args, **kwargs)
            cls._config = Config()
        return cls._instance

    def get_instrument(self, alias: str) -> Optional[Instrument_Entry]:
        """
        Returns an Instrument_Entry object with similiar idn string.

        Args:
            alias (str): The match of the instrument.

        Returns:
            Optional[Instrument_Entry]: An Instrument_Entry object that matches the alias, or None if no instrument with that alias is found.
        """
        with self._instrument_lock:
            logger.debug(f"Searching for instrument with alias: {alias}")
            for instr in self.instruments_list:
                if alias.lower() in instr.data.idn.lower():
                    logger.debug(f"Found instrument with alias: {alias}")
                    return instr
            logger.warning(f"No instrument found with alias: {alias}")
        return None

    def get_instruments_aliases(self, idn: bool = False) -> List[str]:
        """
        Returns a list of aliases of all instruments in the InstrumentsList.

        Returns:
            List[str]: A list of aliases of all instruments in the InstrumentsList.
        """
        with self._instrument_lock:
            if not idn:
                return [instr.data.alias for instr in self.instruments_list]
            else:
                return [instr.data.idn for instr in self.instruments_list]

    def is_scpi_info_busy(self, instr_info: SCPI_Info) -> bool:
        """
        Checks if the SCPI_Info's port is currently busy (i.e., already in use by an instrument).

        Args:
            instr_info (SCPI_Info): The SCPI_Info object to check.

        Returns:
            bool: True if the SCPI_Info's port is busy, False otherwise.
        """
        with self._instrument_lock:
            return any(
                instr.scpi_instrument.port == instr_info.port
                for instr in self.instruments_list
            )

    def verify_instruments(self) -> None:
        """
        Verifies the connected instruments based on the configured communication mode.
        """
        with self._instrument_lock:
            comm_mode: str = self._config.get("communication_mode", "pyvisa").lower()
            valid_instruments = []
            if comm_mode == "pyvisa":
                for instr in self.instruments_list:
                    try:
                        _ = instr.scpi_instrument.id  # Attempt to retrieve ID
                        valid_instruments.append(instr)  # Instrument is valid
                    except RuntimeError as rt:
                        logger.warning(
                            f"Failed to verify instrument: {instr.data.idn} -> {rt}"
                        )
                        instr.scpi_instrument.disconnect()  # Free up COM port lock
            elif comm_mode == "serial":
                for instr in self.instruments_list:
                    try:
                        timeout: float = self._config.get("default_timeout", 0.5)
                        instr.com_obj.open()
                        try:
                            instr.com_obj.write(b"*IDN?\n")  # Send identification query
                            time.sleep(timeout)
                            response: str = instr.com_obj.read(
                                instr.com_obj.in_waiting
                            ).decode()
                            if validate_response(response.encode()):
                                valid_instruments.append(instr)  # Instrument is valid
                        finally:
                            instr.com_obj.close()
                    except Exception as e:
                        logger.error(f"Error verifying instrument: {e}")
            self.instruments_list = valid_instruments  # Update the InstrumentsList

    def fetch_all_instruments(self, curAliasesList: List[str]) -> None:
        """
        Fetches all instruments based on the provided list of aliases.

        This method iterates over the provided list of instrument aliases,
        iterates over all available ports with their baud rates, and when a
        matching identification string is found, creates an Instrument_Entry instance
        using custom_instr_handler and appends it to the InstrumentsList.

        Args:
            curAliasesList (List[str]): A list of instrument aliases to fetch.
        """
        with self._instrument_lock:
            logger.debug(f"Fetching instruments based on aliases: {curAliasesList}")
            curLockedPorts: List[str] = [
                instr.scpi_instrument.port for instr in self.instruments_list
            ]
            logger.debug(f"Locked ports: {curLockedPorts}")
            all_comports: List[ListPortInfo] = comports()
            available_ports: List[str] = [
                port.name for port in all_comports if port.name not in curLockedPorts
            ]
            com_idn_baud: List[Tuple[str, str, int]] = []
            com_idn_baud_lock = Lock()

            def safe_detect_baud_wrapper(port):
                nonlocal com_idn_baud
                result = detect_baud_wrapper(port, None, timeout)
                if result is not None:
                    with com_idn_baud_lock:
                        com_idn_baud.append(result)

            threadsList: List[Thread] = []
            timeout: float = self._config.get("default_timeout", 0.5)
            for port in available_ports:
                newThread: Thread = Thread(
                    target=safe_detect_baud_wrapper, args=(port,)
                )
                newThread.start()
                threadsList.append(newThread)
            for thread in threadsList:
                thread.join()
            logger.debug(f"COM ports, IDN strings, and baud rates: {com_idn_baud}")

            for alias in curAliasesList:
                scpi_info: Optional[SCPI_Info] = None
                for port, idn_string, baud in com_idn_baud:
                    if alias.lower() in idn_string.lower():
                        splitted_idn: List[str] = idn_string.split(",")
                        scpi_info = SCPI_Info(
                            port=port,
                            baud_rate=baud,
                            idn=idn_string,
                            alias=alias,
                            name=splitted_idn[0] + " " + splitted_idn[1],
                        )
                        logger.debug(f"Found instrument: {alias} -> {scpi_info}")
                        break
                if scpi_info is not None:
                    instrument_entry: Optional[Instrument_Entry] = custom_instr_handler(
                        scpi_info
                    )
                    if instrument_entry is not None:
                        self.instruments_list.append(instrument_entry)
                        curLockedPorts.append(scpi_info.port)
                    else:
                        logger.error(
                            f"Failed to create Instrument_Entry for instrument: {scpi_info.idn}"
                        )

    def save_config(self) -> None:
        """
        Saves the current configuration of instruments to a JSON file.
        """
        with self._file_lock:
            instr_info_list: List[SCPI_Info] = [
                instr.data for instr in self.instruments_list
            ]
            instr_info_json: List[dict[str, Any]] = [
                asdict(item) for item in instr_info_list
            ]
            try:
                file_path: str = self._config.get("instrument_connections_datapath", "")
                with open(file_path, "w") as data_file:
                    json.dump(instr_info_json, data_file, indent=4)
            except FileNotFoundError:
                logger.error(
                    f"Error: The file '{file_path}' does not exist or the directory is invalid."
                )
            except PermissionError:
                logger.error(
                    f"Error: Insufficient permissions to write to '{file_path}'."
                )
            except IsADirectoryError:
                logger.error(f"Error: '{file_path}' is a directory, not a file.")
            except TypeError as e:
                logger.error(f"JSON serialization error: {e}")
            except OSError as e:
                logger.error(f"I/O error: {e}")
            except ValueError as e:
                logger.error(f"Configuration error: {e}")
            except Exception as e:
                logger.error(f"An error occurred while saving configuration: {e}")

    def load_config(self) -> None:
        """
        Loads the configuration of instruments from a JSON file.
        """
        with self._file_lock:
            try:
                file_path: str = self._config.get("instrument_connections_datapath", "")
                with open(file_path, "r") as data_file:
                    instr_info_json: List[Dict[str, Any]] = json.load(data_file)
                    instr_info_list: List[SCPI_Info] = [
                        SCPI_Info(**item) for item in instr_info_json
                    ]
                for instr_info in instr_info_list:
                    if not self.is_scpi_info_busy(instr_info):
                        instrument_entry: Optional[Instrument_Entry] = (
                            custom_instr_handler(instr_info)
                        )
                        if instrument_entry is not None:
                            self.instruments_list.append(instrument_entry)
                        else:
                            logger.error(
                                f"Failed to create Instrument_Entry for instrument: {instr_info.idn}"
                            )
            except FileNotFoundError:
                logger.warning(
                    "Configuration file not found. Fetching instruments based on configured aliases."
                )
                self.fetch_all_instruments(self._config.get("instr_aliases", []))
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse configuration file: {e}")
                raise RuntimeError(f"Failed to parse configuration file: {e}")
            except (OSError, ValueError) as e:
                logger.error(f"Error loading configuration: {e}")
                self.fetch_all_instruments(self._config.get("instr_aliases", []))
