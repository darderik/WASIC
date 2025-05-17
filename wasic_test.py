from connections import Connections
from addons.instruments import TDS2012C, RelayMatrix, TBS1052C
from addons.tasks import Tasks
import logging
from config import Config
import os


def test_function():
    Connections().fetch_all_instruments()
    Tasks().run_task("Test Task")


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
    scope_entry = Connections().get_instrument("tds 2012C")
    scope: TDS2012C = scope_entry.scpi_instrument
    rel_matrix: RelayMatrix = relay_entry.scpi_instrument
    points = 2000
    scope.trigger_config(
        source=2,
        slope="RISE",
        level=1,
        mode="normal",
    )
    # Hard coded positioning
    scope.vertical_position(1, -3)
    scope.vertical_position(2, 1)
    scope.vertical_scale(1, 1)
    scope.vertical_scale(2, 1)
    scope.horizontal_position(3e-3)
    # Data setup
    scope.acquire_toggle(False)
    scope.initialize_waveform_settings(
        points=points,
    )
    # Reset and ground (A1)

    # try to break connection (stability test)loop it
    # use queries and write all
    for _ in range(50):  # Perform 50 connectivity checks
        # Check scope connection
        scope_idn = scope.query("*IDN?")
        print(f"Scope IDN: {scope_idn}")
        # Perform multiple queries and writes for the scope
        scope.write(":MEASUREMENT:IMMED:SOURCE CH1")
        print("Set measurement source to CH1.")
        scope.write(":MEASUREMENT:IMMED:TYPE PK2PK")
        print("Set measurement type to Peak-to-Peak.")
        pk2pk_value = scope.query(":MEASUREMENT:IMMED:VALUE?")
        print(f"Peak-to-Peak Value: {pk2pk_value}")
        scope.write(":MEASUREMENT:IMMED:SOURCE CH2")
        print("Set measurement source to CH2.")
        rms_value = scope.query(":MEASUREMENT:IMMED:VALUE?")
        print(f"RMS Value: {rms_value}")
        # Check relay matrix connection
        relay_idn = rel_matrix.query("*IDN?")
        print(f"Relay Matrix IDN: {relay_idn}")
        # Toggle relay matrix state
        rel_matrix.switch_commute_exclusive("a1")
        rel_matrix.switch_commute_exclusive("a2")
        print("Relay matrix toggled successfully.")


if __name__ == "__main__":
    test_main()
