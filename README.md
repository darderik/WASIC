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

**Customizing aliases**: Add instrument keywords to `instr_aliases` to automatically identify connected instruments.

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
│   └── utilities.py          # Serial/USB detection helpers
├── instruments/              # Core instrument abstractions
│   ├── instrument_entry.py   # Instrument wrapper class
│   └── properties.py         # Instrument property definitions
├── tasks/                    # Measurement task framework
│   ├── task.py              # Base task class
│   ├── DataProcessor.py     # Real-time data processing
│   └── structures.py        # Data structure definitions
├── addons/                   # Extensible instrument drivers & tasks
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
├── easy_scpi/               # SCPI command abstraction
├── data/                    # Runtime data directory (auto-created)
│   ├── charts/             # Measurement data (JSON)
│   ├── instr/              # Instrument configurations
│   └── wasic.log           # Application log
├── requirements.txt         # Python dependencies
├── main.py                  # Application entry point
└── README.md               # This file
```

## Extending WASIC

### Registering a new task

1. Create a new Python module in `addons/tasks/`, for example `addons/tasks/my_task.py`.
2. Define a task function with the signature `def my_task_function(task_obj: Task) -> None:` and use `task_obj.data` and `task_obj.parameters` to produce `ChartData` objects.
3. Add an initialization function that creates a `Task` instance and adds it to the global task manager:

```python
from tasks import Task, Tasks

def init_my_task() -> None:
    my_task = Task(
        name="My Custom Task",
        description="Description of my custom task.",
        instrs_aliases=["MyInstrumentAlias"],
        function=my_task_function,
        parameters={
            "update_interval": "1",
            "my_parameter": "value",
        },
    )
    Tasks().add_task(my_task)
```

4. Register the init function in `addons/tasks/__init__.py`:

```python
from .my_task import init_my_task

# existing imports ...

task_obj.add_init_task(init_my_task)
```

5. Restart WASIC. The main application imports `addons.tasks` at startup, so the new task will be registered automatically.

### Registering a new instrument

1. Create a new instrument driver file in `addons/instruments/`, for example `addons/instruments/MyInstrument.py`.
2. Implement a custom instrument class that accepts an adapter and a name, typically by subclassing `pymeasure.instruments.Instrument` or a compatible SCPI mixin:

```python
from instruments import property_info
import pymeasure.adapters as pma
from pymeasure.instruments import Instrument, SCPIMixin

class MyInstrument(SCPIMixin, Instrument):
    def __init__(self, adapter, name, **kwargs):
        super().__init__(adapter, name=name)
        self.init_properties()

    def init_properties(self) -> None:
        self.properties_list = []
```

3. Add the new instrument class to `addons/instruments/__init__.py` and register it in `INSTRUMENT_REGISTRY`:

```python
from .MyInstrument import MyInstrument

INSTRUMENT_REGISTRY = {
    "MyInstrument": ("MyInstrumentIDN", MyInstrument),
    # existing entries...
}
```

4. Choose an IDN substring for the registry entry that matches the instrument's `*IDN?` response. The string is matched case-insensitively against the connected device IDN.
5. Optionally add the same alias to `config.json` under `instr_aliases` if you want it included in generic instrument discovery as well.
6. Restart WASIC. The instrument registry is loaded from `addons/instruments` through `config.Config`, so the custom instrument class will be available during discovery.

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
