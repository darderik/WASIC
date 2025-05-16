from connections import Connections
from addons.instruments import TDS2012C, RelayMatrix, TBS1052C
from addons.tasks import Tasks


def test_function():
    Connections().fetch_all_instruments()
    Tasks().run_task("RM Transient 2012_C")


def test_main():
    Connections().fetch_all_instruments()
    # Get instrument tbs 1052C
    scope_entry = Connections().get_instrument("tds 2012C")
    relay_matrix: RelayMatrix = (
        Connections().get_instrument("Relay Matrix").scpi_instrument
    )
    scope: TDS2012C = tbs.scpi_instrument
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
    relay_matrix.switch_commute_reset_all()
    relay_matrix.switch_commute_exclusive("a1")

    # try to break connection (stability test)loop it
    # use queries and write all
    for i in range(2000):
        # Rise sequence
        # Set 25us for rise sequence
        scope.time_scale = 25e-6
        relay_matrix.opc()
        scope.single()
        # NCS trigger
        relay_matrix.switch_commute_exclusive("a2")
        relay_matrix.opc()
        scope.wait()
        t_rise, V_rise = scope.get_waveform(points=points)
        scope.acquire_toggle(False)
        scope.wait()
        # Set 1ms for fall sequence
        scope.time_scale = 1e-3
        scope.horizontal_position(2.3e-3)
        # Arm trigger
        scope.single()
        # NCS trigger
        relay_matrix.switch_commute_exclusive("a1")
        relay_matrix.opc()
        scope.wait()
        t_fall, V_fall = scope.get_waveform(points=points)


if __name__ == "__main__":
    test_main()
