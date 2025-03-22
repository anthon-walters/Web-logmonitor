import os
import logging
from typing import Dict, List, Any
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('config')

# Load environment variables from .env file
load_dotenv(override=True)

# API Settings
API_USERNAME = os.getenv('API_USERNAME', 'admin')
API_PASSWORD = os.getenv('API_PASSWORD', 'changeme')
API_HOST = "0.0.0.0"
API_PORT = int(os.getenv('API_PORT', '8000'))

# Statistics Server Settings
STATS_SERVER_HOST = os.getenv('STATS_SERVER_HOST', 'localhost')
STATS_SERVER_PORT = int(os.getenv('STATS_SERVER_PORT', '8000'))

# Field Device Settings
FIELD_DEVICE_PORT = int(os.getenv('FIELD_DEVICE_PORT', '8000'))

# File paths
PRE_DEST_DIR = os.getenv('PRE_DEST_DIR', r'\\PRODUCTION\media')  # Use raw string for Windows path

# Debug mode
DEBUG_MODE: bool = os.getenv('DEBUG_MODE', 'False').lower() == 'true'
PI_MONITOR_DEBUG: bool = os.getenv('PI_MONITOR_DEBUG', 'False').lower() == 'true'

# Window settings
WEB_INTERFACE_TITLE: str = "Web Log Monitor (Ver 1.0b)"
WINDOW_TITLE: str = "Web Log Monitor V1.0"
WINDOW_WIDTH: int = int(os.getenv('WINDOW_WIDTH', '1800'))
WINDOW_HEIGHT: int = int(os.getenv('WINDOW_HEIGHT', '1150'))
WINDOW_SIZE: str = f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}"

# Tree widget column settings
FILE_COUNT_COLUMNS: List[Dict[str, Any]] = [
    {'name': 'Directory', 'width': 150, 'anchor': 'w'},
    {'name': 'Count', 'width': 70, 'anchor': 'center'}
]

PI_MONITOR_COLUMNS: List[Dict[str, Any]] = [
    {'name': 'Devices', 'width': 80, 'anchor': 'center'},
    {'name': 'Processed', 'width': 70, 'anchor': 'center'},
    {'name': 'Uploaded', 'width': 70, 'anchor': 'center'}
]

# Font settings
TITLE_FONT: tuple = ("Arial", 10, "bold")
SUBTITLE_FONT: tuple = ("Arial", 9, "bold")
TEXT_FONT: tuple = ("Courier", 8)
STATUS_COUNT_FONT: tuple = ("Arial", 12)

# Bottom log widgets settings
LOG_WIDGET_WIDTH: int = int(os.getenv('LOG_WIDGET_WIDTH', '30'))
LOG_WIDGET_HEIGHT: int = int(os.getenv('LOG_WIDGET_HEIGHT', '2'))

# Update intervals (in seconds)
FILE_COUNT_UPDATE_INTERVAL: int = int(os.getenv('FILE_COUNT_UPDATE_INTERVAL', '30'))
FILES_PROCESSED_UPDATE_INTERVAL: int = int(os.getenv('FILES_PROCESSED_UPDATE_INTERVAL', '10'))
PI_MONITOR_UPDATE_INTERVAL: int = int(os.getenv('PI_MONITOR_UPDATE_INTERVAL', '10'))
PI_STATUS_UPDATE_INTERVAL: int = int(os.getenv('PI_STATUS_UPDATE_INTERVAL', '10'))

# Maximum number of lines to keep in log widgets
MAX_LOG_LINES: int = int(os.getenv('MAX_LOG_LINES', '100'))

# Logging configuration
LOG_LEVEL: str = os.getenv('LOG_LEVEL', 'INFO')
LOG_FILE: str = os.getenv('LOG_FILE', 'web_log_monitor.log')

# File monitoring settings
FILE_CHECK_INTERVAL: int = int(os.getenv('FILE_CHECK_INTERVAL', '1'))
RETRY_DELAY: int = int(os.getenv('RETRY_DELAY', '5'))

# PI Status Display settings
PI_STATUS_FONT: tuple = ("Arial", 9)
PI_STATUS_LED_SIZE: int = 12

# Processing Status Widget settings
STATUS_RECT_WIDTH: int = 100
STATUS_RECT_HEIGHT: int = 50
STATUS_GRID_COLUMNS: int = 5
STATUS_GRID_ROWS: int = 2
STATUS_UPDATE_CHECK_INTERVAL: int = 1000
STATUS_STALE_THRESHOLD: int = 15 * 60
STATUS_FLASH_INTERVAL: int = 500
STATUS_PROCESSED_THRESHOLD: int = 4

# Log current configuration
logger.info("Configuration loaded:")
logger.info(f"API_USERNAME: {API_USERNAME}")
logger.info(f"STATS_SERVER_HOST: {STATS_SERVER_HOST}")
logger.info(f"STATS_SERVER_PORT: {STATS_SERVER_PORT}")
logger.info(f"PRE_DEST_DIR: {PRE_DEST_DIR}")
logger.info(f"FILE_COUNT_UPDATE_INTERVAL: {FILE_COUNT_UPDATE_INTERVAL}")
logger.info(f"FILES_PROCESSED_UPDATE_INTERVAL: {FILES_PROCESSED_UPDATE_INTERVAL}")
logger.info(f"PI_MONITOR_UPDATE_INTERVAL: {PI_MONITOR_UPDATE_INTERVAL}")
logger.info(f"PI_STATUS_UPDATE_INTERVAL: {PI_STATUS_UPDATE_INTERVAL}")
