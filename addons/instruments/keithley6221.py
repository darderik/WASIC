"""WASIC discovery for the PyMeasure Keithley 6221 driver."""
from pymeasure.instruments.keithley import Keithley6221
from wasic_api import InstrumentSpec

PLUGIN = InstrumentSpec(
    id="keithley6221", name="Keithley 6221", idn_keywords=("Model 6221",),
    factory=lambda adapter, info: Keithley6221(adapter=adapter, name=info.name),
)
