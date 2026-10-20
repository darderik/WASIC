"""Hardware diagnostic: source off by default; --active tests at 100 uA/1 V.

Run as a script, never during test discovery. Uses the existing COM4/5/6 setup.
"""
import json
import math
import sys
import time
from pathlib import Path
from threading import Event

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from connections import Connections
from instruments import SCPI_Info
from pymeasure.instruments.keithley import Keithley2182, Keithley6221
from addons.instruments.RelayMatrix import RelayMatrix
from addons.tasks.van_der_pauw import PLUGIN, relay_routes, _read_voltage, _check_source, _cleanup, _Compliance
from wasic_api import TaskContext


def main():
    parameters = PLUGIN.parse_parameters({})
    routes = relay_routes(parameters)
    output = Path("data/diagnostics")
    output.mkdir(parents=True, exist_ok=True)
    path = output / ("vdp_" + time.strftime("%Y%m%d_%H%M%S") + ".jsonl")
    cache = json.loads(Path("connections/wasic_serial_cache.tmp").read_text())
    adapters = []
    source = meter = matrix = None
    with path.open("w", encoding="utf-8") as log:
        def emit(**record):
            record["time"] = time.strftime("%Y-%m-%d %H:%M:%S")
            line = json.dumps(record)
            log.write(line + "\n")
            log.flush()
            print(line, flush=True)

        def connect(port, cls, expected):
            options = {k: v for k, v in cache[port].items() if k != "ts"}
            info = SCPI_Info(port=port, resource_str=f"ASRL{port[3:]}::INSTR", **options)
            adapter = Connections()._create_visa_adapter(info)
            adapters.append(adapter)
            instrument = cls(adapter, name=port)
            identity = instrument.ask("*IDN?")
            if expected not in identity.upper():
                raise RuntimeError(f"Unexpected instrument on {port}: {identity}")
            emit(port=port, identity=identity, timeout_ms=adapter.connection.timeout)
            return instrument

        try:
            source = connect("COM6", Keithley6221, "MODEL 6221")
            source.disable_source()
            source.source_current = 0
            meter = connect("COM5", Keithley2182, "MODEL 2182")
            matrix = connect("COM4", RelayMatrix, "RELAY MATRIX")
            def state():
                return {key: meter.ask(cmd) for key, cmd in {
                    "auto": ":SENS:VOLT:CHAN1:RANG:AUTO?",
                    "range": ":SENS:VOLT:CHAN1:RANG?",
                    "nplc": ":SENS:VOLT:NPLC?",
                    "error": "SYST:ERR?",
                }.items()}
            emit(stage="initial", meter=state())
            source.reset()
            source.disable_source()
            source.source_current = 0
            source.source_compliance = 1.0
            source.source_auto_range = True
            source.output_low_grounded = False
            source.write(":FORM:SREG ASC")
            meter.reset()
            meter.write(":INIT:CONT OFF")
            meter.write(":ABOR")
            if meter.ask("*OPC?").strip() != "1":
                raise RuntimeError("Meter reset did not complete")
            meter.active_channel = 1
            meter.channel_function = "voltage"
            meter.voltage_nplc = 5
            meter.auto_zero_enabled = True
            meter.ch_1.voltage_offset_enabled = False
            meter.ch_1.voltage_range_auto_enabled = True
            meter.trigger_immediately()
            meter.trigger_count = 1
            meter.write(":SAMP:COUN 1")
            if meter.ask("*OPC?").strip() != "1":
                raise RuntimeError("Meter configuration did not complete")
            emit(stage="configured", meter=state())
            if "--verify-task" in sys.argv:
                ctx = TaskContext({"source": source, "meter": meter, "matrix": matrix},
                                  parameters, [], Event())
                for name, route in routes.items():
                    matrix.switch_commute_reset_all()
                    time.sleep(.2)
                    matrix.switch_commute_exclusive(*route)
                    time.sleep(.2)
                    record = {"positive_V": [], "negative_V": []}
                    for index in range(6):
                        _read_voltage(ctx, source, meter, route, record, "positive_V", parameters)
                        emit(stage="task_helper_source_off", route=name, index=index,
                             voltage=record["positive_V"][-1])
                    emit(stage="task_helper_source_off", route=name, record=record, meter=state())
                return
            if "--active" not in sys.argv:
                for stage, settle, fixed in (("passive_auto", .2, False), ("passive_auto_wait1s", 1., False), ("passive_fixed100mV", .2, True)):
                    meter.ch_1.voltage_range = .1 if fixed else 100
                    meter.ch_1.voltage_range_auto_enabled = not fixed
                    for cycle in range(3):
                        for name, route in routes.items():
                            matrix.switch_commute_reset_all()
                            time.sleep(.2)
                            matrix.switch_commute_exclusive(*route)
                            time.sleep(settle)
                            for index in range(4):
                                started = time.monotonic()
                                voltage = float(meter.voltage)
                                emit(stage=stage, cycle=cycle, route=name, index=index,
                                     voltage=voltage, read_s=time.monotonic()-started, meter=state())
                meter.ch_1.voltage_range_auto_enabled = True
                return
            for stage, settle, fixed in (("baseline", .3, False), ("settle_1s", 1., False), ("fixed_100mV", .3, True)):
                if fixed:
                    meter.ch_1.voltage_range = .1
                else:
                    meter.ch_1.voltage_range_auto_enabled = True
                emit(stage=stage, meter=state())
                for cycle in range(1, 9):
                    for name, route in routes.items():
                        source.disable_source()
                        source.source_current = 0
                        time.sleep(.2)
                        matrix.switch_commute_reset_all()
                        time.sleep(.2)
                        matrix.switch_commute_exclusive(*route)
                        time.sleep(.2)
                        for sign in (1, -1):
                            source.source_current = sign * .0001
                            source.enable_source()
                            time.sleep(settle)
                            try:
                                _check_source(source, current=sign * .0001, compliance=1, route=route)
                            except _Compliance as exc:
                                emit(stage=stage, event="initial_compliance", detail=str(exc))
                                time.sleep(1)
                                _check_source(source, current=sign * .0001, compliance=1, route=route)
                            started = time.monotonic()
                            voltage = float(meter.voltage)
                            emit(stage=stage, cycle=cycle, route=name, sign=sign,
                                 voltage=voltage, read_s=time.monotonic()-started)
                            if not math.isfinite(voltage) or abs(voltage) >= 1e30:
                                emit(stage=stage, event="overflow", meter=state())
                                for retry in range(1, 4):
                                    time.sleep(.5)
                                    _check_source(source, current=sign * .0001, compliance=1, route=route)
                                    voltage = float(meter.voltage)
                                    emit(stage=stage, event="retry", retry=retry, voltage=voltage)
                                    if math.isfinite(voltage) and abs(voltage) < 1e30:
                                        break
                            _check_source(source, current=sign * .0001, compliance=1, route=route)
                            source.disable_source()
                    emit(stage=stage, completed_cycle=cycle)
            meter.ch_1.voltage_range_auto_enabled = True
            emit(stage="final", meter=state())
        finally:
            try:
                if source is not None and matrix is not None:
                    _cleanup(source, matrix, .2)
                    emit(event="cleanup", source_off=True, relays_open=True)
                elif source is not None:
                    source.disable_source()
                    source.source_current = 0
            finally:
                try:
                    if meter is not None:
                        meter.ch_1.voltage_range_auto_enabled = True
                        emit(event="meter_restored", auto=meter.ch_1.voltage_range_auto_enabled)
                finally:
                    for adapter in reversed(adapters):
                        adapter.close()
    print(f"Saved {path}", flush=True)


if __name__ == "__main__":
    main()
