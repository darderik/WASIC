# Copilot instructions for WASIC

## Big picture architecture
- WASIC is a Streamlit-based SCPI control app. Entry point is `main.py`: it initializes logging/data dirs, discovers instruments via `Connections().fetch_all_instruments()`, then launches `streamlit_app.py`.
- Core boundaries:
  - `config/`: singleton runtime config (`Config`) backed by `config.json`.
  - `connections/`: instrument discovery, adapter creation, config save/load.
  - `instruments/`: `SCPI_Info` + `Instrument_Entry` wrappers used across UI/tasks.
  - `tasks/`: task runtime (`Task`, `Tasks`) and data pipeline (`DataProcessor`, `ChartData`).
  - `addons/`: extension points for custom instrument classes and task registration.
  - `webapp/pages/`: Streamlit UI pages consuming singleton `Connections()` and `Tasks()`.

## Startup and extension loading
- Stable addon contracts live in `wasic_api.py`: `TaskSpec`, `InstrumentSpec`, `ParameterSpec`, `TaskContext`. This module must stay independent of runtime managers and UI.
- `addons/loader.py` discovers modules recursively and registers their `PLUGIN` definitions. It ignores filenames starting with `_` and allows helper modules without `PLUGIN`.
- `load_addons()` is the explicit, idempotent bootstrap used by `main.py`, `streamlit_app.py` and library clients. Importing `addons.tasks` no longer registers anything.
- Each addon owns its metadata; never add central import lists or edit `Config` to register a driver. Task and instrument `__init__.py` files stay lightweight.
- Driver factories receive `(adapter, SCPI_Info)`; instrument requirements in tasks refer to driver IDs and are injected into `TaskContext.instruments` by role.
- Duplicate IDs/task names and invalid definitions are isolated and logged in `registry.errors`. Changes require restart; do not promise hot reload.
- `addons/tasks/test_task.py` is the complete hardware-free task example; `addons/instruments/keithley2000.py` illustrates wrapping a third-party driver.

## Instrument discovery and communication patterns
- Discovery path in `connections/connections.py`:
  1) gather locked resources from existing entries,
  2) enumerate USB via `pymeasure.instruments.list_resources()` (`@py` backend),
  3) probe COM ports with `BaudTrialDetector`,
  4) match `*IDN?` against instrument definitions, then `config.instr_aliases` for generic devices.
- `_create_instrument_entry()` uses the matched addon factory and wraps its result in `Instrument_Entry`. Multiple matching drivers or devices for one task role are rejected.
- For serial resources, code uses VISA `ASRL...::INSTR` strings plus `asrl={'baud_rate': ...}`.

## Task and data flow conventions
- `Tasks` is a singleton scheduler allowing only one running task (`_is_running`) at a time.
- `Task.start()` launches two threads: task function thread + `DataProcessor` watchdog thread.
- Task functions should:
  - append `ChartData` objects to `task_obj.data`,
  - monitor `task_obj.exit_flag`,
  - declare typed `ParameterSpec` values; the UI renders type-specific controls and the runtime validates before launch. Legacy programmatic tasks still support the dictionary editor.
  - use `TaskContext` instead of manager singletons; the runtime signals completion when the function returns or raises.
- Chart persistence format is JSON via `ChartData.to_dict()` / `from_dict()`; backups are created by `DataProcessor.backup_saver()` under `data/charts/backups`.

## Streamlit UI patterns used in this repo
- Pages are defined in `streamlit_app.py` using `st.navigation` with files under `webapp/pages/`.
- Live updates use `@st.fragment(run_every=2)` (`webapp/pages/tasks.py`, `webapp/pages/logs.py`).
- Shared state is stored in `st.session_state` keys (instrument table, log buffer, chart selections).
- Prefer updating existing singleton objects (`Connections()`, `Tasks()`) rather than creating parallel managers.

## Developer workflows (current project reality)
- Environment setup and app run:
  - `python -m venv venv`
  - activate venv
  - `pip install -r requirements.txt`
  - `python main.py`
- Logs are written to `data/wasic.log`; this is the first place to inspect instrument detection and task thread issues.
- Run `python -m unittest discover -s tests -v` for addon contracts, discovery and runtime integration with simulated instruments. Verify physical communication manually; no test should scan real hardware.

## Project-specific coding guidance for agents
- Preserve singleton semantics (`Config`, `Connections`, `Tasks`) and thread-safety locks already present.
- Keep config keys backward compatible (`config/default_config` + existing `config.json` values).
- Do not change chart JSON schema shape casually; `webapp/pages/charts.py` relies on single-chart and merged-chart formats.
- Prefer extending via `addons/instruments` and `addons/tasks` rather than modifying core manager logic unless fixing a core bug.
- When adding instrument wrappers, expose `properties_list` entries (`property_info`) so the Instruments page can auto-render editable properties.
