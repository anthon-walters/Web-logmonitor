import asyncio
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum
import redis # Import redis

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

# --- Redis Configuration ---
# Assuming Redis runs on localhost:6379 by default
# TODO: Make these configurable via environment variables or config file
REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB = 0
MONITORING_STATES_KEY = "monitoring_states" # Key for the Redis Hash
# --- End Redis Configuration ---

class DataService:
    """Service for fetching and formatting data from the file monitor."""

    def __init__(self, file_monitor):
        self.file_monitor = file_monitor
        # Remove local monitoring_states dictionary
        # self.monitoring_states = {f"H{i}": True for i in range(1, 11)}
        self.last_statuses: Dict[str, bool] = {f"H{i}": False for i in range(1, 11)}
        self.last_monitoring_data: List[Tuple[str, str, str]] = [(f"H{i}", "0", "0") for i in range(1, 11)]
        self._lock = asyncio.Lock() # Lock for updating shared results

        # Initialize Redis connection
        try:
            # Use connection pool for better performance with multiple workers/requests
            self.redis_pool = redis.ConnectionPool(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=REDIS_DB,
                decode_responses=True
            )
            self.redis_client = redis.Redis(connection_pool=self.redis_pool)
            self.redis_client.ping() # Check connection
            logger.info(f"Connected to Redis at {REDIS_HOST}:{REDIS_PORT}")
            # Initialize states in Redis if not already present
            if not self.redis_client.exists(MONITORING_STATES_KEY):
                initial_states = {f"H{i}": "True" for i in range(1, 11)} # Store as strings
                self.redis_client.hset(MONITORING_STATES_KEY, mapping=initial_states)
                logger.info("Initialized monitoring states in Redis.")
        except redis.exceptions.ConnectionError as e:
            logger.error(f"Failed to connect to Redis: {e}. Monitoring state toggling will not work.", exc_info=True)
            self.redis_client = None
            self.redis_pool = None
        except Exception as e:
             logger.error(f"An unexpected error occurred during Redis initialization: {e}", exc_info=True)
             self.redis_client = None
             self.redis_pool = None


    # --- Helper to get all monitoring states ---
    def _get_all_monitoring_states_sync(self) -> Dict[str, bool]:
        if not self.redis_client:
            logger.warning("Redis client not available, returning default monitoring states (all True).")
            return {f"H{i}": True for i in range(1, 11)}
        try:
            states_str_dict = self.redis_client.hgetall(MONITORING_STATES_KEY)
            # Convert string values back to boolean
            states_bool_dict = {dev: state == "True" for dev, state in states_str_dict.items()}
            # Ensure all H1-H10 keys exist, defaulting to True if missing
            for i in range(1, 11):
                 pi_name = f"H{i}"
                 if pi_name not in states_bool_dict:
                      states_bool_dict[pi_name] = True # Default missing keys to True
            return states_bool_dict
        except Exception as e:
            logger.error(f"Error reading all monitoring states from Redis: {e}", exc_info=True)
            return {f"H{i}": True for i in range(1, 11)} # Default on error

    async def set_monitoring_state(self, device: str, state: bool):
        """Set the monitoring state for a device in Redis."""
        if not self.redis_client:
            logger.error("Cannot set monitoring state: Redis client not available.")
            # Optionally raise an exception to signal failure to the caller
            raise ConnectionError("Redis client not available")

        try:
            # Store state as string ("True" or "False")
            state_str = str(state)
            # Run Redis operation in executor as redis-py client is synchronous
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.redis_client.hset(MONITORING_STATES_KEY, device, state_str)
            )
            logger.info(f"Set monitoring state for {device} to {state} in Redis")
        except Exception as e:
            logger.error(f"Error setting monitoring state for {device} in Redis: {e}", exc_info=True)
            # Optionally re-raise or handle
            raise


    async def get_file_counts(self) -> Dict[str, Any]:
        """Get file counts for each Pi directory."""
        try:
            is_connected = await asyncio.get_event_loop().run_in_executor(None, self.file_monitor.is_connected)
            if not is_connected:
                logger.warning("File counts check skipped: Share not connected.")
                return { "type": "file_counts", "data": { "counts": [], "total": 0, "timestamp": datetime.now().isoformat() } }
        except Exception as e:
             logger.error(f"Error checking share connection for file counts: {e}", exc_info=True)
             return { "type": "file_counts", "data": { "counts": [], "total": 0, "timestamp": datetime.now().isoformat() } }

        loop = asyncio.get_event_loop()
        # Fetch current states from Redis before running in executor
        current_states = self._get_all_monitoring_states_sync()
        try:
            result = await loop.run_in_executor(None, self._get_file_counts_sync, current_states)
        except Exception as e:
             logger.error(f"Error during _get_file_counts_sync execution: {e}", exc_info=True)
             result = {"counts": [], "total": 0}

        return {
            "type": "file_counts",
            "data": {
                "counts": result["counts"],
                "total": result["total"],
                "timestamp": datetime.now().isoformat()
            }
        }

    # Accepts monitoring_states argument
    def _get_file_counts_sync(self, current_monitoring_states: Dict[str, bool]) -> Dict[str, Any]:
        """Synchronous version of get_file_counts."""
        jpg_counts = []
        total_files = 0
        for i in range(1, 11):
            pi_name = f"H{i}"
            if not current_monitoring_states.get(pi_name, True): continue
            try:
                count = self.file_monitor.count_files(pi_name, '.JPG')
                jpg_counts.append({"directory": pi_name, "count": count})
                total_files += count
            except ShareConnectionError as e: logger.error(f"Share connection error counting files for {pi_name}: {e}"); continue
            except Exception as e: logger.error(f"Unexpected error counting files for {pi_name}: {e}", exc_info=True); continue
        return {"counts": jpg_counts, "total": total_files}

    async def get_pi_status(self) -> Dict[str, Any]:
        """Fetches and stores the status/data of all Pi devices, returns status."""
        try:
            is_connected = await asyncio.get_event_loop().run_in_executor(None, self.file_monitor.is_connected)
            if not is_connected:
                logger.warning("Pi status check skipped: Share not connected.")
                async with self._lock: statuses_to_return = self.last_statuses.copy()
                return { "type": "pi_status", "data": { "statuses": statuses_to_return, "timestamp": datetime.now().isoformat() } }
        except Exception as e:
             logger.error(f"Error checking share connection for pi status: {e}", exc_info=True)
             async with self._lock: statuses_to_return = self.last_statuses.copy()
             return { "type": "pi_status", "data": { "statuses": statuses_to_return, "timestamp": datetime.now().isoformat() } }

        loop = asyncio.get_event_loop()
        # Fetch current states from Redis before running in executor
        current_states = self._get_all_monitoring_states_sync()
        logger.debug(f"Calling check_pi_status_and_get_data with monitoring_states: {current_states}")
        try:
            statuses, monitoring_data = await loop.run_in_executor(None, self.file_monitor.check_pi_status_and_get_data, current_states)
            async with self._lock:
                self.last_statuses = statuses
                self.last_monitoring_data = monitoring_data

            # Update internal processing state based on online status and Redis state
            # Use the 'current_states' fetched at the start of this function call
            for pi_name, is_online in statuses.items():
                 if not is_online and current_states.get(pi_name, True): # Check against the state used for the check
                      if pi_name in self.file_monitor.pi_states:
                           if self.file_monitor.pi_states[pi_name].status != ProcessingStatus.DISABLED:
                                self.file_monitor.pi_states[pi_name].status = ProcessingStatus.OFFLINE
            status_to_return = statuses
        except Exception as e:
             logger.error(f"Error during check_pi_status_and_get_data execution: {e}", exc_info=True)
             async with self._lock: status_to_return = self.last_statuses.copy()

        return {
            "type": "pi_status",
            "data": { "statuses": status_to_return, "timestamp": datetime.now().isoformat() }
        }

    # Accepts monitoring_states argument
    def _get_pi_statistics_sync(self, current_monitoring_states: Dict[str, bool]) -> Dict[str, Any]:
        """Synchronous version of get_pi_statistics."""
        sent_data = []
        tagged_data = []
        bibs_data = []
        for i in range(1, 11):
            pi_name = f"H{i}"
            if not current_monitoring_states.get(pi_name, True):
                sent_data.append({"device": pi_name, "count": 0}); tagged_data.append({"device": pi_name, "count": 0}); bibs_data.append({"device": pi_name, "count": 0})
                continue
            try:
                total_images = self.file_monitor.get_pi_total_images(pi_name)
                sent_data.append({"device": pi_name, "count": total_images})
                tagged_count = self.file_monitor.get_pi_statistics(pi_name)
                tagged_data.append({"device": pi_name, "count": tagged_count})
                bibs_count = self.file_monitor.get_pi_bib_statistics(pi_name)
                bibs_data.append({"device": pi_name, "count": bibs_count})
            except (ApiConnectionError, ApiTimeoutError, ApiResponseError, FileMonitorError) as e:
                 logger.error(f"API/Monitor error getting statistics for {pi_name}: {e}")
                 sent_data.append({"device": pi_name, "count": 0}); tagged_data.append({"device": pi_name, "count": 0}); bibs_data.append({"device": pi_name, "count": 0})
                 continue
            except Exception as e:
                 logger.error(f"Unexpected error getting statistics for {pi_name}: {e}", exc_info=True)
                 sent_data.append({"device": pi_name, "count": 0}); tagged_data.append({"device": pi_name, "count": 0}); bibs_data.append({"device": pi_name, "count": 0})
                 continue
        totals = [ sum(item["count"] for item in sent_data), sum(item["count"] for item in tagged_data), sum(item["count"] for item in bibs_data) ]
        return { "sent": sent_data, "tagged": tagged_data, "bibs": bibs_data, "totals": totals }

    async def get_pi_monitor(self) -> Dict[str, Any]:
        """Gets stored monitoring data and formats it."""
        async with self._lock:
            monitor_data_to_return = self.last_monitoring_data
        # Fetch current states from Redis for formatting
        current_states = self._get_all_monitoring_states_sync()
        formatted_monitor_data = []
        for device_id, processed, uploaded in monitor_data_to_return:
             pi_name = device_id
             is_monitored = current_states.get(pi_name, True)
             formatted_monitor_data.append({
                 "device": device_id,
                 "processed": int(processed) if is_monitored else 0,
                 "uploaded": int(uploaded) if is_monitored else 0
             })
        return {
             "type": "pi_monitor",
             "data": { "data": formatted_monitor_data, "timestamp": datetime.now().isoformat() }
        }

    async def get_success_rates(self) -> Dict[str, Any]:
        """Get CV and bib detection success rates."""
        try:
            is_connected = await asyncio.get_event_loop().run_in_executor(None, self.file_monitor.is_connected)
            if not is_connected:
                logger.warning("Success rates check skipped: Share not connected.")
                return { "type": "success_rates", "data": { "cv_rate": 0, "bib_rate": 0, "timestamp": datetime.now().isoformat() } }
        except Exception as e:
             logger.error(f"Error checking share connection for success rates: {e}", exc_info=True)
             return { "type": "success_rates", "data": { "cv_rate": 0, "bib_rate": 0, "timestamp": datetime.now().isoformat() } }

        loop = asyncio.get_event_loop()
        # Get monitored Pis based on current Redis state
        current_states = self._get_all_monitoring_states_sync()
        monitored_pis = [pi for pi, state in current_states.items() if state]
        try:
            cv_rate, bib_rate = await loop.run_in_executor( None, lambda: self.file_monitor.get_pi_success_rates(monitored_pis) )
        except Exception as e:
             logger.error(f"Error getting success rates: {e}", exc_info=True)
             cv_rate, bib_rate = 0, 0
        return {
            "type": "success_rates",
            "data": { "cv_rate": cv_rate, "bib_rate": bib_rate, "timestamp": datetime.now().isoformat() }
        }

    async def get_processing_status(self) -> Dict[str, Any]:
        """Get processing status for all Pi devices using the refactored method."""
        try:
            is_connected = await asyncio.get_event_loop().run_in_executor(None, self.file_monitor.is_connected)
            if not is_connected:
                logger.warning("Processing status check skipped: Share not connected.")
                default_statuses = { f"H{i}": { "status": ProcessingStatus.DISABLED.value, "count": 0 } for i in range(1, 11) }
                return { "type": "processing_status", "data": { "statuses": default_statuses, "timestamp": datetime.now().isoformat() } }
        except Exception as e:
             logger.error(f"Error checking share connection for processing status: {e}", exc_info=True)
             default_statuses = { f"H{i}": { "status": ProcessingStatus.DISABLED.value, "count": 0 } for i in range(1, 11) }
             return { "type": "processing_status", "data": { "statuses": default_statuses, "timestamp": datetime.now().isoformat() } }

        loop = asyncio.get_event_loop()
        try:
            # Fetch current states from Redis before running in executor
            current_states = self._get_all_monitoring_states_sync()
            statuses = await loop.run_in_executor( None, self.file_monitor.get_all_processing_states, current_states )
        except Exception as e:
             logger.error(f"Error getting processing states: {e}", exc_info=True)
             statuses = { f"H{i}": { "status": ProcessingStatus.DISABLED.value, "count": 0 } for i in range(1, 11) }

        return {
            "type": "processing_status",
            "data": { "statuses": statuses, "timestamp": datetime.now().isoformat() }
        }

    async def get_all_data(self) -> Dict[str, Any]:
        """Get all data for the frontend."""
        # Define default empty data structure first
        default_data = {
            "file_counts": {"counts": [], "total": 0},
            "pi_status": {"statuses": {}},
            "pi_statistics": {"sent": [], "tagged": [], "bibs": [], "totals": [0, 0, 0]},
            "pi_monitor": {"data": []},
            "success_rates": {"cv_rate": 0, "bib_rate": 0},
            "processing_status": {"statuses": {}},
            "timestamp": datetime.now().isoformat()
        }
        try:
            # Ensure pi_status runs first to fetch and store latest status/monitor data
            pi_status = await self.get_pi_status()

            # Now run other tasks in parallel, they can use stored data if needed
            file_counts_task = asyncio.create_task(self.get_file_counts())
            # Fetch current states from Redis before running sync function in executor
            current_states_stats = self._get_all_monitoring_states_sync()
            pi_statistics_task = asyncio.get_event_loop().run_in_executor(None, self._get_pi_statistics_sync, current_states_stats)
            pi_monitor_task = asyncio.create_task(self.get_pi_monitor()) # Reads stored data
            success_rates_task = asyncio.create_task(self.get_success_rates())
            processing_status_task = asyncio.create_task(self.get_processing_status())

            # Wait for the remaining tasks to complete
            file_counts = await file_counts_task
            pi_statistics_result = await pi_statistics_task
            pi_monitor = await pi_monitor_task
            success_rates = await success_rates_task
            processing_status = await processing_status_task

            logger.debug("Sending all data to client")

            # Combine all data safely
            combined_data = {
                "file_counts": file_counts.get("data", default_data["file_counts"]),
                "pi_status": pi_status.get("data", default_data["pi_status"]),
                "pi_statistics": pi_statistics_result if pi_statistics_result is not None else default_data["pi_statistics"],
                "pi_monitor": pi_monitor.get("data", default_data["pi_monitor"]),
                "success_rates": success_rates.get("data", default_data["success_rates"]),
                "processing_status": processing_status.get("data", default_data["processing_status"]),
                "timestamp": datetime.now().isoformat()
            }

            return { "type": "all_data", "data": combined_data }

        except (ApiConnectionError, ApiTimeoutError, ApiResponseError, ShareConnectionError, FileMonitorError) as fm_error:
            logger.error(f"FileMonitor error getting all data: {type(fm_error).__name__} - {str(fm_error)}")
            error_message = f"{type(fm_error).__name__}: {str(fm_error)}"
            # Return default empty data structure with error message
            error_data = default_data.copy()
            error_data["error"] = error_message
            return { "type": "all_data", "data": error_data }
        except Exception as e:
            logger.error(f"Unexpected error getting all data: {str(e)}", exc_info=True)
            # Return default empty data structure with error message
            error_data = default_data.copy()
            error_data["error"] = str(e)
            return { "type": "all_data", "data": error_data }
