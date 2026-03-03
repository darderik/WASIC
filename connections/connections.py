import os
import sys
from pathlib import Path
import threading
import logging
from threading import Thread, Lock
import json
from typing import List, Optional, Any, Tuple, Dict, cast
from dataclasses import asdict
from serial.tools.list_ports import comports
from instruments import Instrument_Entry, SCPI_Info
from config import Config
from .baud_detector import BaudTrialDetector
import pymeasure.instruments as pmi
import pymeasure.adapters as pma
from pymeasure.instruments.instrument import Instrument

logger = logging.getLogger(__name__)
MULTITHREAD_FLAG = True  # Set to False to disable multithreading for COM port detection

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
        # Singleton pattern: keep one shared connection manager across the app.
        if cls._instance is None:
            cls._instance = super(Connections, cls).__new__(cls, *args, **kwargs)
            cls._config = Config()
            # Default to pyvisa-py backend for USB/VISA resources.
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
            for instr in self.instruments_list:
                resource = instr.scpi_instrument
                if isinstance(resource, pma.SerialAdapter):
                    if str(resource.connection.port) == instr_info.port:
                        return True
                elif isinstance(resource, pma.VISAAdapter):
                    if str(resource.resource_name) == instr_info.port:
                        return True
                else:
                    if str(resource) == instr_info.port:
                        return True
            return False

    def verify_instruments(self) -> None:
        """
        Verifies the connected instruments based on the configured communication mode.
        """
        with self._instrument_lock:
            valid_instruments = []
            for instr in self.instruments_list:
                try:
                    _ = instr.scpi_instrument.ask("*IDN?")
                    valid_instruments.append(instr)  # Instrument is valid
                except RuntimeError as rt:
                    logger.warning(
                        f"Failed to verify instrument: {instr.data.idn} -> {rt}"
                    )
                    self._disconnect_instrument(instr.scpi_instrument)
                except Exception as ex:
                    logger.warning(
                        f"Failed to verify instrument: {instr.data.idn} -> {ex}"
                    )
                    self._disconnect_instrument(instr.scpi_instrument)
            self.instruments_list = valid_instruments  # Update the InstrumentsList

    def fetch_all_instruments(
        self,
        curAliasesList: Optional[List[str]] = None,
        clear_list: bool = True,
    ) -> None:
        """
        Fetches all instruments based on the provided list of aliases, including USB instruments.

        Args:
            curAliasesList (List[str]): A list of instrument aliases to fetch.
            clear_list (bool): Whether to clear the current instruments list before fetching.
        """
        curAliasesList = curAliasesList or self._config.get("instr_aliases")
        with self._instrument_lock:
            if clear_list:
                self._clear_instruments()

            logger.debug(f"Fetching instruments based on aliases: {curAliasesList}")
            # Keep track of resources already open by existing entries.
            curLockedPorts = self._get_locked_ports()
            # Scan COM ports first, excluding currently locked resources.
            available_ports = self._get_available_ports(curLockedPorts)
            # Scan VISA resources (USB/GPIB/TCPIP), also skipping locked entries.
            self._fetch_usb_instruments(curLockedPorts)

            # Probe serial ports by trying candidate baud rates and querying *IDN?.
            com_idn_baud = self._fetch_com_instruments(available_ports)
            # Build SCPI_Info objects and register matching aliases only.
            self._process_com_instruments(com_idn_baud)

    def _clear_instruments(self) -> None:
        """Disconnects and clears the current instruments list."""
        for instr in list(self.instruments_list):
            try:
                self._disconnect_instrument(instr.scpi_instrument)
                logger.debug(f"Disconnected instrument: {instr.data.idn}")
            except Exception as e:
                logger.error(
                    f"Failed to disconnect instrument: {instr.data.idn} -> {e}"
                )
        self.instruments_list = []

    @staticmethod
    def _disconnect_instrument(instr: Instrument) -> None:
        try:
            instr.adapter.connection.close()
        except Exception:
            instr.close()

    def _get_locked_ports(self) -> List[str]:
        """Returns a list of ports currently locked by instruments."""
        locked_ports: List[str] = []
        for instr in self.instruments_list:
            resource = instr.scpi_instrument
            if isinstance(resource, pma.SerialAdapter):
                locked_ports.append(str(resource.connection.port))
            elif isinstance(resource, pma.VISAAdapter):
                locked_ports.append(str(resource.resource_name))
        return locked_ports

    def _get_available_ports(self, locked_ports: List[str]) -> List[str]:
        """Returns a list of available COM ports."""
        all_comports = comports()
        # On Linux lots of ttyS* pseudo-ports appear; prefer USB/ACM to avoid noise.
        if sys.platform.startswith("linux"):
            candidates = [
                port.device
                for port in all_comports
                if port.device.startswith("/dev/ttyUSB")
                or port.device.startswith("/dev/ttyACM")
            ]
        else:
            candidates = [port.name for port in all_comports]

        return [port for port in candidates if port not in locked_ports]

    def _fetch_com_instruments(
        self, available_ports: List[str]
    ) -> List[Tuple[str, str, int]]:
        """Fetches instruments connected via COM ports."""
        com_idn_baud: List[Tuple[str, str, int]] = []
        com_idn_baud_lock = Lock()
        threads = []

        if MULTITHREAD_FLAG:
            # Probe each port in parallel; each worker appends successful detections.
            for port in available_ports:
                thread = Thread(
                    target=self._detect_baud_for_port,
                    args=(port, com_idn_baud, com_idn_baud_lock),
                )
                thread.start()
                threads.append(thread)

            for thread in threads:
                thread.join()
        else:
            # Single-thread fallback useful for debugging race/resource issues.
            for port in available_ports:
                    result = BaudTrialDetector(port=port).detect()
                    if result is not None:
                        detected: Tuple[str, str, int] = (port, result.idn, result.baud_rate)
                        logger.debug(
                            f"BR Detection on port {detected[0]} with Baud {detected[2]} and IDN {detected[1]}"
                    )
                    com_idn_baud.append(detected)

        logger.debug(f"COM ports, IDN strings, and baud rates: {com_idn_baud}")
        return com_idn_baud

    def _detect_baud_for_port(
        self,
        port: str,
        target: List[Tuple[str, str, int]],
        target_lock: Lock,
    ) -> None:
        # Try known baud rates and collect only successful *IDN? detections.
        result = BaudTrialDetector(port=port).detect()
        if result is None:
            logger.debug(f"Failed to detect baud rate for port {port}")
            return

        detected: Tuple[str, str, int] = (port, result.idn, result.baud_rate)
        logger.debug(
            f"BR Detection on port {detected[0]} with Baud {detected[2]} and IDN {detected[1]}"
        )
        with target_lock:
            target.append(detected)

    def _fetch_usb_instruments(
        self, locked_ports: List[str]
    ) -> None:
        """Fetches instruments connected via USB using the PyVISA resource manager (@py backend)."""
        try:
            all_usb_instruments = pmi.list_resources()
            logger.debug(f"USB instruments found via pymeasure: {all_usb_instruments}")
            for usb_instr in (
                x
                for x in all_usb_instruments
                if x not in locked_ports
                # Serial VISA resources are handled in COM probing path.
                and "ASRL" not in x
            ):
                self._process_usb_instrument(usb_instr, "@py")
        except Exception as e:
            logger.error(f"Failed to initialize USB resource manager via pyvisa: {e}")

    def _process_usb_instrument(self, usb_instr: str, backend: str) -> None:
        """Processes a single USB instrument."""
        id_str = ""
        cur_instr: Optional[Instrument] = None
        try:
            cur_instr = Instrument(
                adapter=usb_instr,
                backend=backend,
                name=usb_instr,
            )
            id_str = cur_instr.ask("*IDN?")
            alias = Config().is_in_instr_aliases(id_str)
            if alias:
                splitted_idn = id_str.split(",")
                scpi_info = SCPI_Info(
                    port=usb_instr,
                    baud_rate=0,
                    idn=id_str,
                    alias=alias,
                    resource_str=usb_instr,
                    name=f"{splitted_idn[0]} {splitted_idn[1]}",
                    backend=backend                
                    )
                self._add_instrument(scpi_info)
        except Exception as e:
            logger.error(f"Failed to create instrument for USB: {usb_instr} -> {e}")
        finally:
            try:
                if cur_instr is not None:
                    cur_instr.close()
            except Exception:
                pass

    def _process_com_instruments(
        self, com_idn_baud: List[Tuple[str, str, int]]
    ) -> None:
        """Processes instruments connected via COM ports."""
        for port, idn_string, baud in com_idn_baud:
            # Convert COMx -> ASRLx::INSTR for VISAAdapter.
            resource_str = f"ASRL{''.join(filter(str.isdigit, port))}::INSTR"
            alias = Config().is_in_instr_aliases(idn_string)
            if alias:
                splitted_idn = idn_string.split(",")
                scpi_info = SCPI_Info(
                    port=port,
                    baud_rate=baud,
                    idn=idn_string,
                    alias=alias,
                    resource_str=resource_str,
                    name=f"{splitted_idn[0]} {splitted_idn[1]}",
                )
                logger.debug(f"Found instrument: {alias} -> {scpi_info}")
                self._add_instrument(scpi_info)

    def _add_instrument(self, scpi_info: SCPI_Info) -> None:
        """Adds an instrument to the instruments list."""
        instrument_entry = self._custom_instr_handler(scpi_info)
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
            raw_path: str = self._config.get("instrument_connections_datapath", "")
            file_path = Path(str(raw_path).replace("\\", os.sep))
            try:
                if not raw_path:
                    raise ValueError("Configuration file path is not set.")
                file_path.parent.mkdir(parents=True, exist_ok=True)
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
                raw_path: str = self._config.get("instrument_connections_datapath", "")
                file_path = Path(str(raw_path).replace("\\", os.sep))
                with open(file_path, "r") as data_file:
                    instr_info_json: List[Dict[str, Any]] = json.load(data_file)
                    instr_info_list: List[SCPI_Info] = [
                        SCPI_Info(**item) for item in instr_info_json
                    ]

                for instr_info in instr_info_list:
                    if not self.is_scpi_info_busy(instr_info):
                        instrument_entry: Optional[Instrument_Entry] = (
                            self._custom_instr_handler(instr_info)
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

    def _custom_instr_handler(self, scpi_info: SCPI_Info) -> Optional[Instrument_Entry]:
        config = self._config
        cur_backend: str = self.backend
        instr_extensions = cast(
            List[Tuple[str, type[Instrument]]],
            config.get("instruments_extensions", []),
        )
        newSCPI: Optional[Instrument] = None
        curInstrumentWrapper: Optional[Instrument_Entry] = None
        # Try extension registry first: map IDN substring -> custom instrument class.
        for instr_ext in instr_extensions:
            if instr_ext[0].lower() in scpi_info.idn.lower():
                type_obj = instr_ext[1]
                logger.debug(f"Found extension for {scpi_info.idn}")
                # Always open through VISAAdapter; ASRL options are ignored for non-serial resources.
                newAdapter = pma.VISAAdapter(
                        resource_name=scpi_info.resource_str,
                        visa_library=cur_backend,
                        asrl={'baud_rate': scpi_info.baud_rate}
                    )
                newSCPI = type_obj(adapter=newAdapter, name=scpi_info.name)
                curInstrumentWrapper = Instrument_Entry(
                    data=scpi_info,
                    scpi_instrument=newSCPI,
                )
                break
        # No extension found, use default instrument class
        if newSCPI is None:
            logger.debug("No extension found, using default pymeasure adapter")
            # Respect per-instrument backend override when available.
            bend = scpi_info.backend if scpi_info.backend != "" else cur_backend
            visaAdapter = pma.VISAAdapter(
                resource_name=scpi_info.resource_str,
                visa_library=bend,
                asrl={'baud_rate': scpi_info.baud_rate},
            )
            newSCPI = pmi.generic_types.Instrument(visaAdapter, scpi_info.name)
            # Lock the instrument resource
            curInstrumentWrapper = Instrument_Entry(
                data=scpi_info,
                scpi_instrument=newSCPI,
            )
        return curInstrumentWrapper