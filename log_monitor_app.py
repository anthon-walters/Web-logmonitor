import tkinter as tk
import logging
import sys
from typing import Optional
from ui import UI
from log_monitor import LogMonitor

class LogMonitorApp:
    """Main application class for the Log Monitor."""
    
    def __init__(self):
        self.logger = logging.getLogger('LogMonitorApp')
        
        # Create main window
        self.root = tk.Tk()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Create UI
        self.ui = UI(self.root)
        
        # Create log monitor
        self.log_monitor = LogMonitor(self.ui)
        
        # Initialize state
        self.running = False
    
    def start(self) -> None:
        """Start the application."""
        try:
            self.logger.info("Starting Log Monitor")
            
            # Start monitoring
            self.running = True
            self.log_monitor.start_monitoring()
            
            # Start UI
            self.root.mainloop()
            
        except Exception as e:
            self.logger.error(f"Error starting monitoring: {str(e)}")
            self.logger.error("Traceback:", exc_info=True)
            self.stop()
    
    def stop(self) -> None:
        """Stop the application."""
        try:
            self.logger.info("Stopping Log Monitor")
            
            # Stop monitoring
            if hasattr(self, 'log_monitor'):
                self.log_monitor.stop_monitoring()
            
            self.running = False
            
            # Stop UI
            if hasattr(self, 'root'):
                self.root.quit()
            
        except Exception as e:
            self.logger.error(f"Error stopping monitoring: {str(e)}")
            self.logger.error("Traceback:", exc_info=True)
    
    def on_closing(self) -> None:
        """Handle window closing."""
        self.logger.info("Window closing")
        self.stop()

def setup_logging() -> None:
    """Set up logging configuration."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )

def main() -> None:
    """Main entry point."""
    # Set up logging
    setup_logging()
    
    # Create and start application
    app = LogMonitorApp()
    app.start()

if __name__ == "__main__":
    main()
