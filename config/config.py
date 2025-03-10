from typing import List
from enum import Enum
from threading import RLock
import json

default_config = {
    "instr_aliases": ["Raspberry", "Model 2000", "Relay Matrix"],
    "communication_mode": "pyvisa",
    "instrument_connections_datapath": "data\\instr\\instruments.json",
    "data_charts_path": "data\\charts",
    "default_timeout": 0.5,
    "init_properties_types": ["NV34420", "K2000", "RaspberrySIM"],
}


class Config:
    _lock = RLock()
    _instance = None
    _data: dict = {}

    def __new__(cls, config_path="config.json"):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._config_path = config_path
                cls._instance.load_config()
                cls._instance._data["instruments_extensions"] = (
                    []
                )  # no need to add to json
        return cls._instance

    def load_config(self):
        config_path = self._config_path
        try:
            with open(config_path, "r") as file:
                self._data = json.load(file)
        except FileNotFoundError:
            # Create file with default values
            with open(config_path, "w") as file:
                json.dump(default_config, file, indent=4)
            self._data = default_config
        except json.JSONDecodeError:
            self._data = default_config
            # TODO: Log error decoding
            pass

    def add_instrument_extension(self, instr_extension: tuple[str, type]):
        """
        Adds an instrument extension to the configuration.

        Args:
            instr_extension (Any): The instrument extension to add.
        """
        self._data["instruments_extensions"].append(instr_extension)

    def get(self, key, default=None):
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
        return self._data.get(key, default)
