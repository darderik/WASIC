from typing import List, Any, TypeVar, Optional, overload
from enum import Enum
from threading import RLock
import json
import logging

T = TypeVar("T")

default_config = {
    "instr_aliases": ["Raspberry", "Model 2000", "Relay Matrix"],
    "instrument_connections_datapath": "data/instr/instruments.json",
    "data_charts_path": "data/charts",
    "data_charts_relative_bkps": "backups",
    "backup_switch": True,
    "backup_schedule": 120,
    "default_timeout": 0.5,
    "log_level": "DEBUG",
}

# In instr_aliases one shall add keyword to look for while parsing the idn string
logger = logging.getLogger(__name__)


class Config:
    _lock = RLock()
    _instance = None
    _data: dict[str, Any] = {}

    def __new__(cls, config_path: str = "config.json") -> "Config":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._config_path = config_path
                cls._instance._registry_loaded = False
                cls._instance.load_config()
                cls._instance._data["instruments_extensions"] = (
                    []
                )  # no need to add to json
                cls._instance._load_instrument_registry()
        return cls._instance

    def _load_instrument_registry(self) -> None:
        """Populate in-memory instruments_extensions from addon registry."""
        if self._registry_loaded:
            return

        try:
            from addons.instruments import INSTRUMENT_REGISTRY
        except (ImportError, AttributeError):
            return

        for display_name, instrument_type in INSTRUMENT_REGISTRY.values():
            self.add_instrument_extension((display_name, instrument_type))
        self._registry_loaded = True

    def load_config(self):
        config_path = self._config_path
        try:
            with open(config_path, "r") as file:
                self._data = json.load(file)
        except FileNotFoundError:
            logger.warning(
                f"Configuration file not found at {config_path}. Creating..."
            )
            # Create file with default values
            with open(config_path, "w") as file:
                json.dump(default_config, file, indent=4)
            self._data = default_config
        except json.JSONDecodeError:
            logger.error(
                f"Error decoding configuration file at {config_path}. Using default configuration."
            )
            self._data = default_config
            
    def is_in_instr_aliases(self, idn_string: str) -> Optional[str]:
        """
        Checks if any of the instrument aliases are present in the given IDN string.

        Args:
            idn_string (str): The IDN string to check against the instrument aliases.
        Returns:
            Optional[str]: The matching alias if found, otherwise None.
        """
        for alias in self.get("instr_aliases", []):
            if alias in idn_string:
                return alias
        return None
    def add_instrument_extension(self, instr_extension: tuple[str, type]):
        """
        Adds an instrument extension to the configuration.

        Args:
            instr_extension (Any): The instrument extension to add.
        """
        logger.debug(f"Adding instrument extension: {instr_extension}")
        existing = self._data.get("instruments_extensions", [])
        if instr_extension not in existing:
            existing.append(instr_extension)
            self._data["instruments_extensions"] = existing

    @overload
    def get(self, key: str) -> Any:
        ...

    @overload
    def get(self, key: str, default: T) -> T:
        ...

    def get(self, key: str, default: Any = None) -> Any:
        """
        Retrieves the value for the specified configuration key.

        Args:
            key (str): The configuration key to retrieve.
            default (Any): The default value to return if the key is not found.

        Returns:
            Any: The value associated with the specified key, or the default value if the key is not found.

        Keys in default_config:
            - instr_aliases (List[str]): List of instrument aliases.
            - communication_mode (str): Communication mode, either "pyvisa" or "serial".
            - instrument_connections_datapath (str): Path to the JSON file containing instrument connections.
            - data_charts_path (str): Path to the directory for data charts.
            - default_timeout (float): Default timeout value in seconds.
            - instruments_extensions (List[Any]): List of instrument extensions.
        """
        if default is None:
            default = default_config.get(key, None)
        if key == "instruments_extensions" and not self._registry_loaded:
            self._load_instrument_registry()
        return_val = self._data.get(key, default)
        if key not in self._data:
            logger.warning(
                f"Key {key} not found in configuration. Using default value: {default}"
            )
        return return_val
