from connections import Connections
from addons.instruments import TDS2012, RelayMatrix, TBS1052C
from addons.tasks import Tasks


def test_function():
    Connections().fetch_all_instruments()
    Tasks().run_task("RM Transient 1052C")


def test_main():
    print("WASIC TEST Testing Connections and Tasks")
    # Create a Connections object
    conn_object = Connections()
    conn_object.fetch_all_instruments()

    # Fetch instr
    TBS_wrap = conn_object.get_instrument("TBS1052")
    if TBS_wrap is None:
        print("Error: Instrument 'TBS 1052' not found.")
        return
    scope: TBS1052C = TBS_wrap.scpi_instrument
    # Fetch all instruments

    points: int = 2000
    # Scope setup
    # Setup trigger with fall detection
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

    # Sync with WAI and OPC
    scope.wait()
    scope.opc()

    while True:
        # Rise sequence
        # Set 25us for rise sequence
        scope.time_scale = 25e-6
        scope.opc()
        scope.single()
        # NCS trigger
        scope.wait()
        scope.opc()
        scope.acquire_toggle(False)
        scope.wait()
        scope.opc()
        # Set 1ms for fall sequence
        scope.time_scale = 1e-3
        scope.horizontal_position(2.3e-3)


if __name__ == "__main__":
    test_main()
