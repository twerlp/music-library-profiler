# main_window.py - The main application window for Music Library Profiler.
from PyQt6.QtWidgets import QMainWindow, QLabel, QPushButton, QVBoxLayout, QWidget, QProgressBar
from PyQt6.QtGui import QIcon, QFont
from PyQt6.QtCore import Qt, QThread

from core.config_manager import ConfigManager
import utils.resource_manager as rm
from widgets.directory_selector import DirectorySelector
from core.scanner import Scanner
from workers.scan_worker import ScanWorker

import logging
from pathlib import Path

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config = ConfigManager()
        self._init_ui()
        self._load_config()
    
    def _init_ui(self):
        """Initialize the main window UI components."""
        self.setWindowTitle("Music Library Profiler")
        self.statusBar().showMessage("Ready")
        
        # Create menu
        # file_menu = self.menuBar().addMenu("File")
        
        # Set window icon
        try:
            icon_path = rm.project_path("assets/icon.png")
            print(icon_path)
            self.setWindowIcon(QIcon(str(icon_path)))
        except Exception as e:
            logging.exception(f"Could not load icon: {e}")
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
        logging.info(f"Starting scan of: {directory}")  # Replace with actual scanning logic
        self.status_label.setText("Scanning in progress...")
        
        # Initialize scanner and worker thread
        self.scan_worker = ScanWorker(Path(directory))

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
            f"Scan complete! Processed {results['successful_files']}/{results['total_files']} files"
        )
        
        # Export results
        # output_path = Path.home() / "music_library_export.json"
        # if self.scanner.export_results(output_path):
        #     print(f"Results exported to {output_path}")

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
        # self.cancel_button.setVisible(scanning)  # Add cancel button