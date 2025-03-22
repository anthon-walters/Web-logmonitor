import os
import threading
import time
import logging
import platform
from typing import Dict, List, Tuple
import asyncio
from ui import UI
from config import (
    FILE_COUNT_UPDATE_INTERVAL,
    FILES_PROCESSED_UPDATE_INTERVAL,
    PI_MONITOR_UPDATE_INTERVAL,
    PI_STATUS_UPDATE_INTERVAL
)

# Import platform-specific file monitor
if platform.system() == 'Windows':
    from windows_file_monitor import FileMonitor
else:
    from file_monitor import FileMonitor

class LogMonitor:
    """Monitor log files on a Samba share."""
    
    def __init__(self, ui_updater: UI):
        self.logger = logging.getLogger('LogMonitor')
        self.ui_updater = ui_updater
        self.stop_event = threading.Event()
        self.file_monitor = FileMonitor()
        
        # Set UI instance in file monitor
        self.file_monitor.set_ui(ui_updater)
        
        # Event loop for async operations
        self.loop = None
        self.async_thread = None
        
        if self.file_monitor.is_connected():
            self.logger.info("LogMonitor initialized - Connected to share")
        else:
            self.logger.warning("LogMonitor initialized - Share not accessible")

    def _run_async_loop(self):
        """Run the async event loop in a separate thread."""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        try:
            # Keep the event loop running until stop is requested
            while not self.stop_event.is_set():
                self.loop.run_until_complete(asyncio.sleep(1))
        except Exception as e:
            self.logger.error(f"Error in async loop: {str(e)}", exc_info=True)
        finally:
            self.loop.close()

    def start_monitoring(self) -> None:
        """Start all monitoring threads."""
        self.logger.info("Starting monitoring threads")
        
        # Start async operations in a separate thread
        self.async_thread = threading.Thread(target=self._run_async_loop, daemon=True)
        self.async_thread.start()
        
        # Start all monitoring threads
        self._start_thread(self.monitor_file_counts)
        self._start_thread(self.monitor_files_processed)
        self._start_thread(self.monitor_pi_status)
        self._start_thread(self.monitor_success_rates)

    def _start_thread(self, target: callable, *args) -> None:
        """Start a new monitoring thread."""
        thread = threading.Thread(target=target, args=args, daemon=True)
        thread.start()

    def stop_monitoring(self) -> None:
        """Stop all monitoring threads."""
        self.logger.info("Stopping monitoring")
        self.stop_event.set()
        
        # Clean up file monitor resources
        if hasattr(self, 'file_monitor'):
            self.file_monitor.cleanup()
            self.logger.info("Cleaned up file monitor resources")
        
        # Stop the async event loop
        if self.loop and self.loop.is_running():
            self.loop.stop()
            self.logger.info("Stopped async event loop")

    def monitor_file_counts(self) -> None:
        """Monitor file counts."""
        while not self.stop_event.is_set():
            if not self.file_monitor.is_connected():
                self.ui_updater.update_file_count_widget([], 0)
                time.sleep(FILE_COUNT_UPDATE_INTERVAL)
                continue
            
            try:
                # Count JPG files in each Pi directory
                jpg_counts = []
                total_files = 0
                
                # Explicitly check each device directory (H1 through H10)
                for i in range(1, 11):
                    pi_name = f"H{i}"
                    
                    # Skip if monitoring is disabled for this Pi
                    if not self.ui_updater.monitoring_states.get(pi_name, True):
                        self.logger.debug(f"Skipping {pi_name} - monitoring disabled")
                        continue
                    
                    self.logger.debug(f"Checking directory: {pi_name}")
                    
                    # Count JPG files in this Pi directory
                    count = self.file_monitor.count_files(pi_name, '.JPG')
                    jpg_counts.append((pi_name, count))
                    total_files += count
                    
                    self.logger.debug(f"Found {count} JPG files in {pi_name}")
                
                self.logger.info(f"Total JPG files across monitored Pi directories: {total_files}")
                self.ui_updater.update_file_count_widget(jpg_counts, total_files)
                
            except Exception as e:
                self.logger.error(f"Error monitoring file counts: {str(e)}")
                
            time.sleep(FILE_COUNT_UPDATE_INTERVAL)

    def monitor_files_processed(self) -> None:
        """Monitor processed files and processing status."""
        while not self.stop_event.is_set():
            if not self.file_monitor.is_connected():
                empty_data = [(f"H{i}", 0) for i in range(1, 11)]
                self.ui_updater.update_files_processed_widget(empty_data, empty_data, empty_data, [0, 0, 0])
                time.sleep(FILES_PROCESSED_UPDATE_INTERVAL)
                continue
            
            try:
                # Get statistics for each Pi
                sent_data = []
                tagged_data = []
                bibs_data = []
                
                for i in range(10):  # For H1 through H10
                    pi_name = f"H{i+1}"
                    
                    # Skip if monitoring is disabled for this Pi
                    if not self.ui_updater.monitoring_states.get(pi_name, True):
                        sent_data.append((pi_name, 0))
                        tagged_data.append((pi_name, 0))
                        bibs_data.append((pi_name, 0))
                        continue
                    
                    # Get total images from central statistics API
                    # This will also update the processing status
                    total_images = self.file_monitor.get_pi_total_images(pi_name)
                    sent_data.append((pi_name, total_images))
                    
                    # Get tagged files from central statistics API
                    tagged_count = self.file_monitor.get_pi_statistics(pi_name)
                    tagged_data.append((pi_name, tagged_count))
                    
                    # Get bib statistics from API
                    bibs_count = self.file_monitor.get_pi_bib_statistics(pi_name)
                    bibs_data.append((pi_name, bibs_count))
                
                totals = [
                    sum(count for _, count in sent_data),
                    sum(count for _, count in tagged_data),
                    sum(count for _, count in bibs_data)
                ]
                
                self.ui_updater.update_files_processed_widget(
                    sent_data, tagged_data, bibs_data, totals
                )
                
            except Exception as e:
                self.logger.error(f"Error monitoring files processed: {str(e)}")
                
            time.sleep(FILES_PROCESSED_UPDATE_INTERVAL)

    def monitor_pi_status(self) -> None:
        """Monitor Raspberry Pi status by checking network connectivity."""
        while not self.stop_event.is_set():
            if not self.file_monitor.is_connected():
                statuses = {f"H{i}": False for i in range(1, 11)}
                self.ui_updater.update_pi_status(statuses)
                time.sleep(PI_STATUS_UPDATE_INTERVAL)
                continue
            
            try:
                # Check each Pi's network connectivity
                statuses = {}
                
                # Only check status for monitored Pis
                for i in range(1, 11):
                    pi_name = f"H{i}"
                    if not self.ui_updater.monitoring_states.get(pi_name, True):
                        statuses[pi_name] = False
                        continue
                        
                    # Get status from file monitor
                    pi_statuses = self.file_monitor.check_pi_status()
                    statuses[pi_name] = pi_statuses.get(pi_name, False)
                    
                    # Log the status update
                    self.logger.debug(f"Pi Status Update - {pi_name}: {'Online' if statuses[pi_name] else 'Offline'}")
                
                # Update the UI with the status information
                self.ui_updater.update_pi_status(statuses)
                
            except Exception as e:
                self.logger.error(f"Error monitoring PI status: {str(e)}")
                # Set all Pis to offline in case of error
                statuses = {f"H{i}": False for i in range(1, 11)}
                self.ui_updater.update_pi_status(statuses)
                
            time.sleep(PI_STATUS_UPDATE_INTERVAL)

    def monitor_success_rates(self) -> None:
        """Monitor CV and bib detection success rates."""
        while not self.stop_event.is_set():
            if not self.file_monitor.is_connected():
                self.ui_updater.update_success_rates(0, 0)
                time.sleep(PI_MONITOR_UPDATE_INTERVAL)
                continue
            
            try:
                # Only get rates for monitored Pis
                cv_rate, bib_rate = self.file_monitor.get_pi_success_rates(
                    [pi for pi, state in self.ui_updater.monitoring_states.items() if state]
                )
                self.ui_updater.update_success_rates(cv_rate, bib_rate)
                
            except Exception as e:
                self.logger.error(f"Error monitoring success rates: {str(e)}")
                
            time.sleep(PI_MONITOR_UPDATE_INTERVAL)
