"""WASIC discovery for PyMeasure's 2182 driver, including the 2182A."""
from pymeasure.instruments.keithley import Keithley2182
from wasic_api import InstrumentSpec

PLUGIN = InstrumentSpec(
    id="keithley2182", name="Keithley 2182 / 2182A", idn_keywords=("Model 2182",),
    factory=lambda adapter, info: Keithley2182(adapter=adapter, name=info.name),
)
