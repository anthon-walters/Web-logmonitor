import asyncio
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum

# Define Exceptions and Enum locally within this module
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

class ProcessingStatus(Enum):
    PROCESSING = "processing"
    WAITING = "waiting"
    DONE = "done"
    DISABLED = "disabled"
    OFFLINE = "offline"

logger = logging.getLogger("data_service")

class DataService:
    """Service for fetching and formatting data from the file monitor."""
    
    def __init__(self, file_monitor):
        self.file_monitor = file_monitor
        self.monitoring_states = {f"H{i}": True for i in range(1, 11)}
    
    def set_monitoring_state(self, device: str, state: bool):
        """Set the monitoring state for a device."""
        if device in self.monitoring_states:
            self.monitoring_states[device] = state
            logger.info(f"Set monitoring state for {device} to {state}")
    
    async def get_file_counts(self) -> Dict[str, Any]:
        """Get file counts for each Pi directory."""
        if not self.file_monitor.is_connected():
            return {
                "type": "file_counts",
                "data": {
                    "counts": [],
                    "total": 0,
                    "timestamp": datetime.now().isoformat()
                }
            }
        
        # Run in a thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, self._get_file_counts_sync)
        
        return {
            "type": "file_counts",
            "data": {
                "counts": result["counts"],
                "total": result["total"],
                "timestamp": datetime.now().isoformat()
            }
        }
    
    def _get_file_counts_sync(self) -> Dict[str, Any]:
        """Synchronous version of get_file_counts."""
        jpg_counts = []
        total_files = 0
        
        # Count JPG files in each Pi directory
        for i in range(1, 11):
            pi_name = f"H{i}"
            
            # Skip if monitoring is disabled
            if not self.monitoring_states.get(pi_name, True):
                continue
            
            # Fix: Add comma between arguments
            count = self.file_monitor.count_files(pi_name, '.JPG') 
            jpg_counts.append({"directory": pi_name, "count": count})
            total_files += count
        
        return {"counts": jpg_counts, "total": total_files}
    
    async def get_pi_status(self) -> Dict[str, Any]:
        """Get the status of all Pi devices."""
        if not self.file_monitor.is_connected():
            return {
                "type": "pi_status",
                "data": {
                    "statuses": {f"H{i}": False for i in range(1, 11)},
                    "timestamp": datetime.now().isoformat()
                }
            }
        
        # Run in a thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        # Use the new method which returns both status and monitor data
        statuses, _ = await loop.run_in_executor(None, self.file_monitor.check_pi_status_and_get_data)
        
        # Also update internal processing state based on online status
        for pi_name, is_online in statuses.items():
             if not is_online and self.monitoring_states.get(pi_name, True):
                  if pi_name in self.file_monitor.pi_states:
                       # Mark as offline if not already disabled - Use locally defined ProcessingStatus
                       if self.file_monitor.pi_states[pi_name].status != ProcessingStatus.DISABLED:
                            self.file_monitor.pi_states[pi_name].status = ProcessingStatus.OFFLINE

        return {
            "type": "pi_status",
            "data": {
                "statuses": statuses,
                "timestamp": datetime.now().isoformat()
            }
        }
    
    def _get_pi_statistics_sync(self) -> Dict[str, Any]:
        """Synchronous version of get_pi_statistics."""
        sent_data = []
        tagged_data = []
        bibs_data = []
        
        for i in range(1, 11):
            pi_name = f"H{i}"
            
            # Skip if monitoring is disabled
            if not self.monitoring_states.get(pi_name, True):
                sent_data.append({"device": pi_name, "count": 0})
                tagged_data.append({"device": pi_name, "count": 0})
                bibs_data.append({"device": pi_name, "count": 0})
                continue
            
            # Get total images
            total_images = self.file_monitor.get_pi_total_images(pi_name)
            sent_data.append({"device": pi_name, "count": total_images})
            
            # Get tagged files
            tagged_count = self.file_monitor.get_pi_statistics(pi_name)
            tagged_data.append({"device": pi_name, "count": tagged_count})
            
            # Get bib statistics
            bibs_count = self.file_monitor.get_pi_bib_statistics(pi_name)
            bibs_data.append({"device": pi_name, "count": bibs_count})
        
        totals = [
            sum(item["count"] for item in sent_data),
            sum(item["count"] for item in tagged_data),
            sum(item["count"] for item in bibs_data)
        ]
        
        return {
            "sent": sent_data,
            "tagged": tagged_data,
            "bibs": bibs_data,
            "totals": totals
        }
    
    async def get_pi_monitor(self) -> Dict[str, Any]:
        """Get monitoring data for all Pi devices."""
        if not self.file_monitor.is_connected():
            return {
                "type": "pi_monitor",
                "data": {
                    "data": [],
                    "timestamp": datetime.now().isoformat()
                }
            }
        
        # Run in a thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        # Use the new dedicated method, passing current monitoring states
        monitor_data = await loop.run_in_executor(None, self.file_monitor.get_pi_monitor_data, self.monitoring_states)
        
        return {
            "type": "pi_monitor",
            "data": {
                "data": monitor_data,
                "timestamp": datetime.now().isoformat()
            }
        }
    
    # This synchronous helper is no longer needed as get_pi_monitor_data handles it
    # def _get_pi_monitor_sync(self) -> List[Dict[str, Any]]:
    #     ...
    
    async def get_success_rates(self) -> Dict[str, Any]:
        """Get CV and bib detection success rates."""
        if not self.file_monitor.is_connected():
            return {
                "type": "success_rates",
                "data": {
                    "cv_rate": 0,
                    "bib_rate": 0,
                    "timestamp": datetime.now().isoformat()
                }
            }
        
        # Run in a thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        
        # Get monitored Pis
        monitored_pis = [pi for pi, state in self.monitoring_states.items() if state]
        
        # Get success rates
        cv_rate, bib_rate = await loop.run_in_executor(
            None, 
            lambda: self.file_monitor.get_pi_success_rates(monitored_pis)
        )
        
        return {
            "type": "success_rates",
            "data": {
                "cv_rate": cv_rate,
                "bib_rate": bib_rate,
                "timestamp": datetime.now().isoformat()
            }
        }

    async def get_processing_status(self) -> Dict[str, Any]:
        """Get processing status for all Pi devices using the refactored method."""
        if not self.file_monitor.is_connected():
            # Return default status if not connected
            default_statuses = {}
            for i in range(1, 11):
                 pi_name = f"H{i}"
                 # Use locally defined ProcessingStatus
                 default_statuses[pi_name] = {
                     "status": ProcessingStatus.DISABLED.value,
                     "count": 0
                 }
            return {
                "type": "processing_status",
                "data": {
                    "statuses": default_statuses,
                    "timestamp": datetime.now().isoformat()
                }
            }

        # If connected, run the actual status check in executor
        loop = asyncio.get_event_loop()
        statuses = await loop.run_in_executor(
            None,
            self.file_monitor.get_all_processing_states,
            self.monitoring_states
        )

        return {
            "type": "processing_status",
            "data": {
                "statuses": statuses,
                "timestamp": datetime.now().isoformat()
            }
        }
    
    async def get_all_data(self) -> Dict[str, Any]:
        """Get all data for the frontend."""
        try:
            # Get all data in parallel
            file_counts_task = asyncio.create_task(self.get_file_counts())
            pi_status_task = asyncio.create_task(self.get_pi_status())
            # Use _get_pi_statistics_sync directly in executor as it handles exceptions
            pi_statistics_task = asyncio.get_event_loop().run_in_executor(None, self._get_pi_statistics_sync)
            pi_monitor_task = asyncio.create_task(self.get_pi_monitor())
            success_rates_task = asyncio.create_task(self.get_success_rates())
            processing_status_task = asyncio.create_task(self.get_processing_status())
            
            # Wait for all tasks to complete
            file_counts = await file_counts_task
            pi_status = await pi_status_task
            pi_statistics_result = await pi_statistics_task # Result from sync function
            pi_monitor = await pi_monitor_task
            success_rates = await success_rates_task
            processing_status = await processing_status_task
            
            # Log the data being sent
            logger.info("Sending all data to client")
            
            # Combine all data
            return {
                "type": "all_data",
                "data": {
                    "file_counts": file_counts["data"],
                    "pi_status": pi_status["data"],
                    "pi_statistics": pi_statistics_result, # Use the direct result
                    "pi_monitor": pi_monitor["data"],
                    "success_rates": success_rates["data"],
                    "processing_status": processing_status["data"],
                    "timestamp": datetime.now().isoformat()
                }
            }
        # Catch specific FileMonitor errors using the locally defined classes
        except (ApiConnectionError, ApiTimeoutError, ApiResponseError, ShareConnectionError, FileMonitorError) as fm_error:
            logger.error(f"FileMonitor error getting all data: {type(fm_error).__name__} - {str(fm_error)}")
            error_message = f"{type(fm_error).__name__}: {str(fm_error)}"
            # Return empty data with specific error info
            return {
                "type": "all_data",
                "data": {
                    "file_counts": {"counts": [], "total": 0},
                    "pi_status": {"statuses": {}},
                    "pi_statistics": {"sent": [], "tagged": [], "bibs": [], "totals": [0, 0, 0]},
                    "pi_monitor": {"data": []},
                    "success_rates": {"cv_rate": 0, "bib_rate": 0},
                    "processing_status": {"statuses": {}},
                    "timestamp": datetime.now().isoformat(),
                    "error": error_message # Use the formatted error message
                }
            }
        except Exception as e: # Catch any other unexpected errors
            logger.error(f"Unexpected error getting all data: {str(e)}", exc_info=True)
            # Return empty data with generic error
            return {
                "type": "all_data",
                "data": {
                    "file_counts": {"counts": [], "total": 0},
                    "pi_status": {"statuses": {}},
                    "pi_statistics": {"sent": [], "tagged": [], "bibs": [], "totals": [0, 0, 0]},
                    "pi_monitor": {"data": []},
                    "success_rates": {"cv_rate": 0, "bib_rate": 0},
                    "processing_status": {"statuses": {}},
                    "timestamp": datetime.now().isoformat(),
                    "error": str(e)
                }
            }
