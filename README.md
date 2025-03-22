# Web Log Monitor

This is a modernized version of the LogMonitor application, focused on the Windows implementation.

## Overview

The Log Monitor application provides a graphical interface for monitoring log files and device statuses across multiple Raspberry Pi devices. It displays file counts, processing status, and success rates for computer vision and bib detection operations.

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

To start the application, run:

```
python log_monitor_app.py
```

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
- `ui.py` - User interface components
- `config.py` - Configuration settings
- `windows_file_monitor.py` - Windows-specific file monitoring
- `.env` - Environment variables
- `requirements.txt` - Python dependencies

## Modernization Notes

This version has been cleaned up to focus on the Windows implementation only. The Linux/Pi-specific components have been removed.
