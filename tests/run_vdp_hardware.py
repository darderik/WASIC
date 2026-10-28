"""Run the registered VDP task on hardware through WASIC Connections.

Explicit script only, excluded from unittest discovery. Defaults match the
saved measurement: 100 uA, 1 V, NPLC 5, autorange, 0.3/0.2 s settling.
"""
import argparse
import logging
import sys
import time
from pathlib import Path
from threading import Event, Timer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from addons.loader import load_addons
from connections import Connections
from tasks import Task
from tasks.chart_io import save_charts_csv
from wasic_api import TaskContext
from addons.tasks.van_der_pauw import relay_routes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--nplc", type=float, default=5)
    parser.add_argument("--samples", type=int, default=1)
    parser.add_argument("--current", type=float, default=.0001)
    parser.add_argument("--settle", type=float, default=.3)
    parser.add_argument("--range", type=float, default=0)
    parser.add_argument("--inspect-routes", action="store_true")
    parser.add_argument("--check-continuity", action="store_true")
    args = parser.parse_args()
    directory = Path("data/diagnostics")
    directory.mkdir(parents=True, exist_ok=True)
    stem = directory / ("wasic_vdp_" + time.strftime("%Y%m%d_%H%M%S"))
    logging.basicConfig(level=logging.DEBUG, filename=str(stem) + ".log",
                        format="%(asctime)s %(name)s %(levelname)s %(message)s")
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    logging.getLogger().addHandler(console)
    registry = load_addons()
    connections = Connections()
    ctx = None
    instruments = {}
    result = {"error": None}
    timer = None
    try:
        # Use the same discovery, factories, verification and role resolution
        # as the app, without replacing adapters or drivers with test doubles.
        for port in ("COM6", "COM5", "COM4"):
            detection = connections._detect_serial_port(port)
            if detection is None:
                raise RuntimeError(f"Cannot discover {port}; close WASIC before testing")
            info = connections._build_serial_info(*detection)
            if info is None or not connections._add_instrument(info):
                raise RuntimeError(f"Cannot connect {port}")
            if port == "COM6":
                source = connections.get_instrument_by_driver("keithley6221").scpi_instrument
                source.disable_source()
                source.source_current = 0
        spec = registry.tasks["van_der_pauw"]
        task = Task.from_spec(spec)
        instruments = task.resolve_instruments()
        parameters = spec.parse_parameters({
            "repetitions": args.repetitions, "nplc": args.nplc,
            "samples_per_polarity": args.samples, "current_A": args.current,
            "compliance_V": 1, "current_settle_s": args.settle,
            "relay_settle_s": .2, "voltage_range_V": args.range,
        })
        result["parameters"] = parameters
        if args.check_continuity:
            source, meter, matrix = (instruments[k] for k in ("source", "meter", "matrix"))
            source.disable_source()
            source.source_current = 0
            source.source_compliance = 1
            source.source_auto_range = True
            source.write(":FORM:SREG ASC")
            result["continuity"] = []
            try:
                for label, hi, lo in [(f"same_contact_{i}", i, i) for i in range(1, 5)] + [("loop_12", 1, 2), ("loop_23", 2, 3)]:
                    source.disable_source()
                    source.source_current = 0
                    time.sleep(.2)
                    matrix.switch_commute_reset_all()
                    matrix.switch_commute_exclusive(f"c{hi}", f"d{lo}", f"a{hi}", f"b{lo}")
                    time.sleep(.2)
                    source.source_current = args.current
                    source.enable_source()
                    time.sleep(1)
                    record = {"label": label, "status": source.ask(":STAT:MEAS:COND?"),
                              "output": source.ask("OUTP?"), "current_setpoint": source.ask(":SOUR:CURR?"),
                              "voltage": float(meter.voltage),
                              "relays": matrix.ask("switch:commute:byte:status?"),
                              "source_errors": source.check_errors(), "meter_errors": meter.check_errors()}
                    result["continuity"].append(record)
                    print(record, flush=True)
                    source.disable_source()
            finally:
                source.disable_source()
                source.source_current = 0
                time.sleep(.2)
                matrix.switch_commute_reset_all()
            return
        if args.inspect_routes:
            source, matrix = instruments["source"], instruments["matrix"]
            source.disable_source()
            source.source_current = 0
            try:
                result["route_states"] = {}
                for name, route in relay_routes(parameters).items():
                    matrix.switch_commute_reset_all()
                    matrix.switch_commute_exclusive(*route)
                    result["route_states"][name] = {
                        "system": matrix.get_system_state(),
                        "bytes": matrix.ask("switch:commute:byte:status?"),
                        "power": matrix.ask("switch:commute:status?"),
                        "log": matrix.get_system_log(),
                    }
                    print(name, result["route_states"][name], flush=True)
            finally:
                matrix.switch_commute_reset_all()
            return
        ctx = TaskContext(instruments, parameters, [], Event())
        timer = Timer(180, ctx.exit_flag.set)
        timer.start()
        started = time.monotonic()
        spec.run(ctx)
        result["elapsed_s"] = time.monotonic() - started
        result["cancelled"] = ctx.exit_flag.is_set()
        source, meter = instruments["source"], instruments["meter"]
        result["final_state"] = {
            "source_output": source.ask("OUTP?"),
            "source_current": source.ask(":SOUR:CURR?"),
            "source_compliance": source.ask(":SOUR:CURR:COMP?"),
            "source_error": source.check_errors(),
            "meter_auto": meter.ask(":SENS:VOLT:CHAN1:RANG:AUTO?"),
            "meter_range": meter.ask(":SENS:VOLT:CHAN1:RANG?"),
            "meter_error": meter.check_errors(),
        }
    except Exception as exc:
        result["error"] = repr(exc)
        logging.exception("Hardware task run failed")
    finally:
        if timer:
            timer.cancel()
        if ctx:
            result["valid_cycles"] = len(ctx.data[2].y_series.processed) if len(ctx.data) == 3 else 0
        # Retry source-off on exceptional exits as well as task cleanup.
        entry = connections.get_instrument_by_driver("keithley6221")
        if entry:
            entry.scpi_instrument.disable_source()
            entry.scpi_instrument.source_current = 0
        for entry in list(connections.instruments_list):
            connections._disconnect_entry(entry)
        connections.instruments_list.clear()
        save_charts_csv(ctx.data if ctx else [], stem.with_suffix(".csv"), metadata=result)
    print(result, flush=True)
    print(f"Saved {stem}.csv, .csv.meta.csv and .log", flush=True)


if __name__ == "__main__":
    main()
