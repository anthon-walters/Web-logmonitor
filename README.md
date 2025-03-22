# Web Log Monitor

This is a modernized version of the LogMonitor application, focused on the Windows implementation.

## Overview

The Log Monitor application provides interfaces for monitoring log files and device statuses across multiple Raspberry Pi devices. It displays file counts, processing status, and success rates for computer vision and bib detection operations.

## Interfaces

The application now provides two interfaces:

1. **Tkinter UI**: The original desktop interface built with Tkinter
2. **Web Interface**: A modern web interface built with FastAPI and React

### Tkinter UI

The Tkinter UI is the original desktop interface that runs as a standalone application.

### Web Interface

The web interface provides a modern, responsive interface that can be accessed from any device with a web browser. It includes:

- Real-time updates via WebSockets
- Interactive device monitoring controls
- Visual status indicators
- Success rate charts
- Processing status grid

For more information about the web interface, see the [Web Interface README](web_interface/README.md).

## Setup

1. Create a virtual environment (recommended):
   ```
   python -m venv venv
   venv\Scripts\activate
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Configure the application:
   - Review and update the `.env` file with your specific settings
   - Ensure the network paths in the configuration are accessible

## Running the Application

### Tkinter UI

To start the Tkinter UI, run:

```
python log_monitor_app.py
```

### Web Interface

To start the web interface in development mode, run:

```
python web_interface/run_dev.py
```

This will start both the backend and frontend servers. For more information, see the [Web Interface README](web_interface/README.md).

## Configuration

The application is configured through the `.env` file and includes settings for:

- Remote host configuration
- API authentication
- File paths
- Pi IP addresses
- Update intervals

## Files

- `log_monitor_app.py` - Main application entry point
- `log_monitor.py` - Core monitoring functionality
- `ui.py` - Tkinter user interface components
- `config.py` - Configuration settings
- `windows_file_monitor.py` - Windows-specific file monitoring
- `.env` - Environment variables
- `requirements.txt` - Python dependencies
- `web_interface/` - Web interface files

## Modernization Notes

This version has been enhanced with a modern web interface while maintaining the original Tkinter UI. The web interface provides a more accessible and responsive way to monitor the system from any device with a web browser.
