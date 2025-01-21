from typing import List
from enum import Enum


class comm_mode(Enum):
    pyVisa = 0
    serial = 1


class Config:
    # Aliases to look for while searching for instruments
    instrAliasesList: List[str] = ["Raspberry"]
    # If false, instruments will need to be added manually on the Connection class
    communication_mode: comm_mode = comm_mode.pyVisa  # 0 pyVisa, 1 serial
    instrument_config_datapath: str = "data\\instr\\instruments.json"
    data_charts_path: str = "data\\charts"
    # Default timeout for instrument communication
    default_timeout: float = 1.5
