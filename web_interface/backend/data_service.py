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
        # Add attributes to store last results
        self.last_statuses: Dict[str, bool] = {f"H{i}": False for i in range(1, 11)}
        self.last_monitoring_data: List[Tuple[str, str, str]] = [(f"H{i}", "0", "0") for i in range(1, 11)]
        self._lock = asyncio.Lock() # Lock for updating shared results

    async def set_monitoring_state(self, device: str, state: bool):
        """Set the monitoring state for a device."""
        if device in self.monitoring_states:
            # Update state safely
            async with self._lock:
                self.monitoring_states[device] = state
            logger.info(f"Set monitoring state for {device} to {state}")
            # Add log AFTER update to check the dictionary content
            logger.debug(f"Current monitoring_states after update in set_monitoring_state: {self.monitoring_states}")

    async def get_file_counts(self) -> Dict[str, Any]:
        """Get file counts for each Pi directory."""
        try:
            # Check connection within the executor to avoid blocking
            is_connected = await asyncio.get_event_loop().run_in_executor(None, self.file_monitor.is_connected)
            if not is_connected:
                logger.warning("File counts check skipped: Share not connected.")
                return {
                    "type": "file_counts",
                    "data": { "counts": [], "total": 0, "timestamp": datetime.now().isoformat() }
                }
        except Exception as e:
             logger.error(f"Error checking share connection for file counts: {e}", exc_info=True)
             return {
                 "type": "file_counts",
                 "data": { "counts": [], "total": 0, "timestamp": datetime.now().isoformat() }
             }

        # Run in a thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        # Pass a copy of monitoring states to avoid race conditions if state changes during execution
        async with self._lock: # Ensure we get a consistent copy
            states_copy = self.monitoring_states.copy()
        try:
            result = await loop.run_in_executor(None, self._get_file_counts_sync, states_copy)
        except Exception as e:
             logger.error(f"Error during _get_file_counts_sync execution: {e}", exc_info=True)
             result = {"counts": [], "total": 0} # Default on error

        return {
            "type": "file_counts",
            "data": {
                "counts": result["counts"],
                "total": result["total"],
                "timestamp": datetime.now().isoformat()
            }
        }

    # Modified to accept monitoring_states argument
    def _get_file_counts_sync(self, current_monitoring_states: Dict[str, bool]) -> Dict[str, Any]:
        """Synchronous version of get_file_counts."""
        jpg_counts = []
        total_files = 0

        # Count JPG files in each Pi directory
        for i in range(1, 11):
            pi_name = f"H{i}"

            # Skip if monitoring is disabled based on the passed state
            if not current_monitoring_states.get(pi_name, True):
                continue

            try:
                # Note: count_files itself raises ShareConnectionError now
                count = self.file_monitor.count_files(pi_name, '.JPG')
                jpg_counts.append({"directory": pi_name, "count": count})
                total_files += count
            except ShareConnectionError as e:
                 logger.error(f"Share connection error counting files for {pi_name}: {e}")
                 continue # Skip this device on error
            except Exception as e:
                 logger.error(f"Unexpected error counting files for {pi_name}: {e}", exc_info=True)
                 continue # Skip this device on error

        return {"counts": jpg_counts, "total": total_files}

    async def get_pi_status(self) -> Dict[str, Any]:
        """Fetches and stores the status/data of all Pi devices, returns status."""
        try:
            is_connected = await asyncio.get_event_loop().run_in_executor(None, self.file_monitor.is_connected)
            if not is_connected:
                logger.warning("Pi status check skipped: Share not connected.")
                async with self._lock:
                    statuses_to_return = self.last_statuses.copy()
                return {
                    "type": "pi_status",
                    "data": { "statuses": statuses_to_return, "timestamp": datetime.now().isoformat() }
                }
        except Exception as e:
             logger.error(f"Error checking share connection for pi status: {e}", exc_info=True)
             async with self._lock:
                 statuses_to_return = self.last_statuses.copy()
             return {
                 "type": "pi_status",
                 "data": { "statuses": statuses_to_return, "timestamp": datetime.now().isoformat() }
             }

        # Run in a thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        # Pass a COPY of monitoring_states to the executor
        async with self._lock: # Ensure we get a consistent copy
            states_copy = self.monitoring_states.copy()
        logger.debug(f"Calling check_pi_status_and_get_data with monitoring_states copy: {states_copy}")
        try:
            # Fetch new statuses and data
            statuses, monitoring_data = await loop.run_in_executor(None, self.file_monitor.check_pi_status_and_get_data, states_copy)

            # Store the results safely
            async with self._lock:
                self.last_statuses = statuses
                self.last_monitoring_data = monitoring_data

            # Also update internal processing state based on online status
            # Use the freshly fetched statuses and current monitoring state
            for pi_name, is_online in statuses.items():
                 # Check current monitoring state from the main dictionary
                 if not is_online and self.monitoring_states.get(pi_name, True):
                      if pi_name in self.file_monitor.pi_states:
                           # Mark as offline if not already disabled
                           if self.file_monitor.pi_states[pi_name].status != ProcessingStatus.DISABLED:
                                self.file_monitor.pi_states[pi_name].status = ProcessingStatus.OFFLINE

            status_to_return = statuses # Return the newly fetched status

        except Exception as e:
             logger.error(f"Error during check_pi_status_and_get_data execution: {e}", exc_info=True)
             # On error, return the last known status
             async with self._lock:
                 status_to_return = self.last_statuses.copy()

        return {
            "type": "pi_status",
            "data": {
                "statuses": status_to_return,
                "timestamp": datetime.now().isoformat()
            }
        }

    # Modified to accept monitoring_states argument
    def _get_pi_statistics_sync(self, current_monitoring_states: Dict[str, bool]) -> Dict[str, Any]:
        """Synchronous version of get_pi_statistics."""
        sent_data = []
        tagged_data = []
        bibs_data = []

        for i in range(1, 11):
            pi_name = f"H{i}"

            # Skip if monitoring is disabled based on the passed state
            if not current_monitoring_states.get(pi_name, True):
                sent_data.append({"device": pi_name, "count": 0})
                tagged_data.append({"device": pi_name, "count": 0})
                bibs_data.append({"device": pi_name, "count": 0})
                continue

            try:
                # Get total images
                total_images = self.file_monitor.get_pi_total_images(pi_name)
                sent_data.append({"device": pi_name, "count": total_images})

                # Get tagged files
                tagged_count = self.file_monitor.get_pi_statistics(pi_name)
                tagged_data.append({"device": pi_name, "count": tagged_count})

                # Get bib statistics
                bibs_count = self.file_monitor.get_pi_bib_statistics(pi_name)
                bibs_data.append({"device": pi_name, "count": bibs_count})
            except (ApiConnectionError, ApiTimeoutError, ApiResponseError, FileMonitorError) as e:
                 logger.error(f"API/Monitor error getting statistics for {pi_name}: {e}")
                 # Append 0 counts on error for this device
                 sent_data.append({"device": pi_name, "count": 0})
                 tagged_data.append({"device": pi_name, "count": 0})
                 bibs_data.append({"device": pi_name, "count": 0})
                 continue # Continue to next device
            except Exception as e:
                 logger.error(f"Unexpected error getting statistics for {pi_name}: {e}", exc_info=True)
                 sent_data.append({"device": pi_name, "count": 0})
                 tagged_data.append({"device": pi_name, "count": 0})
                 bibs_data.append({"device": pi_name, "count": 0})
                 continue # Continue to next device

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
        """Gets stored monitoring data and formats it."""
        # No need to check connection here, rely on get_pi_status having run

        # --- Return the stored data ---
        async with self._lock:
            # Get a reference to the stored list (it's a list of tuples, safe to read)
            monitor_data_to_return = self.last_monitoring_data

        # Format the stored data for the API/WebSocket
        formatted_monitor_data = []
        for device_id, processed, uploaded in monitor_data_to_return:
             pi_name = device_id # Assuming device_id is H1, H2 etc. for monitoring_states lookup
             # Use current monitoring state for formatting
             is_monitored = self.monitoring_states.get(pi_name, True)
             formatted_monitor_data.append({
                 "device": device_id,
                 "processed": int(processed) if is_monitored else 0,
                 "uploaded": int(uploaded) if is_monitored else 0
             })

        return {
             "type": "pi_monitor",
             "data": {
                 "data": formatted_monitor_data, # Use formatted data
                 "timestamp": datetime.now().isoformat()
             }
        }

    async def get_success_rates(self) -> Dict[str, Any]:
        """Get CV and bib detection success rates."""
        try:
            is_connected = await asyncio.get_event_loop().run_in_executor(None, self.file_monitor.is_connected)
            if not is_connected:
                logger.warning("Success rates check skipped: Share not connected.")
                return {
                    "type": "success_rates",
                    "data": { "cv_rate": 0, "bib_rate": 0, "timestamp": datetime.now().isoformat() }
                }
        except Exception as e:
             logger.error(f"Error checking share connection for success rates: {e}", exc_info=True)
             return {
                 "type": "success_rates",
                 "data": { "cv_rate": 0, "bib_rate": 0, "timestamp": datetime.now().isoformat() }
             }

        # Run in a thread pool to avoid blocking
        loop = asyncio.get_event_loop()

        # Get monitored Pis based on current state
        async with self._lock: # Ensure consistent read
            monitored_pis = [pi for pi, state in self.monitoring_states.items() if state]

        # Get success rates
        try:
            cv_rate, bib_rate = await loop.run_in_executor(
                None,
                lambda: self.file_monitor.get_pi_success_rates(monitored_pis)
            )
        except Exception as e:
             logger.error(f"Error getting success rates: {e}", exc_info=True)
             cv_rate, bib_rate = 0, 0 # Default on error

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
        try:
            is_connected = await asyncio.get_event_loop().run_in_executor(None, self.file_monitor.is_connected)
            if not is_connected:
                logger.warning("Processing status check skipped: Share not connected.")
                # Return default status if not connected
                default_statuses = {}
                for i in range(1, 11):
                     pi_name = f"H{i}"
                     default_statuses[pi_name] = { "status": ProcessingStatus.DISABLED.value, "count": 0 }
                return {
                    "type": "processing_status",
                    "data": { "statuses": default_statuses, "timestamp": datetime.now().isoformat() }
                }
        except Exception as e:
             logger.error(f"Error checking share connection for processing status: {e}", exc_info=True)
             default_statuses = {}
             for i in range(1, 11):
                  pi_name = f"H{i}"
                  default_statuses[pi_name] = { "status": ProcessingStatus.DISABLED.value, "count": 0 }
             return {
                 "type": "processing_status",
                 "data": { "statuses": default_statuses, "timestamp": datetime.now().isoformat() }
             }

        # If connected, run the actual status check in executor
        loop = asyncio.get_event_loop()
        try:
            # Pass a copy of monitoring states
            async with self._lock: # Ensure consistent copy
                states_copy = self.monitoring_states.copy()
            statuses = await loop.run_in_executor(
                None,
                self.file_monitor.get_all_processing_states,
                states_copy
            )
        except Exception as e:
             logger.error(f"Error getting processing states: {e}", exc_info=True)
             # Return default status on error
             statuses = {}
             for i in range(1, 11):
                  pi_name = f"H{i}"
                  statuses[pi_name] = {
                      "status": ProcessingStatus.DISABLED.value, # Or some error state?
                      "count": 0
                  }

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
            # Ensure pi_status runs first to fetch and store latest status/monitor data
            pi_status = await self.get_pi_status()

            # Now run other tasks in parallel, they can use stored data if needed
            file_counts_task = asyncio.create_task(self.get_file_counts())
            # Pass a copy of monitoring states to sync function
            async with self._lock: # Ensure consistent copy
                states_copy_stats = self.monitoring_states.copy()
            pi_statistics_task = asyncio.get_event_loop().run_in_executor(None, self._get_pi_statistics_sync, states_copy_stats)
            pi_monitor_task = asyncio.create_task(self.get_pi_monitor()) # Reads stored data
            success_rates_task = asyncio.create_task(self.get_success_rates())
            processing_status_task = asyncio.create_task(self.get_processing_status())

            # Wait for the remaining tasks to complete
            file_counts = await file_counts_task
            pi_statistics_result = await pi_statistics_task
            pi_monitor = await pi_monitor_task
            success_rates = await success_rates_task
            processing_status = await processing_status_task

            # Log the data being sent
            logger.debug("Sending all data to client") # Changed to debug

            # Combine all data
            return {
                "type": "all_data",
                "data": {
                    "file_counts": file_counts["data"],
                    "pi_status": pi_status["data"], # Use status from the initial call
                    "pi_statistics": pi_statistics_result,
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
