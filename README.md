# WASIC

**Web Application for SCPI Instrument Control** — A Python framework for managing and controlling SCPI-compatible instruments (serial, USB, and TCP) through a web-based interface built with Streamlit.

![wasic](https://github.com/user-attachments/assets/da8c8e13-4d24-4402-8154-fd600ddf6cf3)

## Features

- 🔌 **Multi-protocol support**: Serial (RS-232), USB, and TCP/IP instrument connections
- 📊 **Data acquisition & visualization**: Real-time plotting and data management with automatic backups
- 🌐 **Web interface**: Intuitive Streamlit-based UI for instrument control and task management
- 📈 **Task automation**: Run custom measurement routines and data processing pipelines
- 🔧 **Extensible architecture**: Easy to add custom instrument drivers and measurement tasks
- ✅ **Cross-platform**: Works on Windows, Linux (Debian/Ubuntu), and macOS

## Table of Contents
- [Quick Start](#quick-start)
- [Requirements](#requirements)
- [Installation](#installation)
  - [Windows](#windows)
  - [Linux (Debian/Ubuntu)](#linux-debianubuntu)
- [Configuration](#configuration)
- [Usage](#usage)
- [Project Structure](#project-structure)
- [Extending WASIC](#extending-wasic)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

## Quick Start

```bash
# Clone and setup (Windows - PowerShell)
git clone https://github.com/darderik/WASIC.git
cd WASIC
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py

# Or Linux/macOS
git clone https://github.com/darderik/WASIC.git
cd WASIC
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
```

The application will open on `http://localhost:8501` in your browser.

## Requirements

- **Python**: 3.13 or later
- **Git**: For cloning the repository
- **OS-specific**:
  - Windows: Chocolatey (optional, for automated setup)
  - Linux: apt package manager
  - macOS: Homebrew (optional)

### Platform Notes

**Windows**: Remove USBTMC drivers for USB instruments and use WinUSB instead. See [pyvisa-py documentation](https://pyvisa.readthedocs.io/projects/pyvisa-py/en/latest/installation.html#usb-resources-usb-instr-raw) for details.

**Linux**: Ensure you have proper permissions for serial port access:
```bash
sudo usermod -a -G dialout $USER
# Log out and log back in for changes to take effect
```

## Installation

### Windows

#### Option 1: Automated with Chocolatey (Recommended)

1. **Install Chocolatey** (if not already installed):
   
   Open PowerShell as Administrator and run:
   
   ```powershell
   Set-ExecutionPolicy Bypass -Scope Process -Force; `
   [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12; `
   iex ((New-Object System.Net.WebClient).DownloadString('https://chocolatey.org/install.ps1'))
   ```

2. **Install dependencies**:
   
   ```powershell
   choco install git python -y
   ```

#### Option 2: Manual Setup

If you prefer manual setup, download and install:
- Git: https://git-scm.com/
- Python 3.13+: https://www.python.org/

#### Clone and Setup

3. **Clone repository and create virtual environment**:
   
   ```powershell
   git clone https://github.com/darderik/WASIC.git
   cd WASIC
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```
   
   **Note**: If you get an execution policy error, run:
   ```powershell
   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
   ```

4. **Install Python dependencies**:
   
   ```powershell
   pip install -r requirements.txt
   ```

### Linux (Debian/Ubuntu)

1. **Update system packages**:
   
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```

2. **Install dependencies**:
   
   ```bash
   sudo apt install git python3 python3-pip python3-venv libusb-1.0-0-dev -y
   ```

3. **Clone repository**:
   
   ```bash
   git clone https://github.com/darderik/WASIC.git
   cd WASIC
   ```

4. **Create and activate virtual environment**:
   
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

5. **Install Python dependencies**:
   
   ```bash
   pip install -r requirements.txt
   ```

6. **Add user to dialout group** (for serial port access):
   
   ```bash
   sudo usermod -a -G dialout $USER
   # Log out and back in for changes to take effect
   ```

## Configuration

### Initial Setup

After installation, the application automatically creates a `config.json` file with default settings. Key configuration options:

```json
{
  "instr_aliases": ["Raspberry", "Model 2000", "Relay Matrix"],
  "data_charts_path": "data/charts",
  "backup_schedule": 120,
  "log_level": "INFO"
}
```

**Customizing aliases**: Add IDN keywords to `instr_aliases` for generic devices. Registered instrument addons provide their own recognition keywords.

### Instrument Configuration

Connected instruments are saved to `data/instr/instruments.json` after first detection. You can manually edit this file to pre-configure instruments without physically connecting them.

## Usage

After installation and activating the virtual environment:

### Start the Application

**Windows**:
```powershell
.\venv\Scripts\Activate.ps1
python main.py
```

**Linux/macOS**:
```bash
source venv/bin/activate
python main.py
```

The web interface opens automatically at `http://localhost:8501`

### Main Interface

- **Home**: View and manage connected instruments
- **Instruments**: Send SCPI commands and query device properties
- **Tasks**: Run automated measurement routines
- **Charts**: Visualize acquired data with real-time plots
- **Logs**: View application and instrument communication logs

### Deactivate Virtual Environment

```bash
deactivate
```

### Chart data files

Final results and periodic backups are saved as tabular CSV (comma delimiter,
decimal point, full numeric precision). Column headers use `Name(Unit)`, for
example `Time(s),R_s(ohm)`; unitless columns use `Name()`. Each row is a sample,
and unequal series lengths are padded with empty cells. Merged exports place
each chart's X/Y columns side by side, prefixing labels with the chart name.

Each CSV has a `.csv.meta.csv` companion containing chart names, axis metadata,
settings and column mappings in a typed CSV table. Keep both files together
to restore the original charts in Streamlit, including histogram types and
`start_index`. Raw columns are included when `include_raw_on_save` is enabled;
structured raw records are expanded into separate columns (for example
`R_s_raw.positive_V.0()`). Raw fields without their own unit metadata use empty
parentheses. The Charts Selector uses the configured `data_charts_path` and
reads CSV exports and plain two-column CSVs.

## Project Structure

```
WASIC/
├── config/                    # Configuration management
│   ├── config.py             # Config class and defaults
│   └── config.json           # User configuration file
├── connections/              # Instrument connection handling
│   ├── connections.py        # Device discovery and management
│   └── baud_detector.py          # Serial/USB detection helpers
├── instruments/              # Core instrument abstractions
│   ├── instrument_entry.py   # Instrument wrapper class
│   └── properties.py         # Instrument property definitions
├── tasks/                    # Measurement task framework
│   ├── task.py              # Base task class
│   ├── DataProcessor.py     # Real-time data processing
│   └── structures.py        # Data structure definitions
├── wasic_api.py              # Stable addon contracts
├── addons/                   # Extensible instrument drivers & tasks
│   ├── loader.py             # Recursive addon discovery and validation
│   ├── instruments/         # Custom instrument drivers
│   └── tasks/              # Custom measurement tasks
├── webapp/                   # Streamlit web application
│   ├── pages/              # Multi-page interface
│   │   ├── home.py        # Instrument overview
│   │   ├── instruments.py  # Command interface
│   │   ├── tasks.py       # Task runner
│   │   ├── charts.py      # Data visualization
│   │   └── logs.py        # Log viewer
│   └── web_utilities.py    # UI helpers
├── data/                    # Runtime data directory (auto-created)
│   ├── charts/             # Measurement data (CSV)
│   ├── instr/              # Instrument configurations
│   └── wasic.log           # Application log
├── requirements.txt         # Python dependencies
├── main.py                  # Application entry point
└── README.md               # This file
```

## Extending WASIC

Addons are self-contained Python modules. Each module exports a `PLUGIN` definition
from `wasic_api.py`; there is no central import list or registration callback to edit.
The loader discovers modules recursively in `addons/tasks/` and `addons/instruments/`,
including nested directories. Modules starting with `_` are ignored. Helper modules
without `PLUGIN` are allowed. Keep all module-level code lightweight: discovery imports
modules but must not connect hardware, start threads, or run measurements.

### Adding a task

Create `addons/tasks/my_task.py`:

```python
from tasks import ChartData
from wasic_api import TaskSpec, TaskContext, ParameterSpec


def run(ctx: TaskContext) -> None:
    chart = ChartData(name="Example")
    chart.configure_x_axis(label="Sample", unit="")
    chart.configure_y_axis(label="Value", unit="")
    ctx.data.append(chart)
    sample = 0
    while not ctx.exit_flag.is_set():
        chart.add_processed_pair(sample, sample * 2.0)
        sample += 1
        if ctx.exit_flag.wait(ctx.parameters["update_interval"]):
            break


PLUGIN = TaskSpec(
    id="my_task",
    name="My task",
    description="A minimal measurement example without hardware.",
    run=run,
    parameters={
        "update_interval": ParameterSpec(float, 1.0, minimum=0.01),
        "merge_chart_files": ParameterSpec(bool, False),
    },
)
```

Restart WASIC: the task appears automatically. The complete runnable example is
[`addons/tasks/test_task.py`](addons/tasks/test_task.py), shown as **Test Charts**.
It needs no connected instruments and generates four charts.

`TaskContext` exposes the current run's data list, stop event, typed parameters and
instruments mapped by role. Return normally or raise an exception to finish the run;
the runtime handles logging and signals completion. Use `exit_flag.wait(interval)`
for responsive cancellation. The context's parameters are validated at launch and
cannot be edited through the UI while a task runs.

Instrument communication is synchronized by `InstrumentIO`, automatically bound
when an `Instrument_Entry` is created. Each physical driver has its own reentrant
lock, shared by its channels and any existing driver `_io_lock`. A query holds it
from the command through the complete response; ordinary task waits and calculations
leave it free. Properties, manual commands and connection verification use the same
protection. New channels created with `add_child()` inherit it automatically.

Tasks retain their selected connections before the worker starts and release them
after the measurement function, including its cleanup, returns or raises. This is
a reference count, not a lock held for the entire task: refresh queries still run,
while full discovery keeps active connections open and excludes their ports from
the scan. An unsuccessful verification also keeps a connection needed by a task.
Unused connections can be closed normally.

For an indivisible sequence of multiple driver calls, use
`with entry.io.transaction():` or
`with InstrumentIO.for_instrument(driver).transaction():` (import `InstrumentIO`
from `instruments`). Keep the scope limited to the required exchange. Use driver
methods for communication; direct calls to the underlying adapter or VISA resource
bypass this protection. Separate manual `write()` and `read()` calls need an
explicit transaction, or should be replaced by `ask()`.

Parameter types are `str`, `int`, `float` and `bool`. Definitions support `minimum`,
`maximum` and `choices`; the UI generates appropriate controls. Unknown parameters,
invalid values and nonfinite floats are rejected. `merge_chart_files` is an optional
runtime setting: declare it as a boolean to expose it in the UI; omitted means false.

For hardware, declare roles using **driver IDs**, then use the resolved driver:

```python
# Within TaskSpec:
# instruments={"meter": "keithley2000"}
# Within run(ctx):
# meter = ctx.instruments["meter"]
```

See [`addons/tasks/pid_pai/thermal_meas.py`](addons/tasks/pid_pai/thermal_meas.py).
Tasks do not need to import `Connections`, instantiate `Tasks`, or repeat IDN strings.
Missing or multiple devices matching a required driver make the task unavailable;
explicit selection of multiple identical instruments is not yet supported.

### Adding an instrument

Create `addons/instruments/my_instrument.py`:

```python
from pymeasure.instruments import Instrument
from wasic_api import InstrumentSpec


class MyInstrument(Instrument):
    def __init__(self, adapter, name):
        super().__init__(adapter, name=name)
        self.properties_list = []


PLUGIN = InstrumentSpec(
    id="my_instrument",
    name="My instrument",
    idn_keywords=("MyInstrumentModel",),
    factory=lambda adapter, info: MyInstrument(adapter, name=info.name),
)
```

The core provides a transport adapter and `SCPI_Info` to the factory. The factory
adapts the driver's constructor and returns a PyMeasure-compatible instrument.
The same IDN keywords identify the device during discovery and select its driver:
**no additional `instr_aliases` entry is needed**. Matching is case-insensitive;
if multiple definitions match an IDN, it is rejected instead of silently choosing one.
`instr_aliases` remains the fallback for generic SCPI devices without an addon.

Use `property_info` entries in `properties_list` for editable instrument properties;
the UI also supports introspection for existing drivers. A wrapper for a third-party
driver is demonstrated in
[`addons/instruments/keithley2000.py`](addons/instruments/keithley2000.py).

### Rohde & Schwarz ZNB43

[`addons/instruments/ZNB43.py`](addons/instruments/ZNB43.py) provides a
PyMeasure driver (`SCPIMixin`, `Instrument`, and measurement `Channel` objects)
and the `znb43` instrument addon. WASIC recognizes IDN strings containing
`ZNB43` and exposes channel 1 settings and the global RF switch in Instruments.
Construction sends no commands; call `reset()` explicitly when needed.

```python
from addons.instruments.ZNB43 import ZNB43

vna = ZNB43(
    "TCPIP0::192.168.1.100::inst0::INSTR",  # replace with the instrument address
    visa_library="@py",
    timeout=60000,  # VISA timeout in milliseconds, covering the entire acquisition
    read_termination="\n",
    write_termination="\n",
)
try:
    ch = vna.ch_1  # measurement channel, independent of physical RF ports
    ch.define_trace("WASIC_S21", "S21")
    ch.sweep_type = "LIN"
    ch.start_frequency = 1e9
    ch.stop_frequency = 2e9
    ch.sweep_points = 201
    ch.if_bandwidth = 1000
    ch.source_power = -20  # dBm; choose a suitable level for the DUT
    ch.trigger_source = "IMM"
    ch.average_count = 4
    ch.sweep_count = 4  # separate from the averaging factor
    ch.averaging_enabled = True
    ch.clear_averages()
    vna.rf_enabled = True
    ch.sweep()  # single acquisition cycle, waits for *OPC?
    frequency_hz, s21 = ch.read_trace("WASIC_S21")
finally:
    try:
        vna.rf_enabled = False
    finally:
        vna.adapter.close()
```

Tasks can request `instruments={"vna": "znb43"}` and access the driver through
`ctx.instruments["vna"]`. Use `vna.channel(2)` for another measurement channel;
`define_trace()` creates that channel on the analyzer if it does not exist.
Trace names must be unique across channels; defining an existing name on the
same channel replaces that trace. New traces are not automatically displayed
on the instrument screen.

`read_trace()` returns the actual stimulus axis and Python complex values
(`SDAT`), including the applied calibration and ignoring trace mathematics.
It does not acquire data; use a completed single sweep for a consistent snapshot.
The axis is in Hz for frequency sweeps, dBm for power sweeps, and seconds for
time sweeps. `read_formatted_data()` returns `FDAT` in the current display format
(one value per point for Cartesian formats, two for polar/Smith formats).
Both methods set the instrument-wide transfer format to ASCII and leave it there.
Power limits depend on frequency and installed options; IF bandwidth above
1 MHz requires option K17. External/manual triggering requires a suitable timeout
when waiting for completion. Check `vna.check_errors()` for instrument errors.

Command reference: [R&S ZNB official user manual](https://www.rohde-schwarz.com/webhelp/ZNB_HTML_UserManual_en/Content/welcome.htm).
Protocol and discovery tests use simulated adapters; physical ZNB43 communication
still requires verification on the instrument.

### Loading addons and migrating older extensions

Application startup and direct `streamlit run streamlit_app.py` call `load_addons()`.
Library users must call it explicitly before running tasks:

```python
from addons.loader import load_addons
from tasks import Tasks

registry = load_addons()
Tasks().run_task("Test Charts")
```

Loading is idempotent and preserves edited task parameters on Streamlit reruns.
Unique IDs are required within each addon category; task display names must also be
unique. Invalid addons are logged individually and listed in `registry.errors`, so
one broken import does not prevent other modules from loading. Inspect the Logs page
or `data/wasic.log` when an addon is missing. Restart after adding, removing or fixing
modules; hot reload is not supported.

To migrate an old task, replace `init_*()` and its `__init__.py` registration with a
`TaskSpec`; change the function argument to `TaskContext`, convert parameter defaults
to `ParameterSpec`, and replace singleton lookups with named instrument roles.
For instruments, move the former `INSTRUMENT_REGISTRY` entry into the driver's
`InstrumentSpec`. `Config` no longer imports addon implementations.

Direct programmatic `Task(...)`, `Tasks.add_task()` / `add_init_task()` and
`Config.add_instrument_extension()` remain available for legacy library code.
Importing `addons.tasks` alone no longer registers tasks, and the old instrument
registry/export list has been removed. Import driver classes from their modules.
See [`wasic_test.py`](wasic_test.py) for the hardware library bootstrap example.

### Validation

```bash
python -m unittest discover -s tests -v
```

Contract and discovery tests use the standard library. Runtime integration tests
require project dependencies and run with simulated instruments, without probing
hardware. Hardware communication still needs verification with real devices.

### Van der Pauw measurement

The **Van der Pauw** task uses the PyMeasure Keithley 6221 and Keithley
2182/2182A drivers with the Darderik Relay Matrix addon. All three instruments
must be connected and detected for the task to appear. Both Keithleys need
their own WASIC connection: this task uses software-controlled DC reversal,
not the 6221 hardware Delta mode or an inter-instrument trigger link.

Number the sample's four contacts **in cyclic order around its perimeter**.
The defaults assume this wiring:

| Parameter | Default | Connection |
| --- | --- | --- |
| `current_hi_group` | `c` | 6221 current HI |
| `current_lo_group` | `d` | 6221 current LO |
| `voltage_hi_group` | `a` | 2182 channel 1 voltage HI |
| `voltage_lo_group` | `b` | 2182 channel 1 voltage LO |
| `contact_1` ... `contact_4` | 1, 2, 3, 4 | Relay indices for the contacts in perimeter order |

Groups and contact indices are editable task parameters. Use four distinct
single-letter groups and four distinct positive relay indices supported by
your matrix. With the defaults, the two configurations are:

- **RA = V43 / I12**: `c1 d2 a4 b3`.
- **RB = V14 / I23**: `c2 d3 a1 b4`.

Each configuration measures voltage at `+current_A` and `-current_A`, giving
`R = abs(mean(V+) - mean(V-)) / (2 I)`. This cancels a stable thermoelectric
offset and reports resistance magnitudes. Verify contact polarity separately.
The task solves the full equation
`exp(-pi RA/Rs) + exp(-pi RB/Rs) = 1` for sheet resistance `Rs` in ohm/square.
The method assumes a homogeneous, isotropic sample of uniform thickness without
holes, small ohmic contacts at its perimeter, and zero applied magnetic field.
See the [NIST measurement method](https://www.nist.gov/pml/nanoscale-device-characterization-division/popular-links/hall-effect/resistivity-and-hall).

| Acquisition parameter | Default | Meaning |
| --- | --- | --- |
| `repetitions` | 1 | Number of attempted RA/RB cycles, including discarded cycles; task ends automatically |
| `current_A` | 0.0001 | Positive current magnitude in amperes |
| `compliance_V` | 1.0 | 6221 voltage limit; compliance discards the current RA/RB cycle |
| `nplc` | 5.0 | 2182 integration time in power-line cycles (0.01 to 50) |
| `samples_per_polarity` | 1 | Voltage readings averaged at each polarity |
| `overrange_retries` | 3 | Additional attempts after an invalid 2182 reading (0 disables recovery; maximum 10) |
| `overrange_retry_delay_s` | 0.5 | Interruptible settling delay between retries (0 to 10 seconds) |
| `current_settle_s` | 0.2 | Settling time after enabling each current polarity |
| `relay_settle_s` | 0.1 | Delay after output off, opening relays, and selecting a route |
| `repeat_delay_s` | 0.0 | Pause between attempted repetitions, including discarded cycles |
| `voltage_range_V` | 0.0 | 0 for autorange; otherwise 0.01, 0.1, 1, 10 or 100 V |
| `merge_chart_files` | true | Save all result charts together in one CSV file |

The relay matrix uses an `OK` handshake for every command. Its driver waits for
that acknowledgement before another write; queries consume their output followed
by the final `OK` (for example, `*IDN?` returns the IDN line, then `OK`).
Command/response/acknowledgement exchanges are serialized so UI
queries cannot consume a task's reply. Switching commands receive their `OK` before
`*OPC?` is sent. If an acknowledgement or query response times out, reconnect the
matrix to establish a fresh session before sending further commands. Serial discovery
probes with `*IDN?` without sending a preceding `*CLS`, and consumes any final
acknowledgement before handing the connection to the driver.

The task resets both Keithleys, waits for the 2182 reset/configuration with `*OPC?`
in idle mode, configures single channel 1 voltage measurements with
auto-zero, and floats the 6221 output LO. It disables output before changing
relays and on completion, stop or failure, sets current to zero, and opens the
matrix. Compliance discards the current cycle and continues with the next repetition.
It stops on source reading overflow, overtemperature, persistent invalid voltage or
configuration errors. Instrument state is not restored to previous settings.
Set current, compliance and settling times for your sample before running.

Transient 2182 overflow (`9.9E37`) or nonfinite voltage triggers bounded rereads
on the same route and current polarity, with source fault checks before and after
each read. Invalid values are retained as strings in raw `invalid_readings` events
with polarity, sample index and attempt; they are excluded from voltage averages.
After all attempts fail the task stops and performs cleanup, retaining earlier
complete cycles. Transport timeouts are not retried because a late reply could
desynchronize the session. `*OPC?` synchronizes pending commands, not analog
settling, and is not sent before each reading or during continuous initiation.

If the 6221 reports measurement condition `8` (`0x8`), its voltage compliance
limit was reached. The warning includes the requested current, voltage limit and
active relay route. Both RA and RB of that repetition are excluded from all processed
charts, Rs and statistics, even if RA completed before compliance in RB. Raw records
are retained with `accepted=false`, `discard_reason=voltage_compliance` and the
source error. Output is disabled and relays are opened before the next repetition.
Earlier valid cycles remain included; rejected cycles are not retried automatically. At the defaults (100 microampere and 1 V), the source can
sustain this current only up to approximately 10 kilohm of total source-loop
resistance, including current contacts; this is not the calculated sheet resistance.
Check that the configured groups match physical HI/LO wiring and that the sample
contacts form a closed current path. An open circuit can also cause compliance.
If the connected sample requires more voltage, reduce current or select a voltage
limit appropriate for the sample. The task does not automatically increase the limit
or accept readings in compliance. See the [6220/6221 reference manual, section 11](https://download.tek.com/manual/622x-901-01%20%28C%20-%20Oct%202008%29%28Ref%29.pdf).

Three histograms show the distributions of RA, RB and Rs from complete cycles
without compliance. Each saved observation retains its repetition index, so the
three resistance series remain paired for later post-processing. The task computes
neither a running mean nor uncertainty; perform that analysis on the saved data.
Bulk resistivity requires thickness: `rho = Rs * thickness`.

The saved RA/RB charts also retain raw records with relay routes, acquisition
settings, and every positive/negative voltage reading, including interrupted
acquisitions. Saved results can be
reopened from the Charts page after this finite task finishes. This is a
two-configuration measurement without additional reciprocal-contact checks.
Hardware behavior must be verified on the actual setup; automated tests use
simulated instruments and the installed PyMeasure 0.16.0 drivers.

## Troubleshooting

### Instruments Not Detected

1. **Check connection**: Verify USB/serial cable is properly connected
2. **Check permissions** (Linux):
   ```bash
   groups $USER  # Should include 'dialout'
   ```
3. **Clear cache**: Delete `connections/wasic_serial_cache.tmp` and restart
4. **Check logs**: Open the Logs page in the web interface
5. **Verify aliases**: Update `instr_aliases` in `config.json` with your instrument model

### Port Permission Denied (Linux)

```bash
sudo usermod -a -G dialout $USER
# Log out and back in for changes to take effect
```

### Installation Issues

- **USBTMC on Windows**: Uninstall USBTMC drivers and install WinUSB using [Zadig](https://zadig.akeo.ie/)
- **Missing libusb**: Run `sudo apt install libusb-1.0-0-dev` on Linux
- **Permission errors on config files**: Check directory ownership: `ls -la data/`

## Contributing

Contributions are welcome! Follow these steps to contribute:

1. Fork the repository on GitHub.
2. Create a new branch for your feature or bugfix:
   
   ```bash
   git checkout -b feature-name
   ```

3. Commit your changes:
   
   ```bash
   git commit -m "Description of the feature or bugfix"
   ```

4. Push to the newly created branch:
   
   ```bash
   git push origin feature-name
   ```

5. Open a Pull Request on the original repository.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for more details.
