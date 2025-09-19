# main.py - Entry point for the Music Library Profiler application.
import sys
from PyQt6.QtWidgets import QApplication
from main_window import MainWindow
import logging

def main():
    app = QApplication(sys.argv)
    
    # Set application details for QSettings if used elsewhere
    app.setOrganizationName("Twerp")
    app.setApplicationName("MusicLibraryProfiler")

    logging.basicConfig(level=logging.INFO,  # Set the minimum level to INFO
                    format='%(asctime)s - %(levelname)s - %(message)s')
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()