from os import read
import threading
import logging
from threading import Thread, Lock
import time
import json
from typing import List, Optional, Any, Tuple, Dict
from dataclasses import asdict
from serial.tools.list_ports import comports
from instruments import Instrument_Entry, SCPI_Info
from easy_scpi import Instrument
from config import Config
from addons import custom_instr_handler
from .utilities import detect_baud_wrapper, is_instrument_in_aliases
import pyvisa as visa

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
    backend: str = ""

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(Connections, cls).__new__(cls, *args, **kwargs)
            cls._config = Config()
            cls._instance.backend = "@py"
        return cls._instance

    def get_instrument(self, keyword: str) -> Optional[Instrument_Entry]:
        """
        Returns an Instrument_Entry object with similiar idn string.

        Args:
            alias (str): The match of the instrument.

        Returns:
            Optional[Instrument_Entry]: An Instrument_Entry object that matches the alias, or None if no instrument with that alias is found.
        """
        with self._instrument_lock:
            logger.debug(f"Searching for instrument with keyword: {keyword}")
            for instr in self.instruments_list:
                if keyword.lower() in instr.data.idn.lower():
                    logger.debug(f"Found instrument with keyword: {keyword}")
                    return instr
            logger.warning(f"No instrument found with keyword: {keyword}")
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
            valid_instruments = []
            for instr in self.instruments_list:
                try:
                    _ = instr.scpi_instrument.id  # Attempt to retrieve ID
                    valid_instruments.append(instr)  # Instrument is valid
                except RuntimeError as rt:
                    logger.warning(
                        f"Failed to verify instrument: {instr.data.idn} -> {rt}"
                    )
                    instr.scpi_instrument.disconnect()  # Free up COM port lock
            self.instruments_list = valid_instruments  # Update the InstrumentsList

    def fetch_all_instruments(
        self,
        curAliasesList: Optional[List[str]] = None,
        clear_list: bool = True,
        visa_dll_path: str = Config().get("custom_backend", ""),
    ) -> None:
        """
        Fetches all instruments based on the provided list of aliases, including USB instruments.

        Args:
            curAliasesList (List[str]): A list of instrument aliases to fetch.
            clear_list (bool): Whether to clear the current instruments list before fetching.
            visa_dll_path (str): Path to the VISA DLL for the resource manager.
        """
        curAliasesList = curAliasesList or self._config.get("instr_aliases")
        with self._instrument_lock:
            if clear_list:
                self._clear_instruments()

            logger.debug(f"Fetching instruments based on aliases: {curAliasesList}")
            curLockedPorts = self._get_locked_ports()
            available_ports = self._get_available_ports(curLockedPorts)
            self._fetch_usb_instruments(curLockedPorts, visa_dll_path)

            com_idn_baud = self._fetch_com_instruments(available_ports)
            self._process_com_instruments(com_idn_baud)

    def _clear_instruments(self) -> None:
        """Disconnects and clears the current instruments list."""
        for instr in self.instruments_list:
            try:
                instr.scpi_instrument.disconnect()
                self.instruments_list.remove(instr)
            except Exception as e:
                logger.error(
                    f"Failed to disconnect instrument: {instr.data.idn} -> {e}"
                )

    def _get_locked_ports(self) -> List[str]:
        """Returns a list of ports currently locked by instruments."""
        return [instr.scpi_instrument.port for instr in self.instruments_list]

    def _get_available_ports(self, locked_ports: List[str]) -> List[str]:
        """Returns a list of available COM ports."""
        all_comports = comports()
        return [port.name for port in all_comports if port.name not in locked_ports]

    def _fetch_com_instruments(
        self, available_ports: List[str]
    ) -> List[Tuple[str, str, int]]:
        """Fetches instruments connected via COM ports."""
        com_idn_baud: List[Tuple[str, str, int]] = []
        com_idn_baud_lock = Lock()
        threads = []

        for port in available_ports:
            thread = Thread(
                target=detect_baud_wrapper,
                args=(port, com_idn_baud, com_idn_baud_lock),
            )
            thread.start()
            threads.append(thread)

        for thread in threads:
            thread.join()

        logger.debug(f"COM ports, IDN strings, and baud rates: {com_idn_baud}")
        return com_idn_baud

    def _fetch_usb_instruments(
        self, locked_ports: List[str], visa_dll_path: str
    ) -> None:
        """Fetches instruments connected via USB using the VISA resource manager."""
        try:
            resource_manager = (
                visa.ResourceManager(visa_dll_path)
                if visa_dll_path
                else visa.ResourceManager("@py")
            )
            all_usb_instruments = resource_manager.list_resources()
            logger.debug(f"USB instruments found: {all_usb_instruments}")
            for usb_instr in (
                x
                for x in all_usb_instruments
                if x not in locked_ports
                # and "ASRL" not in x
            ):
                self._process_usb_instrument(usb_instr)

        except Exception as e:
            logger.error(f"Failed to initialize VISA resource manager: {e}")

    def _process_usb_instrument(self, usb_instr: str) -> None:
        """Processes a single USB instrument."""
        try:
            # Always use custom backend for USB instruments (pyvisa-py not supported)
            cur_instr = Instrument(
                port=usb_instr,
                backend=Config().get("custom_backend", ""),
                write_terminator="\n",
                read_terminator="\n",
            )
            try:
                cur_instr.connect()
                id_str = cur_instr.id
                if not id_str:
                    logger.error(
                        f"Failed to read IDN from {usb_instr} on first attempt. Skipping..."
                    )
                    return
            except Exception as e:
                logger.error(
                    f"Protocol error: |{e}| while trying to read IDN from {usb_instr}. Skipping..."
                )
                return
            alias = is_instrument_in_aliases(idn=id_str)
            del cur_instr
            if alias:
                # Force backend to custom backend for USB instruments (globally)
                if self.backend == "@py" or self.backend == "":
                    # Use custom backend for USB instruments
                    self.backend = Config().get("custom_backend", "")
                splitted_idn = id_str.split(",")
                scpi_info = SCPI_Info(
                    port=usb_instr,
                    baud_rate=0,
                    idn=id_str,
                    alias=alias,
                    name=f"{splitted_idn[0]} {splitted_idn[1]}",
                )
                self._add_instrument(scpi_info)
        except Exception as e:
            logger.error(f"Failed to create instrument for USB: {usb_instr} -> {e}")

    def _process_com_instruments(
        self, com_idn_baud: List[Tuple[str, str, int]]
    ) -> None:
        """Processes instruments connected via COM ports."""
        for port, idn_string, baud in com_idn_baud:
            alias = is_instrument_in_aliases(idn=idn_string)
            if alias:
                splitted_idn = idn_string.split(",")
                scpi_info = SCPI_Info(
                    port=port,
                    baud_rate=baud,
                    idn=idn_string,
                    alias=alias,
                    name=f"{splitted_idn[0]} {splitted_idn[1]}",
                )
                logger.debug(f"Found instrument: {alias} -> {scpi_info}")
                self._add_instrument(scpi_info)

    def _add_instrument(self, scpi_info: SCPI_Info) -> None:
        """Adds an instrument to the instruments list."""
        instrument_entry = custom_instr_handler(scpi_info)
        if instrument_entry:
            self.instruments_list.append(instrument_entry)
            logger.info(f"Successfully added instrument: {scpi_info.idn}")
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
                # Understand if ni-visa backend is needed (usb instruments)
                usb_instr = [item for item in instr_info_list if "USB" in item.port]
                if usb_instr != []:
                    self.backend = Config().get("custom_backend", "")

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
