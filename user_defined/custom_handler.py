from typing import Optional, List
from easy_scpi.scpi_instrument import SCPI_Instrument
from instruments import Instrument_Entry, SCPI_Info
from serial import Serial
from config import Config  # Add this line to import Config and comm_mode
from user_defined.instruments import *
import logging

config: Config = Config()
logger = logging.getLogger(__name__)


def check_init_properties(scpi_obj: SCPI_Instrument) -> bool:
    init_properties_types: List[str] = config.get("init_properties_types", [])
    return type(scpi_obj) in init_properties_types


def custom_instr_handler(scpi_info: SCPI_Info) -> Optional[Instrument_Entry]:
    instr_extensions: List[tuple[str, type]] = config.get("instruments_extensions", [])
    newSCPI: Optional[SCPI_Instrument] = None
    curInstrumentWrapper: Optional[Instrument_Entry] = None

    # Fetch from config singleton
    for instr_ext in instr_extensions:
        if instr_ext[0].lower() in scpi_info.idn.lower():
            logger.debug(f"Found extension for {scpi_info.idn}")
            newSCPI = instr_ext[1](scpi_info)
            break
    # No extension found, use default instrument class
    if newSCPI is None:
        logger.debug("No extension found, using default SCPI_Instrument")
        newSCPI = SCPI_Instrument(
            port=scpi_info.port,
            baud_rate=scpi_info.baud_rate,
        )

    if newSCPI is not None:
        if not newSCPI.connected:
            newSCPI.connect()
        # Lock the instrument resource
        curInstrumentWrapper = Instrument_Entry(
            data=scpi_info,
            scpi_instrument=newSCPI,
        )
    return curInstrumentWrapper
