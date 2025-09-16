# main_window.py - The main application window for Music Library Profiler.
from PyQt6.QtWidgets import QMainWindow, QLabel, QPushButton, QVBoxLayout, QWidget
from PyQt6.QtGui import QIcon, QFont
from PyQt6.QtCore import Qt

from core.config_manager import ConfigManager
from utils.resource_manager import resource_path
from widgets.directory_selector import DirectorySelector

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config = ConfigManager()
        self._init_ui()
        self._load_config()
    
    def _init_ui(self):
        self.setWindowTitle("Music Library Profiler")
        self.statusBar().showMessage("Ready")
        
        # Create menu
        # file_menu = self.menuBar().addMenu("File")
        
        # Set window icon
        try:
            icon_path = resource_path("assets/icon.png")
            self.setWindowIcon(QIcon(str(icon_path)))
        except Exception as e:
            print(f"Could not load icon: {e}")
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
        
        # Add stretch to push content to top
        layout.addStretch()
    
    def _load_config(self):
        # Load last directory
        last_directory = self.config.get("last_directory")
        if last_directory:
            self.directory_selector.set_directory(last_directory)
        # Load saved window geometry
        geometry = self.config.get("window_geometry")
        if geometry:
            self.setGeometry(*geometry)
    
    def _on_directory_selected(self, directory):
        if directory:
            self.statusBar().showMessage(f"Directory selected: {directory}")
    
    def _on_scan_clicked(self):
        directory = self.directory_selector.get_directory()
        if not directory:
            self.statusBar().showMessage("Please select a directory first!")
            return
        
        # Save directory to config
        self.config.set("last_directory", directory)
        
        # TODO: Start the scanning process
        self.statusBar().showMessage(f"Scanning directory: {directory}")
        print(f"Starting scan of: {directory}")  # Replace with actual scanning logic
    
    def closeEvent(self, event):
        # Save window geometry on close
        self.config.set("window_geometry", [
            self.x(), self.y(), self.width(), self.height()
        ])
        event.accept()