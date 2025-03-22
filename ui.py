import tkinter as tk
from tkinter import ttk, scrolledtext
import logging
import requests
from typing import List, Tuple, Dict, Any
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from datetime import datetime, timedelta
from config import (
    WINDOW_TITLE,
    WINDOW_SIZE,
    FILE_COUNT_COLUMNS,
    PI_MONITOR_COLUMNS,
    TITLE_FONT,
    SUBTITLE_FONT,
    TEXT_FONT,
    STATUS_COUNT_FONT,
    LOG_WIDGET_WIDTH,
    LOG_WIDGET_HEIGHT,
    MAX_LOG_LINES,
    PI_STATUS_FONT,
    PI_STATUS_LED_SIZE,
    PI_MONITOR_DEBUG,
    STATUS_RECT_WIDTH,
    STATUS_RECT_HEIGHT,
    STATUS_GRID_COLUMNS,
    STATUS_GRID_ROWS,
    STATUS_UPDATE_CHECK_INTERVAL,
    STATUS_STALE_THRESHOLD,
    STATUS_FLASH_INTERVAL,
    STATUS_PROCESSED_THRESHOLD,
    API_USERNAME,
    API_PASSWORD
)

# Button colors removed

class ProcessingStatus:
    PROCESSING = "red"
    WAITING = "yellow"
    DONE = "green"
    
    @staticmethod
    def get_flash_color(status: str) -> str:
        """Get the alternate color for flashing state."""
        flash_colors = {
            ProcessingStatus.PROCESSING: "darkred",
            ProcessingStatus.WAITING: "gold",
            ProcessingStatus.DONE: "darkgreen"
        }
        return flash_colors.get(status, status)

class UI:
    def __init__(self, master: tk.Tk):
        self.logger = logging.getLogger('UI')
        self.master = master
        self.master.title(WINDOW_TITLE)
        
        # Calculate the new window size (2/3 of the original size)
        original_width, original_height = map(int, WINDOW_SIZE.split('x'))
        new_width = int(original_width * 2 / 3)
        new_height = int(original_height * 2 / 3)
        self.master.geometry(f"{new_width}x{new_height}")
        
        # Initialize status tracking
        self.status_timestamps = {}  # Track last update time for each Pi
        self.status_counts = {}      # Track count for each Pi
        self.flashing_states = {}    # Track flashing state for each Pi
        self.monitoring_states = {}  # Track monitoring state for each Pi
        
        self.create_widgets()
        
        # Start the status update checker
        self.check_status_updates()

    def create_widgets(self) -> None:
        self.logger.info("Creating widgets")
        
        # Create main frames with emphasis on top row (2:1 ratio)
        self._configure_grid(self.master, [1], [2, 1])  # 2:1 ratio for top and bottom sections
        
        # Create top frame for main widgets (more prominent)
        top_frame = ttk.Frame(self.master)
        top_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self._configure_grid(top_frame, [1, 1, 1, 1, 1], [1])  # 5 equal columns

        # Create main widgets in top frame
        self.file_count_frame, self.file_count_tree = self._create_file_count_frame(top_frame, 0)
        self.sent_frame, self.sent_tree, self.sent_title = self._create_status_frame(top_frame, "Sent for Tagging", 1)
        self.tagged_frame, self.tagged_tree, self.tagged_title = self._create_status_frame(top_frame, "JPG files tagged", 2)
        self.unread_frame, self.unread_tree, self.unread_title = self._create_status_frame(top_frame, "Bibs found", 3)
        self.pi_monitor_frame, self.pi_monitor_tree = self._create_pi_monitor_frame(top_frame, 4)

        # Create bottom frame for processing status and charts
        bottom_frame = ttk.Frame(self.master)
        bottom_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self._configure_grid(bottom_frame, [3, 1], [1])  # 3:1 ratio for status and charts

        # Create processing status frame
        status_frame = ttk.Frame(bottom_frame)
        status_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self._configure_grid(status_frame, [1], [1])  # Single cell for the grid
        self.processing_frames, self.processing_indicators = self._create_processing_status_widgets(status_frame)

        # Create right side frame for status and charts
        right_frame = ttk.Frame(bottom_frame)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        self._configure_grid(right_frame, [1], [1, 1])  # Equal space for status and charts

        # Create PI status display
        self.pi_status_frame, self.pi_status_widgets = self._create_pi_status_display(right_frame)
        
        # Create charts frame (smaller)
        self.charts_frame = self._create_charts_frame(right_frame)

    # Button press handler removed

    def _configure_grid(self, frame: ttk.Frame, column_weights: List[int], row_weights: List[int]) -> None:
        for i, weight in enumerate(column_weights):
            frame.columnconfigure(i, weight=weight)
        for i, weight in enumerate(row_weights):
            frame.rowconfigure(i, weight=weight)

    def _create_file_count_frame(self, parent: ttk.Frame, column: int) -> Tuple[ttk.Frame, ttk.Treeview]:
        frame = ttk.Frame(parent, borderwidth=2, relief="groove")
        frame.grid(row=0, column=column, padx=5, pady=5, sticky="nsew")
    
        self.file_count_title = ttk.Label(frame, text="Overall total JPG files: 0", font=TITLE_FONT)
        self.file_count_title.pack(side="top", fill="x", padx=5, pady=5)
    
        tree = self._create_treeview(frame, FILE_COUNT_COLUMNS, height=5)
        return frame, tree

    def _create_status_frame(self, parent: ttk.Frame, title: str, column: int) -> Tuple[ttk.Frame, ttk.Treeview, ttk.Label]:
        frame = ttk.Frame(parent, borderwidth=2, relief="groove")
        frame.grid(row=0, column=column, padx=5, pady=5, sticky="nsew")
        
        label = ttk.Label(frame, text=f"{title}: 0", font=TITLE_FONT)
        label.pack(side="top", fill="x", padx=5, pady=5)
        
        columns = [{'name': 'Devices', 'width': 80, 'anchor': 'center'},
                   {'name': 'Count', 'width': 80, 'anchor': 'center'}]
        tree = self._create_treeview(frame, columns, height=5)
        
        return frame, tree, label

    def _create_pi_monitor_frame(self, parent: ttk.Frame, column: int) -> Tuple[ttk.Frame, ttk.Treeview]:
        frame = ttk.Frame(parent, borderwidth=2, relief="groove")
        frame.grid(row=0, column=column, padx=5, pady=5, sticky="nsew")
        
        self.pi_monitor_title = ttk.Label(frame, text="Field Device Status", font=TITLE_FONT)
        self.pi_monitor_title.pack(side="top", fill="x", padx=5, pady=5)
        
        tree = self._create_treeview(frame, PI_MONITOR_COLUMNS, height=5)
        return frame, tree

    def _create_treeview(self, parent: ttk.Frame, columns: List[Dict[str, Any]], height: int) -> ttk.Treeview:
        tree = ttk.Treeview(parent, columns=[col['name'] for col in columns], show='headings', height=height)
        for col in columns:
            tree.heading(col['name'], text=col['name'])
            tree.column(col['name'], width=col['width'], anchor=col['anchor'])
        
        tree.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
        scrollbar.pack(side="right", fill="y")
        tree.configure(yscrollcommand=scrollbar.set)
        
        return tree

    def _create_pi_status_display(self, parent: ttk.Frame) -> Tuple[ttk.Frame, Dict[str, Tuple[ttk.Label, tk.Canvas, ttk.Scale]]]:
        frame = ttk.Frame(parent, borderwidth=2, relief="groove")
        frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        # Create title frame to hold title and legend
        title_frame = ttk.Frame(frame)
        title_frame.pack(side="top", fill="x", padx=5, pady=5)

        # Add title
        title = ttk.Label(title_frame, text="Devices Online", font=TITLE_FONT)
        title.pack(side="left", padx=5)

        # No legend needed

        status_widgets = {}
        style = ttk.Style()
        style.configure("Switch.TCheckbutton", padding=2)

        for i in range(1, 11):
            pi_name = f"H{i}"
            pi_frame = ttk.Frame(frame)
            pi_frame.pack(fill="x", padx=5, pady=2)

            # Pi label
            label = ttk.Label(pi_frame, text=pi_name, font=PI_STATUS_FONT, width=5, anchor="w")
            label.pack(side="left")

            # Monitoring switch
            var = tk.BooleanVar(value=True)
            self.monitoring_states[pi_name] = True
            switch = ttk.Checkbutton(pi_frame, style="Switch.TCheckbutton", 
                                   variable=var, 
                                   command=lambda p=pi_name, v=var: self._toggle_monitoring(p, v))
            switch.pack(side="left", padx=5)

            # No buttons needed

            # Status LED
            canvas = tk.Canvas(pi_frame, width=PI_STATUS_LED_SIZE, height=PI_STATUS_LED_SIZE, 
                             highlightthickness=0)
            canvas.pack(side="right", padx=2)
            
            # Draw initial status indicator
            canvas.delete("all")
            canvas.create_oval(2, 2, PI_STATUS_LED_SIZE-2, PI_STATUS_LED_SIZE-2, 
                             fill="red", outline="")

            status_widgets[pi_name] = (label, canvas, switch)

        return frame, status_widgets

    def _create_processing_status_widgets(self, parent: ttk.Frame) -> Tuple[List[ttk.Frame], Dict[str, Tuple[ttk.Label, tk.Canvas, ttk.Label]]]:
        """Create processing status widgets in a 5x2 grid."""
        container = ttk.Frame(parent)
        container.pack(expand=True, fill="both", padx=5, pady=5)
        
        # Configure grid
        for i in range(STATUS_GRID_COLUMNS):
            container.columnconfigure(i, weight=1)
        for i in range(STATUS_GRID_ROWS + 1):  # +1 for legend
            container.rowconfigure(i, weight=1)
            
        frames = []
        indicators = {}
        
        # Create legend at the top
        legend_frame = ttk.Frame(container)
        legend_frame.grid(row=0, column=0, columnspan=STATUS_GRID_COLUMNS, sticky="ew", padx=5, pady=5)
        
        ttk.Label(legend_frame, text="Status Legend:", font=SUBTITLE_FONT).pack(side="left", padx=10)
        for status, color, text in [
            (ProcessingStatus.PROCESSING, "red", "Processing"),
            (ProcessingStatus.WAITING, "yellow", "Waiting"),
            (ProcessingStatus.DONE, "green", "Done")
        ]:
            frame = ttk.Frame(legend_frame)
            frame.pack(side="left", padx=5)
            canvas = tk.Canvas(frame, width=15, height=15, highlightthickness=0)
            canvas.create_rectangle(0, 0, 15, 15, fill=color, outline="")
            canvas.pack(side="left")
            ttk.Label(frame, text=text).pack(side="left", padx=(2, 10))

        # Create status rectangles
        for i in range(10):  # H1 to H10
            row = (i // STATUS_GRID_COLUMNS) + 1  # +1 to account for legend
            col = i % STATUS_GRID_COLUMNS
            pi_name = f"H{i+1}"  # Ensure correct Pi numbering
            
            frame = ttk.Frame(container)
            frame.grid(row=row, column=col, padx=1, pady=1, sticky="nsew")
            frames.append(frame)
            
            # Create canvas with fixed size
            canvas = tk.Canvas(frame, width=STATUS_RECT_WIDTH, height=STATUS_RECT_HEIGHT, 
                             highlightthickness=0)
            canvas.pack(expand=False)  # Don't expand to maintain fixed size
            
            # Create rectangle that fills the entire canvas
            canvas.create_rectangle(0, 0, STATUS_RECT_WIDTH, STATUS_RECT_HEIGHT,
                                 fill=ProcessingStatus.WAITING, outline="", tags="rect")
            
            # Add text centered in the canvas
            canvas.create_text(STATUS_RECT_WIDTH/2, STATUS_RECT_HEIGHT/2,
                             text=f"{pi_name}:0", font=STATUS_COUNT_FONT, 
                             tags=("name", "count"), fill="black", justify="center")
            
            indicators[pi_name] = (None, canvas, None)

        return frames, indicators

    def _create_charts_frame(self, parent: ttk.Frame) -> ttk.Frame:
        frame = ttk.Frame(parent, borderwidth=2, relief="groove")
        frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

        self.fig = Figure(figsize=(2.5, 1))
        
        self.cv_success_ax = self.fig.add_subplot(121)
        self.bib_detection_ax = self.fig.add_subplot(122)
        
        self.fig.subplots_adjust(wspace=0.2,
                               left=0.05,
                               right=0.95,
                               bottom=0.1,
                               top=0.85)
        
        canvas = FigureCanvasTkAgg(self.fig, master=frame)
        canvas.draw()
        canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)
        
        self.chart_canvas = canvas
        
        return frame

    # Clear and Re-insert command functions removed

    def _toggle_monitoring(self, pi_name: str, var: tk.BooleanVar) -> None:
        """Handle toggling of Pi monitoring."""
        is_monitored = var.get()
        self.monitoring_states[pi_name] = is_monitored
        
        if pi_name in self.pi_status_widgets:
            _, canvas, _ = self.pi_status_widgets[pi_name]
            if not is_monitored:
                # Set LED to dark grey when monitoring is disabled
                canvas.delete("all")
                canvas.create_oval(2, 2, PI_STATUS_LED_SIZE-2, PI_STATUS_LED_SIZE-2, fill="darkgrey", outline="")

    def check_status_updates(self) -> None:
        """Check for stale status updates and manage flashing states."""
        current_time = datetime.now()
        pi_processed_values = self._get_pi_processed_values()
        
        for pi_name, (_, canvas, _) in self.processing_indicators.items():
            if pi_name in self.status_timestamps and self.monitoring_states.get(pi_name, True):
                last_update = self.status_timestamps[pi_name]
                time_diff = (current_time - last_update).total_seconds()
                
                # Check if count is stale and if there's a significant difference in processed values
                if (time_diff > STATUS_STALE_THRESHOLD and 
                    pi_name in self.status_counts and 
                    pi_name in pi_processed_values):
                    count_diff = abs(pi_processed_values[pi_name] - self.status_counts[pi_name])
                    
                    if count_diff > STATUS_PROCESSED_THRESHOLD:
                        # Toggle flashing state
                        if pi_name not in self.flashing_states:
                            self.flashing_states[pi_name] = False
                        
                        self.flashing_states[pi_name] = not self.flashing_states[pi_name]
                        current_status = canvas.itemcget("rect", "fill")
                        
                        if self.flashing_states[pi_name]:
                            new_color = ProcessingStatus.get_flash_color(current_status)
                        else:
                            new_color = current_status
                            
                        canvas.itemconfig("rect", fill=new_color)
        
        # Schedule next check
        self.master.after(STATUS_FLASH_INTERVAL, self.check_status_updates)

    def _get_pi_processed_values(self) -> Dict[str, int]:
        """Get the current processed values from the PI monitor widget."""
        processed_values = {}
        for item in self.pi_monitor_tree.get_children():
            values = self.pi_monitor_tree.item(item)['values']
            if values and len(values) > 1:
                pi_name = values[0]
                try:
                    # Handle both string and integer values
                    value = str(values[1])
                    processed = int(value) if value.isdigit() else 0
                    processed_values[pi_name] = processed
                except (ValueError, AttributeError):
                    processed_values[pi_name] = 0
        return processed_values

    def update_pi_status(self, statuses: Dict[str, bool]) -> None:
        """Update the status indicators for each Pi."""
        for pi_name, is_online in statuses.items():
            if pi_name in self.pi_status_widgets:
                _, canvas, _ = self.pi_status_widgets[pi_name]
                
                # Only update color if monitoring is enabled
                if self.monitoring_states.get(pi_name, True):
                    color = "lime" if is_online else "red"
                else:
                    color = "darkgrey"
                
                # Clear and redraw the status indicator
                canvas.delete("all")
                canvas.create_oval(2, 2, PI_STATUS_LED_SIZE-2, PI_STATUS_LED_SIZE-2, 
                                 fill=color, outline="")

    def update_file_count_widget(self, data: List[Tuple[str, int]], total_files: int) -> None:
        self.file_count_title.config(text=f"Overall total JPG files: {total_files}")
        
        # Filter data based on monitoring state
        filtered_data = [(path, count) for path, count in data 
                        if not any(pi_name in path and not self.monitoring_states.get(pi_name, True) 
                                 for pi_name in self.monitoring_states)]
        
        modified_data = [(path.replace("/media/pre-processing/", ""), count) for path, count in filtered_data]
        self._refresh_tree(self.file_count_tree, modified_data)

    def update_files_processed_widget(self, sent_data: List[Tuple[str, int]], 
                                      tagged_data: List[Tuple[str, int]], 
                                      bibs_data: List[Tuple[str, int]], 
                                      totals: List[int]) -> None:
        # Filter data based on monitoring state
        filtered_sent = [(pi, count) for pi, count in sent_data if self.monitoring_states.get(pi, True)]
        filtered_tagged = [(pi, count) for pi, count in tagged_data if self.monitoring_states.get(pi, True)]
        filtered_bibs = [(pi, count) for pi, count in bibs_data if self.monitoring_states.get(pi, True)]
        
        # Calculate new totals based on filtered data
        new_totals = [
            sum(count for _, count in filtered_sent),
            sum(count for _, count in filtered_tagged),
            sum(count for _, count in filtered_bibs)
        ]
        
        self.sent_title.config(text=f"JPG files sent for Tagging: {new_totals[0]}")
        self.tagged_title.config(text=f"JPG files tagged: {new_totals[1]}")
        self.unread_title.config(text=f"Bibs found: {new_totals[2]}")

        self._refresh_tree(self.sent_tree, filtered_sent)
        self._refresh_tree(self.tagged_tree, filtered_tagged)
        self._refresh_tree(self.unread_tree, filtered_bibs)

    def update_pi_monitor_widget(self, data: List[Tuple[str, str, str]]) -> None:
        # Filter data based on monitoring state
        filtered_data = [item for item in data if self.monitoring_states.get(item[0], True)]
        self._refresh_tree(self.pi_monitor_tree, filtered_data)

    def update_success_rates(self, cv_success_rate: float, bib_detection_rate: float) -> None:
        self.cv_success_ax.clear()
        self.bib_detection_ax.clear()
        
        cv_data = [cv_success_rate, 100 - cv_success_rate]
        self.cv_success_ax.pie(cv_data, colors=['green', 'red'], autopct='%1.0f%%',
                              startangle=90, labels=['✓', '✗'],
                              textprops={'fontsize': 5})
        self.cv_success_ax.set_title('CV Success', fontsize=6, pad=1)
        
        bib_data = [bib_detection_rate, 100 - bib_detection_rate]
        self.bib_detection_ax.pie(bib_data, colors=['blue', 'gray'], autopct='%1.0f%%',
                                 startangle=90, labels=['✓', '✗'],
                                 textprops={'fontsize': 5})
        self.bib_detection_ax.set_title('Bib Detection', fontsize=6, pad=1)
        
        self.fig.tight_layout()
        self.chart_canvas.draw()

    def _refresh_tree(self, tree: ttk.Treeview, data: List[Tuple[Any, ...]]) -> None:
        for item in tree.get_children():
            tree.delete(item)
        for entry in data:
            tree.insert('', 'end', values=entry)

    def update_processing_status(self, pi_name: str, status: str, count: int) -> None:
        """Update the processing status for a specific Pi."""
        if pi_name in self.processing_indicators and self.monitoring_states.get(pi_name, True):
            _, canvas, _ = self.processing_indicators[pi_name]
            
            # Update rectangle color
            canvas.itemconfig("rect", fill=status)
            
            # Update text
            canvas.itemconfig("name", text=f"{pi_name}:{count}")
            
            # Update tracking
            self.status_timestamps[pi_name] = datetime.now()
            self.status_counts[pi_name] = count
