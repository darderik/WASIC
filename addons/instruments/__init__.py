from .RelayMatrix import RelayMatrix
from .TBS1052C import TBS1052C
from .RPIB import RPIB

INSTRUMENT_REGISTRY: dict[str, tuple[str, type]] = {
	"RelayMatrix": ("Relay Matrix", RelayMatrix),
	"TBS1052C": ("TBS1052C", TBS1052C),
	"RPIB": ("rpb", RPIB),
}


__all__ = [
	"INSTRUMENT_REGISTRY",
]




