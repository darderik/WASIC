from easy_scpi.scpi_instrument import SCPI_Instrument
from typing import Optional
from .test_instrument import RaspberrySIM
from instruments import Instrument_Entry, SCPI_Info
from serial import Serial
from config import Config, comm_mode  # Add this line to import Config and comm_mode


def custom_instr_handler(scpi_info: SCPI_Info) -> Optional[Instrument_Entry]:
    newSCPI: SCPI_Instrument = None
    curInstrumentWrapper: Optional[Instrument_Entry] = None

    # The user can add new entries of SCPI instruments here
    if "Raspberry" in scpi_info.idn:
        newSCPI = RaspberrySIM(scpi_info)
    else:
        newSCPI = SCPI_Instrument(
            port=scpi_info.port, baud_rate=scpi_info.baud_rate, scpi_info=scpi_info
        )

    newComObj: Serial = Serial(scpi_info.port, scpi_info.baud_rate)  # TODO timeout?
    newComObj.close()
    if newSCPI is not None and newComObj is not None:
        if Config.communication_mode == comm_mode.pyVisa:
            # Lock the instrument resource
            newSCPI.connect()
            if hasattr(newSCPI, "init_properties") and callable(
                getattr(newSCPI, "init_properties")
            ):
                newSCPI.init_properties()
            curInstrumentWrapper = Instrument_Entry(
                data=scpi_info,
                scpi_instrument=newSCPI,
            )
        elif Config.communication_mode == comm_mode.serial:
            curInstrumentWrapper = Instrument_Entry(data=scpi_info, com_obj=newComObj)

    return curInstrumentWrapper
