from easy_scpi.scpi_instrument import SCPI_Instrument
from .test_instrument import RaspberrySIM
from instruments import Instrument_Wrapper, SCPI_Info
from serial import Serial


def custom_instr_handler(scpi_info: SCPI_Info) -> Instrument_Wrapper:
    newSCPI: SCPI_Instrument = None
    newComObj: Serial = Serial(scpi_info.port, scpi_info.baud_rate) # TODO timeout?
    newComObj.close()
    if "Raspberry" in scpi_info.idn:
        newSCPI = RaspberrySIM(scpi_info)
    else:
        newSCPI = SCPI_Instrument(
            port=scpi_info.port, baud_rate=scpi_info.baud_rate, scpi_info=scpi_info
        )
    if newSCPI is not None:
        curInstrumentWrapper: Instrument_Wrapper = Instrument_Wrapper(
            idn=scpi_info.idn,
            name=scpi_info.alias,
            scpi_instrument=newSCPI,
            com_obj=newComObj,
        )
    return curInstrumentWrapper
