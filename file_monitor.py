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
        if not self.base_path:
            raise ValueError("Base path not configured")
        if not self.api_username:
            raise ValueError("API username not configured")
        if not self.api_password:
            raise ValueError("API password not configured")
        if not self.api_port:
            raise ValueError("API port not configured")
        if not self.stats_server_host:
            raise ValueError("Stats server host not configured")
        if not self.stats_server_port:
            raise ValueError("Stats server port not configured")
        
        self.connected = False
        self.ui_instance = None
        
        # Initialize processing state tracking
        # Initialize processing state tracking
        self.pi_states: Dict[str, PiProcessingState] = {f"H{i}": PiProcessingState() for i in range(1, 11)}

        # Load Pi IP addresses from environment
        self.pi_addresses: Dict[str, str] = {}
        for i in range(1, 11):
            ip = os.getenv(f'PI_{i}_IP')
            if ip:
                self.pi_addresses[f"H{i}"] = ip
        
        if not self.pi_addresses:
            self.logger.error("No Pi IP addresses configured in environment")
        else:
            self.logger.info(f"Loaded {len(self.pi_addresses)} Pi IP addresses")
            for pi_name, ip in self.pi_addresses.items():
                self.logger.info(f"{pi_name}: {ip}") # Changed to info level for debugging

        # Try to connect to the share
        try:
            if os.path.exists(self.base_path):
                self.connected = True
                self.logger.info(f"Successfully connected to network share: {self.base_path}")
            else:
                self.logger.error(f"Cannot access share: {self.base_path}")
                # Optionally raise ShareConnectionError here if initial connection is critical
                # raise ShareConnectionError(f"Failed to connect to share {self.base_path}: {e}") from e
        except Exception as e:
            self.logger.error(f"Error connecting to share: {str(e)}")
            # Optionally raise ShareConnectionError here if initial connection is critical
            # raise ShareConnectionError(f"Failed to connect to share {self.base_path}: {e}") from e
    
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
        active_pis = 0
        
        # If no monitored_pis list provided, use all Pis
        if monitored_pis is None:
            monitored_pis = list(self.pi_addresses.keys())
        
        for pi_name in monitored_pis:
            try:
                url = f"http://{self.stats_server_host}:{self.stats_server_port}/statistics/{pi_name}"
                response = requests.get(url, timeout=20)
                
                if response.status_code == 200:
                    data = response.json()
                    cv_rate = data.get('cv_success_rate', 0)
                    bib_rate = data.get('bib_detection_rate', 0)
                    total_images = data.get('total_images', 0)
                    
                    if total_images > 0:  # Only include Pis that have processed images
                        cv_rates.append(cv_rate)
                        bib_rates.append(bib_rate)
                        active_pis += 1
                
            except Exception as e:
                self.logger.error(f"Error getting rates for {pi_name}: {str(e)}")
        
        # Calculate averages
        avg_cv_rate = sum(cv_rates) / len(cv_rates) if cv_rates else 0
        avg_bib_rate = sum(bib_rates) / len(bib_rates) if bib_rates else 0
        
        return avg_cv_rate, avg_bib_rate

    def update_processing_status(self, pi_name: str, current_count: int) -> None:
        """Update processing status based on count changes."""
        # Ensure pi_name exists in states
        if pi_name not in self.pi_states:
             self.logger.warning(f"Attempted to update status for unknown Pi: {pi_name}")
             return

        state = self.pi_states[pi_name]
        now = datetime.now()
        new_status = state.status # Keep current status unless changed
        time_since_change = now - state.last_change_time # Calculate early for logging

        # --- More Detailed Logging ---
        # Log every call for a specific device, e.g., H1
        # Replace "H1" with the actual device name you are debugging
        DEVICE_TO_DEBUG = "H1" 
        if pi_name == DEVICE_TO_DEBUG:
            self.logger.debug(
                f"[{pi_name}] update_processing_status CALLED. "
                f"current_count={current_count}, state.last_count={state.last_count}, "
                f"state.status={state.status.value}, state.last_change_time={state.last_change_time}, "
                f"time_since_change={time_since_change}"
            )
        # --- End Logging ---

        if current_count > state.last_count:
            # Count increased - processing
            new_status = ProcessingStatus.PROCESSING
            state.last_change_time = now
            # --- Log Change ---
            if pi_name == DEVICE_TO_DEBUG: self.logger.debug(f"[{pi_name}] Count INCREASED. Setting status to PROCESSING. Updating last_change_time.")
            # ---
        elif current_count == state.last_count:
            # Count unchanged - check time threshold
            # Use a configurable threshold (import from config if needed)
            stale_threshold_minutes = 10
            if time_since_change > timedelta(minutes=stale_threshold_minutes):
                 if state.status != ProcessingStatus.DONE:
                     # --- Log Change ---
                     if pi_name == DEVICE_TO_DEBUG: self.logger.debug(f"[{pi_name}] Count STABLE > {stale_threshold_minutes}min. Setting status to DONE.")
                     # ---
                     new_status = ProcessingStatus.DONE
                 # Removed previous debug log here as it's covered above
            else:
                 # If not stale, it should be WAITING (unless already DONE)
                 if state.status != ProcessingStatus.DONE:
                      # --- Log Change ---
                      if state.status != ProcessingStatus.WAITING and pi_name == DEVICE_TO_DEBUG: self.logger.debug(f"[{pi_name}] Count STABLE < {stale_threshold_minutes}min. Setting status to WAITING.")
                      # ---
                      new_status = ProcessingStatus.WAITING
        else: # current_count < state.last_count
             self.logger.warning(f"[{pi_name}] Count decreased unexpectedly: {state.last_count} -> {current_count}")
             # Optionally reset status or handle as error
             new_status = ProcessingStatus.WAITING # Revert to waiting?
             state.last_change_time = now
             # --- Log Change ---
             if pi_name == DEVICE_TO_DEBUG: self.logger.debug(f"[{pi_name}] Count DECREASED. Setting status to WAITING. Updating last_change_time.")
             # ---

        # Log final decision before applying
        if pi_name == DEVICE_TO_DEBUG and new_status != state.status:
             self.logger.debug(f"[{pi_name}] FINAL DECISION: Changing status from {state.status.value} to {new_status.value}")
        elif pi_name == DEVICE_TO_DEBUG:
             self.logger.debug(f"[{pi_name}] FINAL DECISION: Status remains {state.status.value}")

        # Update state
        state.last_count = current_count
        state.status = new_status

        # Update Tkinter UI if instance exists
        if self.ui_instance:
            # Map enum back to color string for Tkinter UI
            status_color_map = {
                ProcessingStatus.PROCESSING: "red",
                ProcessingStatus.WAITING: "yellow",
                ProcessingStatus.DONE: "green",
                ProcessingStatus.DISABLED: "darkgrey",
                ProcessingStatus.OFFLINE: "red" # Or another color for offline
            }
            tkinter_status = status_color_map.get(state.status, "grey") # Default grey
            self.ui_instance.update_processing_status(pi_name, tkinter_status, current_count)

    def get_all_processing_states(self, monitoring_states: Dict[str, bool]) -> Dict[str, Dict[str, Any]]:
        """Get the current processing status and count for all Pis."""
        result = {}
        for pi_name, state in self.pi_states.items():
            is_monitored = monitoring_states.get(pi_name, True)
            current_status = state.status

            # Override status if not monitored
            if not is_monitored:
                 current_status = ProcessingStatus.DISABLED

            result[pi_name] = {
                "status": current_status.value, # Return the string value of the enum
                "count": state.last_count if is_monitored else 0
            }
        return result

    def get_pi_total_images(self, pi_name: str) -> int:
        """Get total images count for a specific Pi."""
        url = f"http://{self.stats_server_host}:{self.stats_server_port}/statistics/{pi_name}"
        
        # --- Add Logging ---
        DEVICE_TO_DEBUG = "H3" # Replace with the device you are debugging
        if pi_name == DEVICE_TO_DEBUG: self.logger.debug(f"[{pi_name}] Attempting to get total images from {url}")
        # ---
        try:
            response = requests.get(url, timeout=20)
            # --- Add Logging ---
            if pi_name == DEVICE_TO_DEBUG: self.logger.debug(f"[{pi_name}] Stats API response status: {response.status_code}")
            # ---

            if response.status_code == 200:
                try:
                    data = response.json()
                    # --- Add Logging ---
                    if pi_name == DEVICE_TO_DEBUG: self.logger.debug(f"[{pi_name}] Stats API response JSON parsed successfully.")
                    # ---
                    total_images = data.get('total_images', 0)

                    # Update processing status
                    # --- Add Logging ---
                    if pi_name == DEVICE_TO_DEBUG: self.logger.debug(f"[{pi_name}] Calling update_processing_status with count={total_images}")
                    # ---
                    self.update_processing_status(pi_name, total_images)

                    return total_images
                except Exception as e:
                    # --- Add Logging ---
                    if pi_name == DEVICE_TO_DEBUG: self.logger.error(f"[{pi_name}] Error parsing JSON response from Stats API: {str(e)}")
                    # ---
                    self.logger.error(f"[{pi_name}] Error parsing JSON response: {str(e)}")
                    # Raise error instead of returning 0
                    raise ApiResponseError(f"Failed to parse JSON response from statistics API for {pi_name}") from e
            else:
                # Raise error for non-200 status
                # --- Add Logging ---
                if pi_name == DEVICE_TO_DEBUG: self.logger.error(f"[{pi_name}] Stats API returned non-200 status: {response.status_code}")
                # ---
                self.logger.error(f"[{pi_name}] Statistics API returned status {response.status_code}")
                raise ApiResponseError(f"Statistics API for {pi_name} returned status {response.status_code}")

        except requests.exceptions.Timeout as e:
            # --- Add Logging ---
            if pi_name == DEVICE_TO_DEBUG: self.logger.error(f"[{pi_name}] Timeout calling Stats API: {e}")
            # ---
            self.logger.error(f"[{pi_name}] Timeout getting statistics (20s): {e}")
            raise ApiTimeoutError(f"Timeout connecting to statistics API for {pi_name}") from e
        except requests.exceptions.ConnectionError as e:
            # --- Add Logging ---
            if pi_name == DEVICE_TO_DEBUG: self.logger.error(f"[{pi_name}] Connection error calling Stats API: {e}")
            # ---
            self.logger.error(f"[{pi_name}] Connection error getting statistics: {e}")
            raise ApiConnectionError(f"Connection error connecting to statistics API for {pi_name}") from e
        except Exception as e: # Catch other potential requests errors or general issues
            # --- Add Logging ---
            if pi_name == DEVICE_TO_DEBUG: self.logger.error(f"[{pi_name}] Unexpected error calling Stats API: {str(e)}")
            # ---
            self.logger.error(f"[{pi_name}] Unexpected error getting statistics: {str(e)}")
            # Re-raise as a FileMonitorError or specific API error if identifiable
            raise FileMonitorError(f"Unexpected error getting statistics for {pi_name}: {e}") from e

    def get_pi_statistics(self, pi_name: str) -> int:
        """Get CV processed images count for a specific Pi."""
        url = f"http://{self.stats_server_host}:{self.stats_server_port}/statistics/{pi_name}"
        
        try:
            response = requests.get(url, timeout=20)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    return data.get('cv_processed_images', 0)
                except Exception as e:
                    self.logger.error(f"[{pi_name}] Error parsing JSON response: {str(e)}")
                    return data.get('cv_processed_images', 0)
                except Exception as e:
                    self.logger.error(f"[{pi_name}] Error parsing JSON response for CV stats: {str(e)}")
                    raise ApiResponseError(f"Failed to parse JSON response for CV stats for {pi_name}") from e
            else:
                self.logger.error(f"[{pi_name}] CV Statistics API returned status {response.status_code}")
                raise ApiResponseError(f"CV Statistics API for {pi_name} returned status {response.status_code}")

        except requests.exceptions.Timeout as e:
            self.logger.error(f"[{pi_name}] Timeout getting CV statistics (20s): {e}")
            raise ApiTimeoutError(f"Timeout connecting to CV statistics API for {pi_name}") from e
        except requests.exceptions.ConnectionError as e:
            self.logger.error(f"[{pi_name}] Connection error getting CV statistics: {e}")
            raise ApiConnectionError(f"Connection error connecting to CV statistics API for {pi_name}") from e
        except Exception as e:
            self.logger.error(f"[{pi_name}] Unexpected error getting CV statistics: {str(e)}")
            raise FileMonitorError(f"Unexpected error getting CV statistics for {pi_name}: {e}") from e

    def get_pi_bib_statistics(self, pi_name: str) -> int:
        """Get images with bibs count for a specific Pi."""
        url = f"http://{self.stats_server_host}:{self.stats_server_port}/statistics/{pi_name}"
        
        try:
            response = requests.get(url, timeout=20)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    return data.get('images_with_bibs', 0)
                except Exception as e:
                    self.logger.error(f"[{pi_name}] Error parsing JSON response: {str(e)}")
                    return data.get('images_with_bibs', 0)
                except Exception as e:
                    self.logger.error(f"[{pi_name}] Error parsing JSON response for bib stats: {str(e)}")
                    raise ApiResponseError(f"Failed to parse JSON response for bib stats for {pi_name}") from e
            else:
                self.logger.error(f"[{pi_name}] Bib Statistics API returned status {response.status_code}")
                raise ApiResponseError(f"Bib Statistics API for {pi_name} returned status {response.status_code}")

        except requests.exceptions.Timeout as e:
            self.logger.error(f"[{pi_name}] Timeout getting bib statistics (20s): {e}")
            raise ApiTimeoutError(f"Timeout connecting to bib statistics API for {pi_name}") from e
        except requests.exceptions.ConnectionError as e:
            self.logger.error(f"[{pi_name}] Connection error getting bib statistics: {e}")
            raise ApiConnectionError(f"Connection error connecting to bib statistics API for {pi_name}") from e
        except Exception as e:
            self.logger.error(f"[{pi_name}] Unexpected error getting bib statistics: {str(e)}")
            raise FileMonitorError(f"Unexpected error getting bib statistics for {pi_name}: {e}") from e

    def check_pi_status_and_get_data(self) -> Tuple[Dict[str, bool], List[Tuple[str, str, str]]]:
        """
        Check if each Raspberry Pi is accessible and get monitoring data.
        Returns a tuple: (statuses_dict, monitoring_data_list)
        """
        statuses: Dict[str, bool] = {}
        monitoring_data: List[Tuple[str, str, str]] = []

        self.logger.debug("Starting Pi status and data check")

        # Initialize statuses and data for all potential devices
        for i in range(1, 11):
            pi_name = f"H{i}"
            statuses[pi_name] = False  # Default to offline
            monitoring_data.append((pi_name, "0", "0")) # Default data

        # Use a temporary list to build monitoring data in order
        temp_monitoring_data = {f"H{i}": (f"H{i}", "0", "0") for i in range(1, 11)}

        for pi_name, ip_address in self.pi_addresses.items():
            is_online = False
            processed_count = "0"
            uploaded_count = "0"
            device_identity = pi_name # Default identity

            try:
                # 1. Health Check
                health_url = f"http://{ip_address}:{self.field_device_port}/health"
                self.logger.debug(f"Checking health for {pi_name} at {health_url}")
                health_response = requests.get(health_url, timeout=5)
                self.logger.debug(f"{pi_name} health response status: {health_response.status_code}")

                if health_response.status_code == 200:
                    health_data = health_response.json()
                    if health_data.get('status') == 'healthy':
                        is_online = True
                        self.logger.debug(f"{pi_name} is healthy.")

                        # 2. Get Main Data if Healthy
                        try:
                            main_url = f"http://{ip_address}:{self.field_device_port}/"
                            self.logger.debug(f"Getting main data for {pi_name} at {main_url}")
                            main_response = requests.get(
                                main_url,
                                auth=HTTPBasicAuth(self.api_username, self.api_password),
                                timeout=5
                            )
                            self.logger.debug(f"{pi_name} main data response status: {main_response.status_code}")
                            if main_response.status_code == 200:
                                main_data = main_response.json()
                                device_identity = main_data.get('identity', pi_name) # Use identity from response
                                processed_count = str(main_data.get('totalFiles', 0))
                                uploaded_count = str(main_data.get('uploadedFiles', 0))
                                self.logger.debug(f"{device_identity} data - Processed: {processed_count}, Uploaded: {uploaded_count}")
                            else:
                                self.logger.warning(f"{pi_name} main API returned status code {main_response.status_code}")
                        except Exception as e_main:
                            self.logger.error(f"Error getting main data for {pi_name}: {str(e_main)}")
                    else:
                        self.logger.warning(f"{pi_name} health check returned unhealthy status: {health_data.get('status')}")
                else:
                    self.logger.warning(f"{pi_name} health check returned status code {health_response.status_code}")

            # Catch specific exceptions from requests and re-raise as custom types
            except requests.exceptions.Timeout as e_timeout:
                # Log timeout at DEBUG level as it might be expected if a Pi is slow/offline
                self.logger.debug(f"{pi_name} connection timed out during status check: {e_timeout}")
                # Optionally raise ApiTimeoutError if needed downstream, but often just logging is okay for status check
            except requests.exceptions.ConnectionError as e_conn:
                # Log connection error at DEBUG level as it might be expected if a Pi is offline
                self.logger.debug(f"{pi_name} connection failed during status check: {e_conn}")
                # Optionally raise ApiConnectionError
            except Exception as e_outer:
                self.logger.error(f"Unexpected error checking {pi_name} status: {str(e_outer)}")
                # Optionally raise FileMonitorError

            # Update results for this Pi
            statuses[pi_name] = is_online
            temp_monitoring_data[pi_name] = (device_identity, processed_count, uploaded_count)

        # Convert temp_monitoring_data dict back to list in H1-H10 order
        monitoring_data = [temp_monitoring_data[f"H{i}"] for i in range(1, 11)]

        # Update the Tkinter UI if instance exists
        if self.ui_instance:
            self.logger.debug(f"Updating Tkinter UI with statuses: {statuses}")
            self.ui_instance.update_pi_monitor_widget(monitoring_data)
            self.ui_instance.update_pi_status(statuses)

        return statuses, monitoring_data

    def get_pi_monitor_data(self, monitoring_states: Dict[str, bool]) -> List[Dict[str, Any]]:
        """Gets the processed/uploaded data, respecting monitoring states."""
        _, raw_monitor_data = self.check_pi_status_and_get_data()

        result_data = []
        for device_id, processed, uploaded in raw_monitor_data:
             # Find the original pi_name (H1-H10) in case device_id is different
             pi_name = device_id
             # A more robust way might be needed if identity format varies wildly
             if not device_id.startswith("H") or not device_id[1:].isdigit():
                  # Try to find which Hx corresponds to this IP if possible, otherwise fallback
                  # This part is complex without knowing the exact identity format
                  pass # For now, assume device_id is usable or fallback to Hx name

             is_monitored = monitoring_states.get(pi_name, True) # Default to monitored

             result_data.append({
                 "device": device_id, # Use the reported identity
                 "processed": int(processed) if is_monitored else 0,
                 "uploaded": int(uploaded) if is_monitored else 0
             })
        return result_data

    def list_files(self, pattern: str = None) -> List[str]:
        """List files in the directory matching the pattern."""
        try:
            files = []
            for i in range(1, 11):
                pi_dir = os.path.join(self.base_path, f"H{i}")
                if not os.path.exists(pi_dir):
                    self.logger.warning(f"Directory does not exist: {pi_dir}")
                    continue
                
                self.logger.debug(f"Scanning directory: {pi_dir}")
                for root, dirs, filenames in os.walk(pi_dir):
                    # Skip 'Original' directories
                    if 'Original' in dirs:
                        dirs.remove('Original')
                    
                    for filename in filenames:
                        if pattern is None or pattern.upper() in filename.upper():
                            # Use relative path from base_path
                            full_path = os.path.join(root, filename)
                            rel_path = os.path.relpath(full_path, self.base_path)
                            self.logger.debug(f"Found file: {rel_path}")
                            files.append(rel_path)
            
            # Log summary
            self.logger.info(f"Total files found: {len(files)}") # Changed to info level
            return files
        except Exception as e:
            self.logger.error(f"Error listing files: {str(e)}")
            # Raise ShareConnectionError if appropriate
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
                # Skip 'Original' directories
                if 'Original' in dirs:
                    dirs.remove('Original')
                
                if pattern:
                    matched_files = [f for f in filenames if pattern.upper() in f.upper()]
                    count += len(matched_files)
                else:
                    count += len(filenames)
            
            # Log total count
            self.logger.info(f"Total files in {search_path}: {count}") # Changed to info level
            return count
        except Exception as e:
            self.logger.error(f"Error counting files: {str(e)}")
            # Raise ShareConnectionError if appropriate
            raise ShareConnectionError(f"Error counting files in {search_path}: {e}") from e

    def is_connected(self) -> bool:
        """Check if the share is accessible, raising ShareConnectionError on failure."""
        try:
            accessible = os.path.exists(self.base_path)
            if not accessible:
                 self.logger.warning(f"Share path not accessible: {self.base_path}")
                 # Optionally raise error immediately if connection is mandatory
                 # raise ShareConnectionError(f"Share path not accessible: {self.base_path}")
            return accessible
        except Exception as e:
            self.logger.error(f"Error checking share connection {self.base_path}: {e}")
            # Raise specific error
            raise ShareConnectionError(f"Error checking share connection {self.base_path}: {e}") from e
