# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AIBackgroundWorker is a background system that automatically collects user activity data and external information for AI systems. It consists of two main functional areas:

1. **Internal Data Collection**: Captures user activity in WSL/Windows environments and browser history
2. **External Data Collection**: Gathers news, RSS feeds, and web information

The system prioritizes privacy-by-design, storing only hashed titles and domain names by default.

## Architecture

### Core Components

- **lifelog-system/**: Main lifelog tracking system
  - `src/lifelog/`: Core lifelog functionality with collectors, database, and utilities
  - `src/browser_history/`: Browser history import/tracking
  - `config/`: Configuration files (config.yaml, privacy.yaml, privacy_windows.yaml)
  - `data/`: SQLite database storage (WAL mode)
  - `logs/`: Log files and Windows foreground logger output

- **scripts/**: Shell scripts for various subsystems
  - `daemon.sh`: Main daemon control (start/stop/status)
  - `lifelog/`: Data viewing scripts (summaries, timelines)
  - `browser/`: Browser history collection scripts
  - `windows/`: Windows-side foreground window logger (PowerShell)
  - `info_collector/`: External information collection scripts

### Key Architecture Patterns

1. **Event-Driven Activity Tracking**: Uses `psutil` to monitor processes and windows
2. **Privacy Hash System**: Window titles stored as SHA256 hashes by default
3. **SQLite WAL Mode**: Concurrent read/write performance optimization
4. **Dual Environment**: WSL (main collector) + Windows (foreground window logger via PowerShell)
5. **Bulk Write Strategy**: Batches database writes to reduce I/O

### Database Structure

- **apps**: Application master table
- **activity_intervals**: Main activity data with start/end timestamps
- **health_snapshots**: System health monitoring metrics

## Development Environment

### Setup

```bash
# Install dependencies (from project root or lifelog-system/)
cd lifelog-system
uv sync

# For development dependencies
uv sync --all-extras
```

### Python Environment

- **Python**: 3.12+
- **Package Manager**: uv (Astral's fast Python package manager)
- **Code Quality Tools**: black, ruff, mypy
- **Testing**: pytest

## Common Commands

### Running the System

```bash
# Start lifelog daemon (from project root)
ENABLE_WINDOWS_FOREGROUND_LOGGER=1 ./scripts/daemon.sh start

# Check status
./scripts/daemon.sh status

# View logs
./scripts/daemon.sh logs

# Stop daemon
./scripts/daemon.sh stop

# Restart
./scripts/daemon.sh restart
```

### Windows Foreground Logger Control

```bash
# Stop Windows logger separately
./scripts/daemon.sh winlogger-stop

# Check Windows logger status
./scripts/daemon.sh winlogger-status
```

### Data Viewing (CLI Tools)

```bash
cd lifelog-system

# Daily summary
uv run python -m src.lifelog.cli_viewer summary
uv run python -m src.lifelog.cli_viewer summary --date 2025-11-10

# Hourly activity breakdown
uv run python -m src.lifelog.cli_viewer hourly
uv run python -m src.lifelog.cli_viewer hourly --date 2025-11-10

# Recent timeline
uv run python -m src.lifelog.cli_viewer timeline --hours 2

# Health metrics
uv run python -m src.lifelog.cli_viewer health --hours 24
```

### Testing

```bash
# Run all tests
cd lifelog-system
uv run pytest tests/ -v

# Run with coverage
uv run pytest tests/ --cov=src --cov-report=html
```

### Code Quality

```bash
cd lifelog-system

# Format code
uv run black src/ tests/

# Lint
uv run ruff check src/ tests/

# Type checking
uv run mypy src/
```

## Configuration Files

### lifelog-system/config/config.yaml

Main system configuration:
- Sampling intervals
- Idle detection thresholds
- Bulk write settings
- SLO (Service Level Objective) targets

### lifelog-system/config/privacy.yaml

WSL/Linux privacy settings:
- Title text storage preferences
- Excluded process list
- Sensitive keyword filters

### lifelog-system/config/privacy_windows.yaml

Windows-specific privacy settings for the foreground logger.

## Working with Different Components

### Modifying Activity Collection

Key files:
- `lifelog-system/src/lifelog/collectors/activity_collector.py`: Main collection logic
- `lifelog-system/src/lifelog/collectors/foreground_tracker.py`: Foreground window tracking
- `lifelog-system/src/lifelog/collectors/idle_detector.py`: Idle state detection
- `lifelog-system/src/lifelog/collectors/health_monitor.py`: Health metrics collection

### Database Operations

- `lifelog-system/src/lifelog/database/schema.py`: Schema definitions
- `lifelog-system/src/lifelog/database/db_manager.py`: Database manager with WAL mode setup

### Privacy Controls

- `lifelog-system/src/lifelog/utils/privacy.py`: Privacy hash functions and filters

## Important Notes

1. **Always run from correct directory**: Daemon script should be run from project root, but Python modules from lifelog-system/
2. **Windows integration**: The Windows foreground logger is a PowerShell script that outputs to `logs/windows_foreground.jsonl`
3. **PID files**: Located at project root (`lifelog.pid`, `windows_logger.pid`)
4. **Database location**: `lifelog-system/data/lifelog.db`
5. **Environment variables for Windows logger**:
   - `ENABLE_WINDOWS_FOREGROUND_LOGGER=1`: Enable Windows logger on daemon start
   - `WINDOWS_FOREGROUND_INTERVAL`: Polling interval in seconds (default: 5)
   - `WINDOWS_FOREGROUND_STOP_AFTER`: Auto-stop after N seconds (0 = unlimited)

## Storage Paths

- Windows root path: `C:\YellowMable`
- WSL root path: `/mnt/c/YellowMable`
- Default report output: `/mnt/c/YellowMable/00_Raw`
- Override env var: `YELLOWMABLE_DIR` (default: `/mnt/c/YellowMable`)
- Quick access symlink (repo root): `./YellowMable`

## Future Extensions

- MCP Server implementation (Claude integration)
- Windows API implementation (Win32)
- Browser history integration enhancement
- Local LLM daily summaries
- Web UI for data visualization
