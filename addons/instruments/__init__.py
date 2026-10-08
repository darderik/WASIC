from .RelayMatrix import RelayMatrix
from .TBS1052C import TBS1052C
from .RPIB import RPIB
from pymeasure.instruments.keithley import Keithley2000

INSTRUMENT_REGISTRY: dict[str, tuple[str, type]] = {
	"RelayMatrix": ("Relay Matrix", RelayMatrix),
	"TBS1052C": ("TBS1052C", TBS1052C),
	"RPIB": ("rpb", RPIB),
    "Keithley2000": ("Model 2000", Keithley2000),
}


__all__ = [
	"INSTRUMENT_REGISTRY",
]




