# main_window.py - The main application window for Music Library Profiler.
from PyQt6.QtWidgets import (QMainWindow, QLabel, QPushButton, QVBoxLayout, 
                             QWidget, QProgressBar, QScrollArea)
from PyQt6.QtGui import QIcon, QFont
from PyQt6.QtCore import Qt, QThread

from core.config_manager import ConfigManager
from core.database import Database
from core.track_similarity import TrackSimilarity
import utils.resource_manager as rm
from widgets.directory_selector import DirectorySelector
from widgets.scrollable_tracklist import DynamicScrollWidget
from workers.scan_worker import ScanWorker

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

#TODO: Implement feature for choosing a song to compare similarity to

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.database = Database()
        self.config = ConfigManager()
        self.track_similairty = TrackSimilarity(self.database)
        self._init_ui()
        self._load_config()
    
    def _init_ui(self):
        """Initialize the main window UI components."""
        self.setWindowTitle("Music Library Profiler")
        self.statusBar().showMessage("Ready")

        #TODO: Replace this with the track similarity button, this is purely for debug purposes
        self.track_similairty.find_similar_tracks_to("/home/twerp/Music/👁‍🗨📲 - 👁点击と👁/👁‍🗨📲 - 👁点击と👁 - 03 Satya तुम्हारे लिए Incense एक.mp3", 10)
        # Create menu
        # file_menu = self.menuBar().addMenu("File")
        
        # Set window icon
        try:
            icon_path = rm.project_path("assets/icon.png")
            self.setWindowIcon(QIcon(str(icon_path)))
        except Exception as e:
            logger.exception(f"Could not load icon: {e}")
            # Continue without icon
        
        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Welcome label
        label = QLabel("Welcome to Music Library Profiler!")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setFont(QFont("DejaVu Sans", 16, QFont.Weight.Bold))
        layout.addWidget(label)
        
        # Directory selector
        self.directory_selector = DirectorySelector(placeholder="Enter folder path...")
        self.directory_selector.directorySelected.connect(self._on_directory_selected)
        layout.addWidget(self.directory_selector)
        
        # Scan button
        self.scan_button = QPushButton("Scan folder")
        self.scan_button.setFont(QFont("DejaVu Sans", 14))
        self.scan_button.clicked.connect(self._on_scan_clicked)
        layout.addWidget(self.scan_button)

        # Add progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Add status label
        self.status_label = QLabel()
        layout.addWidget(self.status_label)

        # Add scrollable track list
        self.scroll_widget = DynamicScrollWidget(self.database)

        total_height = self.database.count_number_of_tracks() * 40  # item height
        self.scroll_widget.setFixedHeight(total_height)
        
        scroll_area = QScrollArea()
        scroll_area.setWidget(self.scroll_widget)
        scroll_area.setWidgetResizable(True)
        
        # scroll_bar = scroll_area.verticalScrollBar()
        # scroll_bar.setRange(0, self.database.count_number_of_tracks() * 7)
        # scroll_bar.valueChanged.connect(self._on_scroll_value_changed)
        
        layout.addWidget(scroll_area)
        
        # Add stretch to push content to top
        layout.addStretch()
    
    def closeEvent(self, event):
        """Handle window close event to save window geometry."""
        # Save window geometry on close
        self.config.set("window_geometry", [
            self.x(), self.y(), self.width(), self.height()
        ])
        event.accept()
    
    def _load_config(self):
        """Load configuration settings."""
        # Load last directory
        last_directory = self.config.get("last_directory")
        if last_directory:
            self.directory_selector.set_directory(last_directory)
        # Load saved window geometry
        geometry = self.config.get("window_geometry")
        if geometry:
            self.setGeometry(*geometry)
    
    def _on_directory_selected(self, directory):
        """Handle directory selection."""
        if directory:
            self.statusBar().showMessage(f"Directory selected: {directory}")
    
    def _on_scan_clicked(self):
        """Handle scan button click."""
        directory = self.directory_selector.get_directory()
        if not directory:
            self.statusBar().showMessage("Please select a directory first!")
            return
        
        # Save directory to config
        self.config.set("last_directory", directory)
        
        self.statusBar().showMessage(f"Scanning directory: {directory}")
        logger.info(f"Starting scan of: {directory}")  # Replace with actual scanning logic
        self.status_label.setText("Scanning in progress...")
        
        # Initialize scanner and worker thread
        self.scan_worker = ScanWorker(directory=Path(directory), database=self.database, track_similarity=self.track_similairty)

        self.scan_thread = QThread()
        self.scan_worker.moveToThread(self.scan_thread)

        # Connect signals
        self.scan_worker.progress.connect(self._on_scan_progress)
        self.scan_worker.finished.connect(self._on_scan_finished)
        self.scan_worker.error.connect(self._on_scan_error)
        
        # Start thread
        self.scan_thread.started.connect(self.scan_worker.scan)
        self.scan_thread.start()
        self._set_scan_ui_state(scanning=True)

    def _on_scan_progress(self, current: int, total: int, message: str):
        """Update progress from worker thread"""
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.status_label.setText(message)

    def _on_scan_finished(self, results):
        """Handle completion of the scan."""
        # Clean up thread and update UI
        self._cleanup_scan_thread()
        self._set_scan_ui_state(scanning=False)
        self.status_label.setText("Finished scanning.")
        
        # Show results
        self.statusBar().showMessage(
            f"Scan complete! Processed {len(results['successful_files'])}/{results['total_files']} files"
        )
        
        # Export results
        # output_path = Path.home() / "music_library_export.json"
        # if self.scanner.export_results(output_path):
        #     logger.info(f"Results exported to {output_path}")

        for error in results["errors"]:
            logger.warning(error)

    def _on_scan_error(self, error_message: str):
        """Handle scan errors"""
        self._cleanup_scan_thread()
        self._set_scan_ui_state(scanning=False)
        self.statusBar().showMessage(f"Error: {error_message}")
        self.status_label.setText("Scanning error.")

    def _cleanup_scan_thread(self):
        """Clean up thread resources"""
        if self.scan_thread:
            self.scan_thread.quit()
            self.scan_thread.wait()
            self.scan_thread.deleteLater()
            self.scan_thread = None
        self.scan_worker = None
    
    def _set_scan_ui_state(self, scanning: bool):
        """Update UI state based on scanning status"""
        self.scan_button.setEnabled(not scanning)
        self.progress_bar.setVisible(scanning)
        # self.cancel_button.setVisible(scanning)  # TODO: Add cancel button