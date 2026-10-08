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
│   ├── charts/             # Measurement data (JSON)
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
