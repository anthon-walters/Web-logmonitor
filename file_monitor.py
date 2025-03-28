import os
import os
import time
import logging
import requests
from requests.auth import HTTPBasicAuth
from typing import Optional, Dict, List, Tuple, Any
from datetime import datetime, timedelta
from enum import Enum
import requests.exceptions

# Define ProcessingStatus enum locally
class ProcessingStatus(Enum):
    PROCESSING = "processing"
    WAITING = "waiting"
    DONE = "done"
    DISABLED = "disabled" # Added for consistency
    OFFLINE = "offline" # Added for consistency

# Configure logging
logger = logging.getLogger(__name__)

# Custom Exceptions
class FileMonitorError(Exception):
    """Base exception for FileMonitor errors."""
    pass

class ShareConnectionError(FileMonitorError):
    """Error connecting to or accessing the network share."""
    pass

class ApiConnectionError(FileMonitorError):
    """Error connecting to a remote API (Stats Server or Pi)."""
    pass

class ApiTimeoutError(ApiConnectionError):
    """Timeout connecting to a remote API."""
    pass

class ApiResponseError(ApiConnectionError):
    """Unexpected status code or invalid data from API."""
    pass

class PiProcessingState:
    """Track processing state for a Pi device."""
    def __init__(self):
        self.last_count: int = 0
        self.last_change_time: datetime = datetime.now()
        self.status: ProcessingStatus = ProcessingStatus.WAITING # Default to WAITING

class FileMonitor:
    """Monitor files on a Linux system."""

    def __init__(self):
        self.logger = logging.getLogger('FileMonitor')

        # Get settings from config.py
        from config import (
            PRE_DEST_DIR,
            API_USERNAME,
            API_PASSWORD,
            API_PORT,
            STATS_SERVER_HOST,
            STATS_SERVER_PORT,
            FIELD_DEVICE_PORT
        )

        # Store base path
        self.base_path = PRE_DEST_DIR
        self.api_username = API_USERNAME
        self.api_password = API_PASSWORD
        self.api_port = API_PORT
        self.stats_server_host = STATS_SERVER_HOST
        self.stats_server_port = STATS_SERVER_PORT
        self.field_device_port = FIELD_DEVICE_PORT

        # Validate required settings
        if not self.base_path: raise ValueError("Base path not configured")
        if not self.api_username: raise ValueError("API username not configured")
        if not self.api_password: raise ValueError("API password not configured")
        if not self.api_port: raise ValueError("API port not configured")
        if not self.stats_server_host: raise ValueError("Stats server host not configured")
        if not self.stats_server_port: raise ValueError("Stats server port not configured")

        self.connected = False
        self.ui_instance = None

        # Initialize processing state tracking
        self.pi_states: Dict[str, PiProcessingState] = {f"H{i}": PiProcessingState() for i in range(1, 11)}

        # Load Pi IP addresses from environment
        self.pi_addresses: Dict[str, str] = {}
        for i in range(1, 11):
            ip = os.getenv(f'PI_{i}_IP')
            if ip: self.pi_addresses[f"H{i}"] = ip

        if not self.pi_addresses:
            self.logger.error("No Pi IP addresses configured in environment")
        else:
            self.logger.info(f"Loaded {len(self.pi_addresses)} Pi IP addresses")
            for pi_name, ip in self.pi_addresses.items():
                self.logger.info(f"{pi_name}: {ip}")

        # Try to connect to the share
        try:
            if os.path.exists(self.base_path):
                self.connected = True
                self.logger.info(f"Successfully connected to network share: {self.base_path}")
            else:
                self.logger.error(f"Cannot access share: {self.base_path}")
        except Exception as e:
            self.logger.error(f"Error connecting to share: {str(e)}")

    def cleanup(self):
        """Clean up resources."""
        pass

    def set_ui(self, ui_instance):
        """Set the UI instance for updates (for Tkinter compatibility)"""
        self.ui_instance = ui_instance

    def get_pi_success_rates(self, monitored_pis: List[str] = None) -> Tuple[float, float]:
        """Get average success rates across monitored Pis."""
        cv_rates = []
        bib_rates = []
        if monitored_pis is None: monitored_pis = list(self.pi_addresses.keys())
        for pi_name in monitored_pis:
            try:
                url = f"http://{self.stats_server_host}:{self.stats_server_port}/statistics/{pi_name}"
                response = requests.get(url, timeout=20)
                if response.status_code == 200:
                    data = response.json()
                    if data.get('total_images', 0) > 0:
                        cv_rates.append(data.get('cv_success_rate', 0))
                        bib_rates.append(data.get('bib_detection_rate', 0))
            except Exception as e: self.logger.error(f"Error getting rates for {pi_name}: {str(e)}")
        avg_cv_rate = sum(cv_rates) / len(cv_rates) if cv_rates else 0
        avg_bib_rate = sum(bib_rates) / len(bib_rates) if bib_rates else 0
        return avg_cv_rate, avg_bib_rate

    def update_processing_status(self, pi_name: str, current_count: int) -> None:
        """Update processing status based on count changes."""
        if pi_name not in self.pi_states:
             self.logger.warning(f"Attempted to update status for unknown Pi: {pi_name}")
             return

        state = self.pi_states[pi_name]
        now = datetime.now()
        new_status = state.status
        time_since_change = now - state.last_change_time

        if current_count > state.last_count:
            new_status = ProcessingStatus.PROCESSING
            state.last_change_time = now
        elif current_count == state.last_count:
            stale_threshold_minutes = 10 # Reverted back to 10 minutes
            if time_since_change > timedelta(minutes=stale_threshold_minutes):
                 if state.status != ProcessingStatus.DONE: new_status = ProcessingStatus.DONE
            else:
                 if state.status != ProcessingStatus.DONE: new_status = ProcessingStatus.WAITING
        else: # current_count < state.last_count
             self.logger.warning(f"[{pi_name}] Count decreased unexpectedly: {state.last_count} -> {current_count}")
             new_status = ProcessingStatus.WAITING
             state.last_change_time = now

        state.last_count = current_count
        state.status = new_status

        # Update Tkinter UI if instance exists (keep for compatibility if needed)
        if self.ui_instance:
            status_color_map = { ProcessingStatus.PROCESSING: "red", ProcessingStatus.WAITING: "yellow", ProcessingStatus.DONE: "green", ProcessingStatus.DISABLED: "darkgrey", ProcessingStatus.OFFLINE: "red" }
            tkinter_status = status_color_map.get(state.status, "grey")
            self.ui_instance.update_processing_status(pi_name, tkinter_status, current_count)

    def get_all_processing_states(self, monitoring_states: Dict[str, bool]) -> Dict[str, Dict[str, Any]]:
        """Get the current processing status and count for all Pis."""
        result = {}
        for pi_name, state in self.pi_states.items():
            is_monitored = monitoring_states.get(pi_name, True)
            current_status = state.status
            if not is_monitored: current_status = ProcessingStatus.DISABLED
            result[pi_name] = { "status": current_status.value, "count": state.last_count if is_monitored else 0 }
        return result

    def get_pi_total_images(self, pi_name: str) -> int:
        """Get total images count for a specific Pi."""
        url = f"http://{self.stats_server_host}:{self.stats_server_port}/statistics/{pi_name}"
        try:
            response = requests.get(url, timeout=20)
            if response.status_code == 200:
                try:
                    data = response.json()
                    total_images = data.get('total_images', 0)
                    self.update_processing_status(pi_name, total_images)
                    return total_images
                except Exception as e:
                    self.logger.error(f"[{pi_name}] Error parsing JSON response: {str(e)}")
                    raise ApiResponseError(f"Failed to parse JSON response from statistics API for {pi_name}") from e
            else:
                self.logger.error(f"[{pi_name}] Statistics API returned status {response.status_code}")
                raise ApiResponseError(f"Statistics API for {pi_name} returned status {response.status_code}")
        except requests.exceptions.Timeout as e:
            self.logger.error(f"[{pi_name}] Timeout getting statistics (20s): {e}")
            raise ApiTimeoutError(f"Timeout connecting to statistics API for {pi_name}") from e
        except requests.exceptions.ConnectionError as e:
            self.logger.error(f"[{pi_name}] Connection error getting statistics: {e}")
            raise ApiConnectionError(f"Connection error connecting to statistics API for {pi_name}") from e
        except Exception as e:
            self.logger.error(f"[{pi_name}] Unexpected error getting statistics: {str(e)}")
            raise FileMonitorError(f"Unexpected error getting statistics for {pi_name}: {e}") from e

    def get_pi_statistics(self, pi_name: str) -> int:
        """Get CV processed images count for a specific Pi."""
        url = f"http://{self.stats_server_host}:{self.stats_server_port}/statistics/{pi_name}"
        try:
            response = requests.get(url, timeout=20)
            if response.status_code == 200:
                try: data = response.json(); return data.get('cv_processed_images', 0)
                except Exception as e: self.logger.error(f"[{pi_name}] Error parsing JSON response: {str(e)}"); return 0 # Return 0 on parse error
            else:
                self.logger.error(f"[{pi_name}] CV Statistics API returned status {response.status_code}")
                raise ApiResponseError(f"CV Statistics API for {pi_name} returned status {response.status_code}")
        except requests.exceptions.Timeout as e: self.logger.error(f"[{pi_name}] Timeout getting CV statistics (20s): {e}"); raise ApiTimeoutError(f"Timeout connecting to CV statistics API for {pi_name}") from e
        except requests.exceptions.ConnectionError as e: self.logger.error(f"[{pi_name}] Connection error getting CV statistics: {e}"); raise ApiConnectionError(f"Connection error connecting to CV statistics API for {pi_name}") from e
        except Exception as e: self.logger.error(f"[{pi_name}] Unexpected error getting CV statistics: {str(e)}"); raise FileMonitorError(f"Unexpected error getting CV statistics for {pi_name}: {e}") from e

    def get_pi_bib_statistics(self, pi_name: str) -> int:
        """Get images with bibs count for a specific Pi."""
        url = f"http://{self.stats_server_host}:{self.stats_server_port}/statistics/{pi_name}"
        try:
            response = requests.get(url, timeout=20)
            if response.status_code == 200:
                try: data = response.json(); return data.get('images_with_bibs', 0)
                except Exception as e: self.logger.error(f"[{pi_name}] Error parsing JSON response: {str(e)}"); return 0 # Return 0 on parse error
            else:
                self.logger.error(f"[{pi_name}] Bib Statistics API returned status {response.status_code}")
                raise ApiResponseError(f"Bib Statistics API for {pi_name} returned status {response.status_code}")
        except requests.exceptions.Timeout as e: self.logger.error(f"[{pi_name}] Timeout getting bib statistics (20s): {e}"); raise ApiTimeoutError(f"Timeout connecting to bib statistics API for {pi_name}") from e
        except requests.exceptions.ConnectionError as e: self.logger.error(f"[{pi_name}] Connection error getting bib statistics: {e}"); raise ApiConnectionError(f"Connection error connecting to bib statistics API for {pi_name}") from e
        except Exception as e: self.logger.error(f"[{pi_name}] Unexpected error getting bib statistics: {str(e)}"); raise FileMonitorError(f"Unexpected error getting bib statistics for {pi_name}: {e}") from e

    # Add monitoring_states parameter
    def check_pi_status_and_get_data(self, monitoring_states: Dict[str, bool]) -> Tuple[Dict[str, bool], List[Tuple[str, str, str]]]:
        """
        Check if each Raspberry Pi is accessible (if monitored) and get monitoring data.
        Returns a tuple: (statuses_dict, monitoring_data_list)
        """
        statuses: Dict[str, bool] = {}
        monitoring_data: List[Tuple[str, str, str]] = []
        # self.logger.debug("Starting Pi status and data check") # Commented out noisy log
        for i in range(1, 11): pi_name = f"H{i}"; statuses[pi_name] = False; monitoring_data.append((pi_name, "0", "0"))
        temp_monitoring_data = {f"H{i}": (f"H{i}", "0", "0") for i in range(1, 11)}

        for pi_name, ip_address in self.pi_addresses.items():
            is_monitored = monitoring_states.get(pi_name, True)
            if not is_monitored:
                statuses[pi_name] = False
                temp_monitoring_data[pi_name] = (pi_name, "0", "0")
                continue

            is_online = False; processed_count = "0"; uploaded_count = "0"; device_identity = pi_name
            try:
                health_url = f"http://{ip_address}:{self.field_device_port}/health"
                health_response = requests.get(health_url, timeout=5)
                if health_response.status_code == 200:
                    health_data = health_response.json()
                    if health_data.get('status') == 'healthy':
                        is_online = True
                        try:
                            main_url = f"http://{ip_address}:{self.field_device_port}/"
                            main_response = requests.get( main_url, auth=HTTPBasicAuth(self.api_username, self.api_password), timeout=5 )
                            # self.logger.debug(f"{pi_name} main data response status: {main_response.status_code}") # Keep this?
                            if main_response.status_code == 200:
                                main_data = main_response.json()
                                device_identity = main_data.get('identity', pi_name)
                                processed_count = str(main_data.get('totalFiles', 0))
                                uploaded_count = str(main_data.get('uploadedFiles', 0))
                                # self.logger.debug(f"{device_identity} data - Processed: {processed_count}, Uploaded: {uploaded_count}") # Keep this?
                            else: self.logger.warning(f"{pi_name} main API returned status code {main_response.status_code}")
                        except Exception as e_main: self.logger.error(f"Error getting main data for {pi_name}: {str(e_main)}")
                    else: self.logger.warning(f"{pi_name} health check returned unhealthy status: {health_data.get('status')}")
                else: self.logger.warning(f"{pi_name} health check returned status code {health_response.status_code}")
            except requests.exceptions.Timeout as e_timeout: self.logger.debug(f"{pi_name} connection timed out during status check: {e_timeout}")
            except requests.exceptions.ConnectionError as e_conn: self.logger.debug(f"{pi_name} connection failed during status check: {e_conn}")
            except Exception as e_outer: self.logger.error(f"Unexpected error checking {pi_name} status: {str(e_outer)}")

            statuses[pi_name] = is_online
            temp_monitoring_data[pi_name] = (device_identity, processed_count, uploaded_count)

        monitoring_data = [temp_monitoring_data[f"H{i}"] for i in range(1, 11)]
        if self.ui_instance: # Keep Tkinter UI update for compatibility if needed
            self.logger.debug(f"Updating Tkinter UI with statuses: {statuses}")
            self.ui_instance.update_pi_monitor_widget(monitoring_data)
            self.ui_instance.update_pi_status(statuses)
        return statuses, monitoring_data

    def get_pi_monitor_data(self, monitoring_states: Dict[str, bool]) -> List[Dict[str, Any]]:
        """Gets the processed/uploaded data, respecting monitoring states."""
        states_copy = monitoring_states.copy()
        _, raw_monitor_data = self.check_pi_status_and_get_data(states_copy)
        result_data = []
        for device_id, processed, uploaded in raw_monitor_data:
             pi_name = device_id
             # Basic check if identity matches H{num} format for lookup
             if not (device_id.startswith("H") and device_id[1:].isdigit() and 1 <= int(device_id[1:]) <= 10):
                  pi_name = f"H{int(device_id[1:])}" # Attempt to map back if possible, might need better logic

             is_monitored = monitoring_states.get(pi_name, True)
             result_data.append({ "device": device_id, "processed": int(processed) if is_monitored else 0, "uploaded": int(uploaded) if is_monitored else 0 })
        return result_data

    def list_files(self, pattern: str = None) -> List[str]:
        """List files in the directory matching the pattern."""
        try:
            files = []
            for i in range(1, 11):
                pi_dir = os.path.join(self.base_path, f"H{i}")
                if not os.path.exists(pi_dir): continue
                # self.logger.debug(f"Scanning directory: {pi_dir}") # Removed noisy log
                for root, dirs, filenames in os.walk(pi_dir):
                    if 'Original' in dirs: dirs.remove('Original')
                    for filename in filenames:
                        if pattern is None or pattern.upper() in filename.upper():
                            full_path = os.path.join(root, filename)
                            rel_path = os.path.relpath(full_path, self.base_path)
                            # self.logger.debug(f"Found file: {rel_path}") # Removed noisy log
                            files.append(rel_path)
            self.logger.info(f"Total files found: {len(files)}")
            return files
        except Exception as e:
            self.logger.error(f"Error listing files: {str(e)}")
            raise ShareConnectionError(f"Error listing files in {self.base_path}: {e}") from e

    def count_files(self, directory: str = None, pattern: str = None) -> int:
        """Count files in a directory matching the pattern."""
        try:
            count = 0
            search_path = os.path.join(self.base_path, directory) if directory else self.base_path
            if not os.path.exists(search_path):
                self.logger.warning(f"Path does not exist: {search_path}")
                return 0
            for root, dirs, filenames in os.walk(search_path):
                if 'Original' in dirs: dirs.remove('Original')
                if pattern: count += len([f for f in filenames if pattern.upper() in f.upper()])
                else: count += len(filenames)
            self.logger.info(f"Total files in {search_path}: {count}")
            return count
        except Exception as e:
            self.logger.error(f"Error counting files: {str(e)}")
            raise ShareConnectionError(f"Error counting files in {search_path}: {e}") from e

    def is_connected(self) -> bool:
        """Check if the share is accessible, raising ShareConnectionError on failure."""
        try:
            accessible = os.path.exists(self.base_path)
            if not accessible: self.logger.warning(f"Share path not accessible: {self.base_path}")
            return accessible
        except Exception as e:
            self.logger.error(f"Error checking share connection {self.base_path}: {e}")
            raise ShareConnectionError(f"Error checking share connection {self.base_path}: {e}") from e
