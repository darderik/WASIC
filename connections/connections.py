from typing import List, Tuple
from serial.tools.list_ports import comports
from serial import Serial
from easy_scpi.scpi_instrument import SCPI_Instrument
from config import Config
from connections.utilities import baudRateDetector

class Connections:
    """
    A class to manage connections to SCPI instruments.
    Attributes:
    -----------
    Instruments : List[SCPI_Instrument]
        A list to store connected SCPI instruments.
    Methods:
    --------
    fetchInstruments():
        Class method to fetch and store all SCPI instruments based on configuration.
    findInstrument(cls, matchingName: str) -> Tuple[str, int]:
        Static method to find a specific instrument by its name.
    findAllInstruments(cls, curList: List[str]) -> List[SCPI_Instrument]:
        Static method to find all instruments from a given list of names.
    """
    Instruments: List[SCPI_Instrument] = []

    @classmethod
    def fetchInstruments(cls):
        cls.Instruments = cls.findAllInstruments(cls, Config.instrAliasesList)

    @staticmethod
    def findInstrument(cls,matchingName: str) -> Tuple[str, int]:
        toReturn: Tuple[str, int] = None

        # Obtain all ports
        ports: List[comports] = comports()

        # Find BR for each port
        for port, desc, hwid in sorted(ports):
            detected_BR: int = baudRateDetector.detect_baud_rate(port)
            if detected_BR is not None:
                # Found suitable baud rate
                with Serial(port, detected_BR) as curSerial:
                    # Send IDN query
                    curSerial.write(f"*IDN?{Config.charTerminator}".encode(ascii))
                    curIdnOput: str = curSerial.read(curSerial.in_waiting).decode()
                    curSerial.close()
                    # Check if the name matches
                    if matchingName in curIdnOput:
                        toReturn = (curSerial.port, detected_BR)
        return toReturn

    @staticmethod
    def findAllInstruments(cls,curList: List[str]) -> List[SCPI_Instrument]:
        SCPI_Instruments: List[SCPI_Instrument] = []
        for instr in curList:
            curSerial: Tuple[str, int] = cls.findInstrument(cls,instr)
            if curSerial is not None:
                SCPI_Instruments.append(
                    SCPI_Instrument(port=curSerial[0], baud_rate=str(curSerial[1]))
                )
        return SCPI_Instruments
