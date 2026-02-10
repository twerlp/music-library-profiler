# scan_dialog.py - The window for scan management.

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QProgressBar
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QIcon, QFont

from widgets.directory_selector import DirectorySelector
from core.config_manager import ConfigManager
from workers.scan_worker import ScanWorker

from pathlib import Path
import logging
logger = logging.getLogger(__name__)

#TODO: Status bar for the scan dialog, also add a cancel button to stop the scan if needed. Also add an export button to export results after the scan is done. Also add a way to view errors that occurred during the scan.
#TODO: Hook progress bar into main window

class ScanWindow(QDialog):
    scan_start = pyqtSignal(str)  # Signal to start scan with selected directory
    scan_finish = pyqtSignal(dict)  # Signal emitted when scan finishes with results
    scan_error = pyqtSignal(str)  # Signal emitted when an error occurs during scanning
    scan_progress = pyqtSignal(int, int, str)  # Signal for scan progress updates (current, total, message)

    def __init__(self, parent, config=None, database=None, track_similarity=None):
        super().__init__(parent)
        print("parent:", parent)
        self.setWindowTitle("Scan Manager")
        self.setModal(False)
        self.resize(400, 200)

        self.config = config
        self.database = database
        self.track_similarity = track_similarity

        layout = QVBoxLayout(self)

        # Directory selector
        self.directory_selector = DirectorySelector(placeholder="Enter folder path...")
        layout.addWidget(self.directory_selector)

        # Add progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Add status label
        self.status_label = QLabel()
        layout.addWidget(self.status_label)

        # Scan button
        self.scan_button = QPushButton("Scan folder")
        self.scan_button.setFont(QFont("DejaVu Sans", 14))
        self.scan_button.clicked.connect(self._on_scan_clicked)
        layout.addWidget(self.scan_button)

        self._load_config()


    def _on_scan_clicked(self):
        """Handle scan button click."""
        directory = self.directory_selector.get_directory()
        if not directory:
            self.status_label.setText("Select a valid directory.")
            return
        
        self.status_label.setText("Scanning in progress...")
        
        # Initialize scanner and worker thread
        self.scan_worker = ScanWorker(directory=Path(directory), database=self.database, track_similarity=self.track_similarity)

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

        self.scan_start.emit(directory)  # Emit signal to start scan in main thread

    def _on_scan_progress(self, current: int, total: int, message: str):
        """Update progress from worker thread"""
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.status_label.setText(message)

        self.scan_progress.emit(current, total, message)  # Emit progress signal to main thread

    def _on_scan_finished(self, results):
        """Handle completion of the scan."""
        # Clean up thread and update UI
        self._cleanup_scan_thread()
        self._set_scan_ui_state(scanning=False)
        self.status_label.setText("Finished scanning.")

        self.scan_finish.emit(results)  # Emit results to main thread

        for error in results["errors"]:
            logger.warning(error)

    def _on_scan_error(self, error_message: str):
        """Handle scan errors"""
        self._cleanup_scan_thread()
        self._set_scan_ui_state(scanning=False)
        self.status_label.setText("Scanning error.")
        self.scan_error.emit(error_message)  # Emit error to main thread

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
    
    def _load_config(self):
        """Load configuration settings."""
        # Load last directory
        last_directory = self.config.get("last_directory")
        if last_directory:
            self.directory_selector.set_directory(last_directory)
            
