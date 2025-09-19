# workers/scan_worker.py
from PyQt6.QtCore import QObject, pyqtSignal
from pathlib import Path
from typing import Callable

from core.scanner import Scanner

class ScanWorker(QObject):
    """Worker for scanning music files in background thread"""
    
    # Signals for communication with main thread
    progress = pyqtSignal(int, int, str)  # current, total, message
    finished = pyqtSignal(dict)           # results dictionary
    error = pyqtSignal(str)               # error message
    
    def __init__(self, directory: Path):
        """Initialize worker with scanner and directory (main thread)"""
        super().__init__()
        self.scanner = Scanner(directory)
        self.scanner.set_progress_callback(self._on_progress)
        self.directory = directory
        self._is_cancelled = False
    
    def scan(self):
        """Worker's main scanning method (own thread) """
        try:
            if not self.scanner or not self.directory:
                self.error.emit("Worker not properly initialized")
                return
            
            results = self.scanner.scan_directory()
            if not self._is_cancelled:
                self.finished.emit(results)
                
        except Exception as e:
            if not self._is_cancelled:
                self.error.emit(f"Scan error: {str(e)}")
    
    def cancel(self):
        """Request cancellation"""
        self._is_cancelled = True
        if self.scanner:
            #TODO: Add cancel method to scanner
            pass
    
    def _on_progress(self, current: int, total: int, message: str):
        """Forward progress updates to main thread"""
        if not self._is_cancelled:
            self.progress.emit(current, total, message)