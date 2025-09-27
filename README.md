# WASIC

WASIC is a Python project that provides basic features for managing various data inputs and tasks concering serial instruments. This README includes instructions for installation and usage on Windows and Linux (Debian/Ubuntu).
![wasic](https://github.com/user-attachments/assets/da8c8e13-4d24-4402-8154-fd600ddf6cf3)


## Table of Contents
- [Requirements](#requirements)
- [Installation](#installation)
  - [Windows](#windows)
  - [Linux (Debian/Ubuntu)](#linux-debianubuntu)
- [Usage](#usage)
- [Structure](#structure)
- [Contributing](#contributing)
- [License](#license)

## Requirements
Make sure you have the following tools installed:

- **Git**: Required to clone the repository.
- **Python**: A recent version of Python is required (Python 3.13+ recommended).
- **Package Manager**:
  - **Windows**: Chocolatey
  - **Linux**: apt



## Recommendations
On Windows, one shall uninstall USBTMC drivers of USB instruments and use WINUSB drivers.
View [pyvisa-py doc](https://pyvisa.readthedocs.io/projects/pyvisa-py/en/latest/installation.html#usb-resources-usb-instr-raw)

## Installation

### Windows
1. Install Chocolatey (if not already installed):
   
   Open a PowerShell window with administrator privileges and run:
   
   ```powershell
   Set-ExecutionPolicy Bypass -Scope Process -Force; \
   [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12; \
   iex ((New-Object System.Net.WebClient).DownloadString('https://chocolatey.org/install.ps1'))
   ```

2. Install Git and Python using Chocolatey:
   
   ```powershell
   choco install git -y
   choco install python -y
   ```

3. Clone the WASIC repository:
   
   ```powershell
   git clone https://github.com/darderik/WASIC.git
   cd WASIC
   ```

4. Install the required Python dependencies:
   
   ```powershell
   pip install -r requirements.txt
   ```

### Linux (Debian/Ubuntu)
1. Update the system:
   
   ```bash
   sudo apt update
   sudo apt upgrade -y
   ```

2. Install Git and Python:
   
   ```bash
   sudo apt install git python3 python3-pip -y
   ```

3. Clone the WASIC repository:
   
   ```bash
   git clone https://github.com/darderik/WASIC.git
   cd WASIC
   ```

4. Install the required Python dependencies:
   
   ```bash
   pip3 install -r requirements.txt
   ```

## Usage

After completing the installation, you can run the project with:

- **On Windows**:
  
  ```powershell
  python main.py
  ```

- **On Linux**:
  
  ```bash
  python3 main.py
  ```
## Structure

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
