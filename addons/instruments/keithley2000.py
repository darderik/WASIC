"""Example adapter for an existing third-party driver."""
from pymeasure.instruments.keithley import Keithley2000
from wasic_api import InstrumentSpec

PLUGIN = InstrumentSpec(
    id="keithley2000", name="Keithley 2000", idn_keywords=("Model 2000",),
    factory=lambda adapter, info: Keithley2000(adapter=adapter, name=info.name),
)
