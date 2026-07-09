# AGENTS.md — Radiometría Fototérmica

## Run

```bash
python main.py               # launch PyQt6 GUI
```

Python 3.12.10 required; `numpy<2.0` pinned. All deps in `requirements.txt`.

## Architecture

`main.py` → `MeasurementOrchestrator` (src/ui/orchestrator.py) coordinates:
- **MesaXY** (`src/ingest/mesaxy.py`) — Arduino over serial (AccelStepper firmware at `src/ingest/MesaXYSerial/MesaXYSerial.ino`)
- **SR830** (`src/ingest/lockin.py`) — lock-in amplifier over GPIB via PyVISA
- **DataManager** (`src/ingest/data_manager.py`) — DuckDB in-memory buffer, exported to Parquet on `finalizar_experimento()`

UI layers: `gui.py` (pure layout) → `orchestrator.py` (control logic) → `workers.py` (QThreads).

## Key defaults (hardcoded in `src/constants/constants.py`)

| Setting | Value |
|---|---|
| Serial port | `COM3` |
| GPIB address | `GPIB0::8::INSTR` |
| Laser ON/OFF | 5.0 / 0.6 V via lock-in AUX OUT 3 |
| Table limits | 0–100 mm X/Y |
| Auto-gain delay | 7 s |
| Pre-start stabilisation | 10 s |

## Data

- Measurements → `data/raw/{TYPE}_{YYYYMMDD_HHMM}.parquet`
- Phase calibration reference → `data/calibracion/calibracion.parquet` (steel measurement, subtracted via interpolation)
- Experiment aliases → `data/raw/aliases.json`
- Min spatial resolution: 5 µm (physical limit)

## Scan modes

1. **XY sweep (3D)** — raster scan over X×Y grid at fixed frequency. Arduino sends `LASER` at each point, Python measures via `SNAP? 1,2,3,4`, replies `CONT`.
2. **Frequency sweep (2D)** — measures 5 cross-points across a frequency range. Uses `CRUZ` Arduino command.

## Conventions

- All UI strings, comments, docs in **Spanish**
- Design decision log: `docs/desicion_log.md`
- Stylesheet: `src/ui/styles.qss`
- Right-drag on 3D plots scales Z axis interactively
- "Home" + "Connect" are a single combined button flow
- TC and slope auto-configured per frequency in `SR830.set_frequency()`

## Tooling

- No tests, no CI, no linter, no formatter, no typechecker
- Standalone manual-control utility: `python src/utils/movemesa.py`
- Calibration file generator: `python src/utils/creador_archivo_calibracion.py` (edit paths inside)
