import json
import logging
import os
import sys
import threading
from dataclasses import asdict
from pathlib import Path
from threading import Lock, Thread
from typing import Any, Optional, cast

import pymeasure.adapters as pma
import pymeasure.instruments as pmi
import pyvisa
from pyvisa.constants import ControlFlow, StopBits
from pymeasure.instruments.instrument import Instrument
from serial.tools.list_ports import comports

from config import Config
from addons.loader import registry
from instruments import Instrument_Entry, SCPI_Info
from .baud_detector import BaudTrialDetector, SerialParamCache, parse_response, parse_stop_bits

logger = logging.getLogger(__name__)

MULTITHREAD_DETECTION = True
SerialDetection = tuple[str, str, int, str, str, str, str]


class Connections:
    _instance = None
    _instrument_lock = threading.Lock()
    _file_lock = threading.Lock()

    instruments_list: list[Instrument_Entry] = []
    backend: str = "@py"

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._config = Config()
        return cls._instance

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------

    def get_instrument(self, keyword: str) -> Optional[Instrument_Entry]:
        keyword = keyword.lower()

        with self._instrument_lock:
            for instrument in self.instruments_list:
                if keyword in instrument.data.idn.lower():
                    return instrument

        logger.warning("No instrument found with keyword: %s", keyword)
        return None

    def get_instrument_by_driver(self, driver_id: str) -> Optional[Instrument_Entry]:
        """Resolve a task requirement by registered driver ID, rejecting ambiguity."""
        with self._instrument_lock:
            matches = [entry for entry in self.instruments_list
                       if (spec := registry.match_instrument(entry.data.idn)) is not None
                       and spec.id == driver_id]
        if len(matches) > 1:
            raise ValueError(f"Multiple instruments match driver {driver_id}")
        return matches[0] if matches else None

    def get_instruments_aliases(self, idn: bool = False) -> list[str]:
        with self._instrument_lock:
            if idn:
                return [instrument.data.idn for instrument in self.instruments_list]

            return [instrument.data.alias for instrument in self.instruments_list]

    def verify_instruments(self) -> None:
        valid_instruments: list[Instrument_Entry] = []

        with self._instrument_lock:
            for instrument in self.instruments_list:
                if self._is_instrument_alive(instrument):
                    valid_instruments.append(instrument)
                else:
                    self._disconnect_entry(instrument)

            self.instruments_list = valid_instruments

    def fetch_all_instruments(
        self,
        curAliasesList: Optional[list[str]] = None,
        clear_list: bool = True,
    ) -> None:
        aliases = curAliasesList or self._config.get("instr_aliases", [])

        with self._instrument_lock:
            if clear_list:
                self._clear_instruments()

            logger.debug("Fetching instruments based on aliases: %s", aliases)

            locked_ports = self._get_locked_ports()
            serial_ports = self._get_available_serial_ports(locked_ports)

            self._discover_visa_instruments(locked_ports)
            self._discover_serial_instruments(serial_ports)

    def save_config(self) -> None:
        with self._file_lock:
            raw_path = self._config.get("instrument_connections_datapath", "")
            file_path = self._normalize_path(raw_path)

            try:
                if not raw_path:
                    raise ValueError("Configuration file path is not set.")

                file_path.parent.mkdir(parents=True, exist_ok=True)

                data = [asdict(instrument.data) for instrument in self.instruments_list]

                with open(file_path, "w", encoding="utf-8") as file:
                    json.dump(data, file, indent=4)

            except Exception as exc:
                logger.error("Failed to save instrument configuration: %s", exc)

    def load_config(self) -> None:
        with self._file_lock:
            try:
                instruments_info = self._read_config_file()

                for info in instruments_info:
                    if self.is_scpi_info_busy(info):
                        continue

                    if not self._add_instrument(info) and "ASRL" in info.resource_str.upper():
                        detection = self._detect_serial_port(info.port)
                        if detection is not None:
                            refreshed = self._build_serial_info(*detection)
                            if refreshed is not None:
                                self._add_instrument(refreshed)

            except FileNotFoundError:
                logger.warning(
                    "Configuration file not found. Fetching instruments from aliases."
                )
                self.fetch_all_instruments(self._config.get("instr_aliases", []))

            except json.JSONDecodeError as exc:
                logger.error("Failed to parse configuration file: %s", exc)
                raise RuntimeError(f"Failed to parse configuration file: {exc}") from exc

            except Exception as exc:
                logger.error("Error loading configuration: %s", exc)
                self.fetch_all_instruments(self._config.get("instr_aliases", []))

    def is_scpi_info_busy(self, instr_info: SCPI_Info) -> bool:
        with self._instrument_lock:
            return instr_info.port in self._get_locked_ports()

    # ---------------------------------------------------------------------
    # Discovery
    # ---------------------------------------------------------------------

    def _discover_visa_instruments(self, locked_ports: list[str]) -> None:
        try:
            # Enumerate only: PyMeasure's helper queries every port and closes
            # the ResourceManager shared with our live VISA adapters.
            manager = pyvisa.ResourceManager(self.backend)
            self._visa_manager = manager
            resources = manager.list_resources()
            logger.debug("VISA instruments found: %s", resources)

            for resource in resources:
                if self._should_skip_visa_resource(resource, locked_ports):
                    continue

                self._process_visa_resource(resource)

        except Exception as exc:
            logger.error("Failed to scan VISA instruments: %s", exc)

    def _discover_serial_instruments(self, ports: list[str]) -> None:
        detections = self._detect_serial_ports(ports)

        for detection in detections:
            info = self._build_serial_info(*detection)

            if info is not None:
                logger.debug("Found serial instrument: %s -> %s", info.alias, info)
                self._add_instrument(info)

    def _detect_serial_ports(self, ports: list[str]) -> list[SerialDetection]:
        if MULTITHREAD_DETECTION:
            return self._detect_serial_ports_parallel(ports)

        detections: list[SerialDetection] = []

        for port in ports:
            detection = self._detect_serial_port(port)

            if detection is not None:
                detections.append(detection)

        logger.debug("Serial detections: %s", detections)
        return detections

    def _detect_serial_ports_parallel(
        self,
        ports: list[str],
    ) -> list[SerialDetection]:
        detections: list[SerialDetection] = []
        detections_lock = Lock()
        threads: list[Thread] = []

        for port in ports:
            thread = Thread(
                target=self._detect_serial_port_worker,
                args=(port, detections, detections_lock),
            )
            thread.start()
            threads.append(thread)

        for thread in threads:
            thread.join()

        logger.debug("Serial detections: %s", detections)
        return detections

    def _detect_serial_port_worker(
        self,
        port: str,
        target: list[SerialDetection],
        target_lock: Lock,
    ) -> None:
        detection = self._detect_serial_port(port)

        if detection is None:
            return

        with target_lock:
            target.append(detection)

    @staticmethod
    def _detect_serial_port(port: str) -> Optional[SerialDetection]:
        # Probe unknown devices with IDN only: a preceding *CLS may require
        # its own handshake, which cannot be assumed for every instrument.
        result = BaudTrialDetector(port=port, clear_on_connect=False).detect()

        if result is None:
            logger.debug("Failed to detect baud rate for port %s", port)
            return None

        logger.debug(
            "Serial detection on port %s: baud=%s idn=%s read=%r write=%r flow=%s",
            port,
            result.baud_rate,
            result.idn,
            result.read_termination,
            result.write_termination,
            result.flow_control,
        )

        return (port, result.idn, result.baud_rate, result.stop_bits.name,
                result.read_termination, result.write_termination, result.flow_control)

    # ---------------------------------------------------------------------
    # Resource processing
    # ---------------------------------------------------------------------

    def _process_visa_resource(self, resource: str) -> None:
        instrument: Optional[Instrument] = None

        try:
            instrument = Instrument(
                adapter=resource,
                visa_library=self.backend,
                name=resource,
            )

            idn = instrument.ask("*IDN?")
            info = self._build_visa_info(resource, idn)

            # USB devices may only allow one open session at a time. Release
            # the discovery connection before the driver opens its own.
            instrument.adapter.close()
            instrument = None

            if info is not None:
                logger.debug("Found VISA instrument: %s -> %s", info.alias, info)
                self._add_instrument(info)

        except Exception as exc:
            logger.error("Failed to create VISA instrument for %s: %s", resource, exc)

        finally:
            self._safe_close(instrument)

    def _build_visa_info(self, resource: str, idn: str) -> Optional[SCPI_Info]:
        spec = registry.match_instrument(idn)
        alias = spec.name if spec else self._config.is_in_instr_aliases(idn)

        if not alias:
            return None

        return SCPI_Info(
            port=resource,
            baud_rate=0,
            idn=idn,
            alias=alias,
            resource_str=resource,
            name=self._name_from_idn(idn),
            backend=self.backend,
        )

    def _build_serial_info(
        self,
        port: str,
        idn: str,
        baud_rate: int,
        stop_bits: str = "one",
        read_termination: str = "\n",
        write_termination: str = "\n",
        flow_control: str = "none",
    ) -> Optional[SCPI_Info]:
        spec = registry.match_instrument(idn)
        alias = spec.name if spec else self._config.is_in_instr_aliases(idn)

        if not alias:
            return None

        return SCPI_Info(
            port=port,
            baud_rate=baud_rate,
            stop_bits=stop_bits,
            read_termination=read_termination,
            write_termination=write_termination,
            flow_control=flow_control,
            idn=idn,
            alias=alias,
            resource_str=self._serial_resource_name(port),
            name=self._name_from_idn(idn),
        )

    def _add_instrument(self, info: SCPI_Info) -> bool:
        entry = self._create_instrument_entry(info)

        if entry is None:
            logger.error("Failed to create Instrument_Entry for %s", info.idn)
            return False

        if not self._is_instrument_alive(entry):
            self._disconnect_entry(entry)
            if "ASRL" in info.resource_str.upper():
                SerialParamCache().forget(info.port)
            logger.warning("Instrument %s did not pass connection verification", info.idn)
            return False

        self.instruments_list.append(entry)
        if "ASRL" in info.resource_str.upper():
            SerialParamCache().save_success(info.port, info.baud_rate,
                                           parse_stop_bits(info.stop_bits),
                                           info.read_termination, info.write_termination,
                                           info.flow_control)
        logger.info("Successfully added instrument: %s", info.idn)
        return True

    # ---------------------------------------------------------------------
    # Instrument creation
    # ---------------------------------------------------------------------

    def _create_instrument_entry(
        self,
        info: SCPI_Info,
    ) -> Optional[Instrument_Entry]:
        try:
            spec = registry.match_instrument(info.idn)
            custom_class = self._find_custom_instrument_class(info.idn) if spec is None else None
            if spec is not None:
                adapter = self._create_visa_adapter(info)
                try:
                    instrument = spec.factory(adapter, info)
                except Exception:
                    adapter.close()
                    raise
            elif custom_class is not None:
                instrument = self._create_custom_instrument(info, custom_class)
            else:
                instrument = self._create_default_instrument(info)

            return Instrument_Entry(
                data=info,
                scpi_instrument=instrument,
            )

        except Exception as exc:
            logger.error("Failed to instantiate instrument %s: %s", info.idn, exc)
            return None

    def _find_custom_instrument_class(
        self,
        idn: str,
    ) -> Optional[type[Instrument]]:
        extensions = cast(
            list[tuple[str, type[Instrument]]],
            self._config.get("instruments_extensions", []),
        )

        for keyword, instrument_class in extensions:
            if keyword.lower() in idn.lower():
                logger.debug("Found extension for %s", idn)
                return instrument_class

        return None

    def _create_custom_instrument(
        self,
        info: SCPI_Info,
        instrument_class: type[Instrument],
    ) -> Instrument:
        adapter = self._create_visa_adapter(info)
        return instrument_class(adapter=adapter, name=info.name)

    def _create_default_instrument(self, info: SCPI_Info) -> Instrument:
        adapter = self._create_visa_adapter(info)
        return pmi.generic_types.Instrument(adapter, info.name)

    def _create_visa_adapter(self, info: SCPI_Info) -> pma.VISAAdapter:
        backend = info.backend or self.backend
        # New serial sessions already use 8N1 and no flow control. Avoid
        # redundant port reconfiguration, which can reset USB CDC firmware.
        serial_options: dict[str, Any] = {
            "baud_rate": info.baud_rate,
            "read_termination": info.read_termination,
            "write_termination": info.write_termination,
        }
        stop_bits = parse_stop_bits(info.stop_bits)
        if stop_bits != StopBits.one:
            serial_options["stop_bits"] = stop_bits
        flow_control = ControlFlow[info.flow_control]
        if flow_control != ControlFlow.none:
            serial_options["flow_control"] = flow_control

        return pma.VISAAdapter(
            resource_name=info.resource_str,
            visa_library=backend,
            # VISA timeouts are in milliseconds; allow high-NPLC acquisitions.
            timeout=30000,
            asrl=serial_options,
        )

    # ---------------------------------------------------------------------
    # List / connection utilities
    # ---------------------------------------------------------------------

    def _clear_instruments(self) -> None:
        for instrument in list(self.instruments_list):
            self._disconnect_entry(instrument)

        self.instruments_list.clear()

    def _disconnect_entry(self, entry: Instrument_Entry) -> None:
        try:
            self._disconnect_instrument(entry.scpi_instrument)
            logger.debug("Disconnected instrument: %s", entry.data.idn)
        except Exception as exc:
            logger.error("Failed to disconnect %s: %s", entry.data.idn, exc)

    @staticmethod
    def _disconnect_instrument(instrument: Instrument) -> None:
        try:
            instrument.adapter.connection.close()
        except Exception:
            instrument.adapter.close()

    @staticmethod
    def _safe_close(instrument: Optional[Instrument]) -> None:
        if instrument is None:
            return

        try:
            instrument.adapter.close()
        except Exception:
            pass

    @staticmethod
    def _is_instrument_alive(entry: Instrument_Entry) -> bool:
        try:
            response = parse_response(entry.scpi_instrument.ask("*IDN?"))
            return response is not None and response == parse_response(entry.data.idn)
        except Exception as exc:
            logger.warning("Failed to verify instrument %s: %s", entry.data.idn, exc)
            return False

    def _get_locked_ports(self) -> list[str]:
        locked_ports: list[str] = []

        for instrument in self.instruments_list:
            locked_ports.extend([instrument.data.port, instrument.data.resource_str])
            resource = instrument.scpi_instrument.adapter

            if isinstance(resource, pma.SerialAdapter):
                locked_ports.append(str(resource.connection.port))

            elif isinstance(resource, pma.VISAAdapter):
                locked_ports.append(str(resource.resource_name))

        return locked_ports

    @staticmethod
    def _get_available_serial_ports(locked_ports: list[str]) -> list[str]:
        ports = comports()

        if sys.platform.startswith("linux"):
            candidates = [
                port.device
                for port in ports
                if port.device.startswith(("/dev/ttyUSB", "/dev/ttyACM"))
            ]
        else:
            candidates = [port.name for port in ports]

        return [port for port in candidates if port not in locked_ports]

    @staticmethod
    def _should_skip_visa_resource(resource: str, locked_ports: list[str]) -> bool:
        return resource in locked_ports or "ASRL" in resource

    # ---------------------------------------------------------------------
    # Config utilities
    # ---------------------------------------------------------------------

    def _read_config_file(self) -> list[SCPI_Info]:
        raw_path = self._config.get("instrument_connections_datapath", "")
        file_path = self._normalize_path(raw_path)

        with open(file_path, "r", encoding="utf-8") as file:
            raw_items = json.load(file)

        return [SCPI_Info(**item) for item in raw_items]

    @staticmethod
    def _normalize_path(path: str) -> Path:
        return Path(str(path).replace("\\", os.sep))

    # ---------------------------------------------------------------------
    # Formatting helpers
    # ---------------------------------------------------------------------

    @staticmethod
    def _serial_resource_name(port: str) -> str:
        port_number = "".join(filter(str.isdigit, port))
        return f"ASRL{port_number}::INSTR"

    @staticmethod
    def _name_from_idn(idn: str) -> str:
        parts = idn.split(",")

        if len(parts) >= 2:
            return f"{parts[0]} {parts[1]}"

        return idn
