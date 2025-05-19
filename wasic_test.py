from connections import Connections
from addons.instruments import TDS2012C, RelayMatrix, TBS1052C
from addons.tasks import Tasks
import logging
from config import Config
import os


def test_function():
    Connections().fetch_all_instruments()
    Tasks().run_task("RM Transient 2012_C")


def test_main():
    file_handler = logging.FileHandler(os.path.join("data", "wasic.log"), mode="w")
    stream_handler = logging.StreamHandler()
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=Config().get("log_level", "NOTSET"),
        handlers=[file_handler, stream_handler],
    )
    logging.basicConfig(
        level=logging.DEBUG,
    )
    Connections().fetch_all_instruments()
    # Get instrument tbs 1052C
    relay_entry = Connections().get_instrument("Relay Matrix")
    relay_scpi: RelayMatrix = relay_entry.scpi_instrument
    for _ in range(500):
        relay_scpi.id
        relay_scpi.switch_commute("f5")
        relay_scpi.opc()
        relay_scpi.id
        relay_scpi.opc()
        relay_scpi.id
        relay_scpi.opc()
        relay_scpi.id
        relay_scpi.opc()
        for _ in range(1000):
            relay_scpi.id
            relay_scpi.opc()
            relay_scpi.switch_commute("f5")
        relay_scpi.opc()
        relay_scpi.switch_commute_exclusive("d1")
        relay_scpi.switch_commute_reset_all()
        for _ in range(10000):
            relay_scpi.opc()
        for _ in range(10000):
            relay_scpi.switch_commute("f5")
            relay_scpi.opc()
            relay_scpi.id
            relay_scpi.opc()


if __name__ == "__main__":
    test_main()
