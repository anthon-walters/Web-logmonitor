import os
import time
import logging
import requests
from requests.auth import HTTPBasicAuth
from typing import Optional, Dict, List, Tuple
from datetime import datetime, timedelta
from ui import ProcessingStatus

# Configure logging
logger = logging.getLogger(__name__)

class PiProcessingState:
    """Track processing state for a Pi device."""
    def __init__(self):
        self.last_count = 0
        self.last_change_time = datetime.now()
        self.status = ProcessingStatus.WAITING

class FileMonitor:
    """Monitor files on a Windows network share."""
    
    def __init__(self):
        self.logger = logging.getLogger('FileMonitor')
        
        # Get settings from config.py
        from config import (
            PRE_DEST_DIR,
            API_USERNAME,
            API_PASSWORD,
            API_PORT,
            STATS_SERVER_HOST,
            STATS_SERVER_PORT
        )
        
        # Store base network path
        self.base_path = PRE_DEST_DIR
        self.api_username = API_USERNAME
        self.api_password = API_PASSWORD
        self.api_port = API_PORT
        self.stats_server_host = STATS_SERVER_HOST
        self.stats_server_port = STATS_SERVER_PORT
        
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
        self.pi_states = {f"H{i}": PiProcessingState() for i in range(1, 11)}
        
        # Load Pi IP addresses from environment
        self.pi_addresses = {}
        for i in range(1, 11):
            ip = os.getenv(f'PI_{i}_IP')
            if ip:
                self.pi_addresses[f"H{i}"] = ip
        
        if not self.pi_addresses:
            self.logger.error("No Pi IP addresses configured in environment")
        else:
            self.logger.info(f"Loaded {len(self.pi_addresses)} Pi IP addresses")
            for pi_name, ip in self.pi_addresses.items():
                self.logger.debug(f"{pi_name}: {ip}")
        
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
        pass  # No cleanup needed for Windows version
    
    def set_ui(self, ui_instance):
        """Set the UI instance for updates"""
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
        state = self.pi_states[pi_name]
        now = datetime.now()
        
        if current_count > state.last_count:
            # Count increased - processing
            state.status = ProcessingStatus.PROCESSING
            state.last_change_time = now
        elif current_count == state.last_count:
            # Count unchanged - check time threshold
            time_since_change = now - state.last_change_time
            if time_since_change > timedelta(minutes=10):
                if state.status != ProcessingStatus.DONE:
                    state.status = ProcessingStatus.DONE
            else:
                if state.status != ProcessingStatus.WAITING:
                    state.status = ProcessingStatus.WAITING
        
        # Update state and UI
        state.last_count = current_count
        if self.ui_instance:
            self.ui_instance.update_processing_status(pi_name, state.status, current_count)

    def get_pi_total_images(self, pi_name: str) -> int:
        """Get total images count for a specific Pi."""
        url = f"http://{self.stats_server_host}:{self.stats_server_port}/statistics/{pi_name}"
        
        try:
            response = requests.get(url, timeout=20)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    total_images = data.get('total_images', 0)
                    
                    # Update processing status
                    self.update_processing_status(pi_name, total_images)
                    
                    return total_images
                except Exception as e:
                    self.logger.error(f"[{pi_name}] Error parsing JSON response: {str(e)}")
                    return 0
            else:
                return 0
                
        except requests.exceptions.Timeout:
            self.logger.error(f"[{pi_name}] Timeout getting statistics (20s)")
            return 0
        except requests.exceptions.ConnectionError:
            self.logger.error(f"[{pi_name}] Connection error getting statistics")
            return 0
        except Exception as e:
            self.logger.error(f"[{pi_name}] Error getting statistics: {str(e)}")
            return 0

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
                    return 0
            else:
                return 0
                
        except requests.exceptions.Timeout:
            self.logger.error(f"[{pi_name}] Timeout getting statistics (20s)")
            return 0
        except requests.exceptions.ConnectionError:
            self.logger.error(f"[{pi_name}] Connection error getting statistics")
            return 0
        except Exception as e:
            self.logger.error(f"[{pi_name}] Error getting statistics: {str(e)}")
            return 0

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
                    return 0
            else:
                return 0
                
        except requests.exceptions.Timeout:
            self.logger.error(f"[{pi_name}] Timeout getting statistics (20s)")
            return 0
        except requests.exceptions.ConnectionError:
            self.logger.error(f"[{pi_name}] Connection error getting statistics")
            return 0
        except Exception as e:
            self.logger.error(f"[{pi_name}] Error getting statistics: {str(e)}")
            return 0

    def check_pi_status(self) -> Dict[str, bool]:
        """Check if each Raspberry Pi is accessible and get monitoring data."""
        statuses = {}
        monitoring_data = []
        
        self.logger.debug("Starting Pi status check")
        
        for pi_name, ip_address in self.pi_addresses.items():
            try:
                # Try to connect to the Pi's health endpoint
                url = f"http://{ip_address}:{self.api_port}/health"
                self.logger.debug(f"Checking {pi_name} at {url}")
                
                response = requests.get(
                    url,
                    timeout=5
                )
                
                self.logger.debug(f"{pi_name} response status: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('status') == 'healthy':
                        statuses[pi_name] = True
                        # Get file counts from the main API endpoint
                        try:
                            main_url = f"http://{ip_address}:{self.api_port}/"
                            main_response = requests.get(
                                main_url,
                                auth=HTTPBasicAuth(self.api_username, self.api_password),
                                timeout=5
                            )
                            if main_response.status_code == 200:
                                main_data = main_response.json()
                                # Use the identity from the API response instead of pi_name
                                device_identity = main_data.get('identity', pi_name)
                                monitoring_data.append((
                                    device_identity,
                                    str(main_data['totalFiles']),
                                    str(main_data['uploadedFiles'])
                                ))
                                self.logger.debug(f"{device_identity} is online - Total: {main_data['totalFiles']}, Uploaded: {main_data['uploadedFiles']}")
                            else:
                                monitoring_data.append((pi_name, "0", "0"))
                                self.logger.debug(f"{pi_name} main API returned status code {main_response.status_code}")
                        except Exception as e:
                            monitoring_data.append((pi_name, "0", "0"))
                            self.logger.error(f"Error getting file counts for {pi_name}: {str(e)}")
                    else:
                        statuses[pi_name] = False
                        monitoring_data.append((pi_name, "0", "0"))
                        self.logger.debug(f"{pi_name} health check returned unhealthy status")
                else:
                    statuses[pi_name] = False
                    monitoring_data.append((pi_name, "0", "0"))
                    self.logger.debug(f"{pi_name} returned status code {response.status_code}")
                    
            except requests.exceptions.Timeout:
                self.logger.debug(f"{pi_name} connection timed out")
                statuses[pi_name] = False
                monitoring_data.append((pi_name, "0", "0"))
            except requests.exceptions.ConnectionError:
                self.logger.debug(f"{pi_name} connection failed")
                statuses[pi_name] = False
                monitoring_data.append((pi_name, "0", "0"))
            except Exception as e:
                self.logger.error(f"Error checking {pi_name} status: {str(e)}")
                statuses[pi_name] = False
                monitoring_data.append((pi_name, "0", "0"))
        
        # Update the UI with the collected data
        if self.ui_instance:
            self.logger.debug(f"Updating UI with statuses: {statuses}")
            self.ui_instance.update_pi_monitor_widget(monitoring_data)
            self.ui_instance.update_pi_status(statuses)
        
        return statuses

    def list_files(self, pattern: str = None) -> List[str]:
        """List files in the share matching the pattern."""
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
            self.logger.info(f"Total files found: {len(files)}")
            return files
        except Exception as e:
            self.logger.error(f"Error listing files: {str(e)}")
            return []

    def count_files(self, directory: str = None, pattern: str = None) -> int:
        """Count files in a directory matching the pattern."""
        try:
            count = 0
            search_path = os.path.join(self.base_path, directory) if directory else self.base_path
            
            if not os.path.exists(search_path):
                self.logger.warning(f"Path does not exist: {search_path}")
                return 0
            
            # Log the directory being searched
            self.logger.debug(f"Counting files in: {search_path}")
                
            for root, dirs, filenames in os.walk(search_path):
                # Skip 'Original' directories
                if 'Original' in dirs:
                    dirs.remove('Original')
                
                if pattern:
                    matched_files = [f for f in filenames if pattern.upper() in f.upper()]
                    count += len(matched_files)
                    # Log matched files
                    self.logger.debug(f"Found {len(matched_files)} matching files in {root}")
                else:
                    count += len(filenames)
                    # Log file count
                    self.logger.debug(f"Found {len(filenames)} files in {root}")
            
            # Log total count
            self.logger.info(f"Total files in {search_path}: {count}")
            return count
        except Exception as e:
            self.logger.error(f"Error counting files: {str(e)}")
            return 0

    def is_connected(self) -> bool:
        """Check if the share is accessible."""
        try:
            return os.path.exists(self.base_path)
        except Exception:
            return False
