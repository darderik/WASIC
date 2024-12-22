from dataclasses import dataclass
from typing import List
from easy_scpi import Instrument

# Replace "CustomInstrument" with the name of the instrument class


class CustomInstrumentWrapper:
    """
    A wrapper class for custom instruments that allows dynamic method handling.
    Attributes:
        instrument (Instrument): The linked instrument instance.
        CIWPropertiesHandles (list): A list of method handles associated with the instrument.
    Methods:
        __init__(linkedInstrument: Instrument, MethodsList: list):
            Initializes the CustomInstrumentWrapper with a linked instrument and a list of method handles.
        __init__(MethodsList: list):
            Initializes the CustomInstrumentWrapper with a default CustomInstrument instance and a list of method handles.
    """

    def __init__(self, linked_instrument: Instrument = None):
        """
        Initializes a TestInstrument instance.

        Args:
            linkedInstrument (Instrument): The instrument to be linked. If None, a default CustomInstrument instance is created.
            MethodsList (list): A list of method/property handles as strings.
                                Example: ["self.source.voltage", "self.source.mode", ...]

        Attributes:
            instrument (Instrument): The linked instrument.
            CIWPropertiesHandles (list): The list of method/property handles.
        """
        if linked_instrument is None:
            self.instrument = CustomInstrument()  # TODO add parameters
        else:
            self.instrument = linked_instrument
        # Example: ["self.source.voltage","self.source.mode"...]
        # Each string property is associated to a method of the instrument
        # custom instrument wrapper
        self.ciw_properties_methods: List[PropertiesMethods] = [
            PropertiesMethods("voltage", self.instrument.voltage),
            PropertiesMethods("current", self.instrument.current),
        ]
    


@dataclass
class PropertiesMethods:
    """
    A class to represent properties and their associated methods.

    Attributes:
    ----------
    name : str
        The name of the property.
    property_method : callable
        A method associated with the property.
    """

    name: str
    property_method: callable


class CustomInstrument(Instrument):
    """
    CustomInstrument is a subclass of Instrument that allows for the control of a custom instrument via a specified port.
    
    Attributes:
        voltage (float): The voltage setting of the instrument. This property can be read to get the current voltage level and set to change the voltage level.
    
    Methods:
        __init__(port=None, **resource_params):
            Initializes the CustomInstrument with the specified port and resource parameters.
        voltage:
            Returns the current voltage setting of the instrument.
        voltage(volts):
            Sets the voltage of the instrument to the specified value.
    """
    
    def __init__(self, port=None, **resource_params):
        super().__init__(
            port=port,
            resource_params=resource_params,
        )

        # Add list of relevant properties for the underlying project
        # These properties will be made editable on the web interface
        @property
        def voltage(self):
            """
            Returns the voltage setting
            """
            return self.source.volt.level()  # SOUrce:VOLTage:LEVel?

        @voltage.setter
        def voltage(self, volts):
            """
            Sets the voltage of the instrument
            """
            self.source.volt.level(volts)
