from typing import List

from instruments import property_info
from pymeasure.instruments import Instrument, SCPIMixin


class RPIB(SCPIMixin, Instrument):
	"""
	SCPI driver for the Raspberry Pi fake instrument running over serial.

	The transport adapter is provided by the connection handler.
	"""

	def __init__(self, adapter, name: str = "RPIB", **kwargs) -> None:
		super().__init__(
			adapter=adapter,
			name=name,
			includeSCPI=False,
		)

		self.init_properties()

	def ask(self, command: str) -> str:
		return str(super().ask(command)).strip()

	def opc(self) -> bool:
		return str(self.ask("*OPC?")).strip() == "1"

	def idn(self) -> str:
		return str(self.ask("*IDN?"))

	def init_properties(self) -> None:
		self.properties_list: List[property_info] = [
			property_info("Voltage range (V)", float, self.get_voltage_range, self.set_voltage_range),
			property_info("NPLC", float, self.get_nplc, self.set_nplc),
			property_info("Offset (V)", float, self.get_offset, self.set_offset),
			property_info("Sample count", int, self.get_sample_count, self.set_sample_count),
		]

	def identify(self) -> str:
		return self.idn()

	def reset(self) -> None:
		self.write("*RST")

	def clear_status(self) -> None:
		self.write("*CLS")

	def get_system_error(self) -> str:
		return self.ask("SYST:ERR?")

	def get_system_version(self) -> str:
		return self.ask("SYST:VERS?")

	def get_operation_status(self) -> int:
		return int(float(self.ask("STAT:OPER?")))

	def configure_voltage_dc(self, voltage_range: float) -> None:
		self.write(f"CONF:VOLT:DC {float(voltage_range)}")

	def set_voltage_range(self, voltage_range: float) -> None:
		self.write(f"VOLT:DC:RANG {float(voltage_range)}")

	def get_voltage_range(self) -> float:
		return float(self.ask("VOLT:DC:RANG?"))

	@property
	def voltage_range(self) -> float:
		return self.get_voltage_range()

	@voltage_range.setter
	def voltage_range(self, value: float) -> None:
		self.set_voltage_range(value)

	def set_nplc(self, nplc: float) -> None:
		self.write(f"VOLT:DC:NPLC {float(nplc)}")

	def get_nplc(self) -> float:
		return float(self.ask("VOLT:DC:NPLC?"))

	@property
	def nplc(self) -> float:
		return self.get_nplc()

	@nplc.setter
	def nplc(self, value: float) -> None:
		self.set_nplc(value)

	def set_offset(self, offset: float) -> None:
		self.write(f"VOLT:DC:OFFS {float(offset)}")

	def get_offset(self) -> float:
		return float(self.ask("VOLT:DC:OFFS?"))

	@property
	def offset(self) -> float:
		return self.get_offset()

	@offset.setter
	def offset(self, value: float) -> None:
		self.set_offset(value)

	def measure_voltage_dc(self) -> float:
		return float(self.ask("MEAS:VOLT:DC?"))

	def read_measurement(self) -> float:
		return float(self.ask("READ?"))

	def fetch(self) -> float:
		return float(self.ask("FETCh?"))

	def set_sample_count(self, count: int) -> None:
		self.write(f"SAMP:COUN {int(count)}")

	def get_sample_count(self) -> int:
		return int(float(self.ask("SAMP:COUN?")))

	@property
	def sample_count(self) -> int:
		return self.get_sample_count()

	@sample_count.setter
	def sample_count(self, value: int) -> None:
		self.set_sample_count(value)

	def init_acquisition(self) -> None:
		self.write("INIT")

	def trigger(self) -> None:
		self.write("TRIG")



from wasic_api import InstrumentSpec

PLUGIN = InstrumentSpec(
    id='rpib', name='RPIB', idn_keywords=('rpb', 'Raspberry'),
    factory=lambda adapter, info: RPIB(adapter=adapter, name=info.name),
)
