import asyncio
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

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
        statuses = await loop.run_in_executor(None, self.file_monitor.check_pi_status)
        
        return {
            "type": "pi_status",
            "data": {
                "statuses": statuses,
                "timestamp": datetime.now().isoformat()
            }
        }
    
    async def get_pi_statistics(self) -> Dict[str, Any]:
        """Get statistics for all Pi devices."""
        if not self.file_monitor.is_connected():
            return {
                "type": "pi_statistics",
                "data": {
                    "sent": [],
                    "tagged": [],
                    "bibs": [],
                    "totals": [0, 0, 0],
                    "timestamp": datetime.now().isoformat()
                }
            }
        
        # Run in a thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, self._get_pi_statistics_sync)
        
        return {
            "type": "pi_statistics",
            "data": {
                "sent": result["sent"],
                "tagged": result["tagged"],
                "bibs": result["bibs"],
                "totals": result["totals"],
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
        monitor_data = await loop.run_in_executor(None, self._get_pi_monitor_sync)
        
        return {
            "type": "pi_monitor",
            "data": {
                "data": monitor_data,
                "timestamp": datetime.now().isoformat()
            }
        }
    
    def _get_pi_monitor_sync(self) -> List[Dict[str, Any]]:
        """Synchronous version of get_pi_monitor."""
        # This is a bit of a hack since we don't have direct access to the monitoring data
        # In a real implementation, we would refactor the file_monitor to provide this data directly
        statuses = self.file_monitor.check_pi_status()
        
        # The check_pi_status method updates the UI with monitoring data
        # We need to extract this data from somewhere else or modify the file_monitor
        # For now, we'll return a simplified version
        monitor_data = []
        for pi_name, is_online in statuses.items():
            # Skip if monitoring is disabled
            if not self.monitoring_states.get(pi_name, True):
                monitor_data.append({
                    "device": pi_name,
                    "processed": 0,
                    "uploaded": 0
                })
                continue
            
            if is_online:
                # Get data from the statistics API
                total_images = self.file_monitor.get_pi_total_images(pi_name)
                # For uploaded, we'll use a placeholder
                # In a real implementation, we would get this from the file_monitor
                monitor_data.append({
                    "device": pi_name,
                    "processed": total_images,
                    "uploaded": total_images  # Placeholder
                })
            else:
                monitor_data.append({
                    "device": pi_name,
                    "processed": 0,
                    "uploaded": 0
                })
        
        return monitor_data
    
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
        """Get processing status for all Pi devices."""
        # This is a placeholder since we don't have direct access to the processing status
        # In a real implementation, we would refactor the file_monitor to provide this data directly
        if not self.file_monitor.is_connected():
            return {
                "type": "processing_status",
                "data": {
                    "statuses": {},
                    "timestamp": datetime.now().isoformat()
                }
            }
        
        # For now, we'll return a simplified version based on the total images
        statuses = {}
        for i in range(1, 11):
            pi_name = f"H{i}"
            
            # Skip if monitoring is disabled
            if not self.monitoring_states.get(pi_name, True):
                statuses[pi_name] = {"status": "disabled", "count": 0}
                continue
            
            # Get total images
            total_images = self.file_monitor.get_pi_total_images(pi_name)
            
            # Determine status based on total images
            # This is a simplified version of the logic in the UI
            if total_images > 0:
                statuses[pi_name] = {"status": "processing", "count": total_images}
            else:
                statuses[pi_name] = {"status": "waiting", "count": 0}
        
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
            pi_statistics_task = asyncio.create_task(self.get_pi_statistics())
            pi_monitor_task = asyncio.create_task(self.get_pi_monitor())
            success_rates_task = asyncio.create_task(self.get_success_rates())
            processing_status_task = asyncio.create_task(self.get_processing_status())
            
            # Wait for all tasks to complete
            file_counts = await file_counts_task
            pi_status = await pi_status_task
            pi_statistics = await pi_statistics_task
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
                    "pi_statistics": pi_statistics["data"],
                    "pi_monitor": pi_monitor["data"],
                    "success_rates": success_rates["data"],
                    "processing_status": processing_status["data"],
                    "timestamp": datetime.now().isoformat()
                }
            }
        except Exception as e:
            logger.error(f"Error getting all data: {str(e)}")
            # Return empty data on error
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
