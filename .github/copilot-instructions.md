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
- `import addons.tasks` in `main.py` is intentional: it triggers task registration side effects.
- Instrument extension discovery is config-driven via `Config._load_instrument_registry()` importing `addons.instruments.INSTRUMENT_REGISTRY`.
- Keep addon registration import-time and lightweight; avoid long blocking operations in module top-level code.

## Instrument discovery and communication patterns
- Discovery path in `connections/connections.py`:
  1) gather locked resources from existing entries,
  2) enumerate USB via `pymeasure.instruments.list_resources()` (`@py` backend),
  3) probe COM ports with `BaudTrialDetector`,
  4) match `*IDN?` against `config.instr_aliases`.
- New instruments are added through `_add_instrument()` and must return an `Instrument_Entry` from `_custom_instr_handler()`.
- For serial resources, code uses VISA `ASRL...::INSTR` strings plus `asrl={'baud_rate': ...}`.

## Task and data flow conventions
- `Tasks` is a singleton scheduler allowing only one running task (`_is_running`) at a time.
- `Task.start()` launches two threads: task function thread + `DataProcessor` watchdog thread.
- Task functions should:
  - append `ChartData` objects to `task_obj.data`,
  - monitor `task_obj.exit_flag`,
  - keep parameters as string-valued dict entries (UI edits via `st.data_editor`).
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
- There is no established pytest suite in this repo; validation is mainly manual through the Streamlit pages and task execution flow.

## Project-specific coding guidance for agents
- Preserve singleton semantics (`Config`, `Connections`, `Tasks`) and thread-safety locks already present.
- Keep config keys backward compatible (`config/default_config` + existing `config.json` values).
- Do not change chart JSON schema shape casually; `webapp/pages/charts.py` relies on single-chart and merged-chart formats.
- Prefer extending via `addons/instruments` and `addons/tasks` rather than modifying core manager logic unless fixing a core bug.
- When adding instrument wrappers, expose `properties_list` entries (`property_info`) so the Instruments page can auto-render editable properties.
