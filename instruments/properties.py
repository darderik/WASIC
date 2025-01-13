from typing import Callable, Optional
from dataclasses import dataclass


@dataclass
class property_info:
    alias: str
    typecheck: type
    associated_getter: Callable
    associated_setter: Callable
