from typing import Optional, List
from easy_scpi.scpi_instrument import SCPI_Instrument
from instruments import Instrument_Entry, SCPI_Info
from serial import Serial
from config import Config, comm_mode  # Add this line to import Config and comm_mode
from user_defined.instruments import *

init_properties_types: List[type] = [RaspberrySIM, K2000]


def check_init_properties(scpi_obj: SCPI_Instrument) -> bool:
    return type(scpi_obj) in init_properties_types


def custom_instr_handler(scpi_info: SCPI_Info) -> Optional[Instrument_Entry]:
    newSCPI: SCPI_Instrument = None
    curInstrumentWrapper: Optional[Instrument_Entry] = None
    # Serial auxiliar object
    newComObj: Serial = Serial(scpi_info.port, scpi_info.baud_rate)  # TODO timeout?
    newComObj.close()

    # Fetch from Config.instrumentsExtensions
    for instr_ext in Config.instruments_extensions:
        if instr_ext[0].lower() in scpi_info.idn.lower():
            newSCPI = instr_ext[1](scpi_info)
            break
    # No extension found, use default instrument class
    if newSCPI is None:
        newSCPI = SCPI_Instrument(
            port=scpi_info.port,
            baud_rate=scpi_info.baud_rate,
        )

    if newSCPI is not None and newComObj is not None:
        if Config.communication_mode == comm_mode.pyVisa:
            # Lock the instrument resource
            if check_init_properties(newSCPI):
                newSCPI.init_properties()
            curInstrumentWrapper = Instrument_Entry(
                data=scpi_info,
                scpi_instrument=newSCPI,
            )
        elif Config.communication_mode == comm_mode.serial:
            curInstrumentWrapper = Instrument_Entry(data=scpi_info, com_obj=newComObj)

    return curInstrumentWrapper
