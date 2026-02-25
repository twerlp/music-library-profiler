# main_window.py - The main application window for Music Library Profiler.
from PyQt6.QtWidgets import (QMainWindow, QLabel, QPushButton, QVBoxLayout, 
                             QHBoxLayout, QWidget, QProgressBar, QScrollArea, 
                             QMenuBar, QMenu, QSplitter
                             )
from PyQt6.QtGui import QIcon, QFont
from PyQt6.QtCore import Qt, QThread

from core.config_manager import ConfigManager
from core.database import Database
from core.track_similarity import TrackSimilarity
import utils.resource_manager as rm

from widgets.scan_window import ScanWindow
from widgets.file_tree import FileTreeWidget
from widgets.playlist import PlaylistListWidget
from widgets.generated_song_list import GeneratedSongListWidget
from widgets.requested_song_list import RequestedSongListWidget
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
        self.track_similarity = TrackSimilarity(self.database)

        self._init_ui()
        self._init_scan_manager()
        self._load_config()
    
    def _init_ui(self):
        """Initialize the main window UI components."""
        self._set_window_title()
        self._create_menu_bar()
        self.statusBar().showMessage("Ready")

        #TODO: Replace this with the track similarity button, this is purely for debug purposes
        # self.track_similarity.find_similar_tracks_to("/home/twerp/Music/Windows 96 - Dated New Aesthetic/01 - Windows 96 - Nome Da Musica.mp3", 500)
        playlist = self.track_similarity.create_playlist_include_track_direction(
            source_track_path=Path("/home/twerp/Music/Windows 96 - Dated New Aesthetic/01 - Windows 96 - Nome Da Musica.mp3"),
            # destination_track_path=Path("/home/twerp/Music/Judy Collins - Wind Beneath My Wings/04 - Judy Collins - Cats In The Cradle.mp3"),
            destination_track_path=Path("/home/twerp/Music/greenhouse - _SNDWRK-gh/greenhouse - _SNDWRK-gh - 01 国際信号旗K.m4a"),
            num_tracks=10)
        print("Generated playlist:")
        for track in playlist:
            print(self.database.get_track_metadata_by_id(track)["file_path"])
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
        # label = QLabel("Welcome to Music Library Profiler!")
        # label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # label.setFont(QFont("DejaVu Sans", 16, QFont.Weight.Bold))
        # layout.addWidget(label)

        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(main_splitter)

        self.file_tree = FileTreeWidget(self.database)
        main_splitter.addWidget(self.file_tree)

        similar_track_splitter = QSplitter(Qt.Orientation.Vertical)
        main_splitter.addWidget(similar_track_splitter)

        self.similar_track_request_list = RequestedSongListWidget(self)
        similar_track_splitter.addWidget(self.similar_track_request_list)

        self.similar_tracks_generate_list = GeneratedSongListWidget(self)
        similar_track_splitter.addWidget(self.similar_tracks_generate_list)

        self.similar_track_request_list.track_added.connect(self._on_track_added_to_request_list)

        self.similar_track_request_list.add_track(self.database.get_track_metadata_by_id(1))
        self.similar_track_request_list.add_track(self.database.get_track_metadata_by_id(300))
    
    def closeEvent(self, event):
        """Handle window close event to save window geometry."""
        # Save window geometry on close
        self.config.set("window_geometry", [
            self.x(), self.y(), self.width(), self.height()
        ])
        event.accept()

    def _init_scan_manager(self):
        """Initialize the scan manager window."""
        self.scan_manager_window = ScanWindow(self, config=self.config, database=self.database, track_similarity=self.track_similarity)
        self.scan_manager_window.hide()

        self.scan_manager_window.scan_start.connect(self._on_scan_started)
        self.scan_manager_window.scan_progress.connect(self._on_scan_progress)
        self.scan_manager_window.scan_finish.connect(self._on_scan_finished)
        self.scan_manager_window.scan_error.connect(self._on_scan_error)

    def _open_scan_manager(self):
        """Open the scan manager window."""
        if (not self.scan_manager_window.isVisible()):
            self.scan_manager_window.show()
        else:
            self.scan_manager_window.hide()
    
    def _create_menu_bar(self):
        """Menu bar for the application, allows users to edit scan directory, load/save playlists, and access settings."""
        menubar = QMenuBar(self)
        
        scan_menu = QMenu("&Scan", self)
        scan_menu.addAction("Open Scan Manager", self._open_scan_manager)
        menubar.addMenu(scan_menu)

        playlist_menu = QMenu("&Playlists", self)
        # playlist_menu.addAction("Load playlist", self._on_load_playlist_clicked)  # TODO: Implement load playlist functionality
        # playlist_menu.addAction("Save playlist", self._on_save_playlist_clicked)  # TODO: Implement save playlist functionality
        menubar.addMenu(playlist_menu)
        
        settings_menu = QMenu("&Settings", self)
        # settings_menu.addAction("Preferences", self._on_preferences_clicked)  # TODO: Implement preferences dialog
        menubar.addMenu(settings_menu)

        self.setMenuBar(menubar)

    def _on_scan_started(self, directory):
        """Handle the start of a scan."""
        self._on_directory_selected(directory)  # Save selected directory to config
        self.statusBar().showMessage(f"Scanning: {directory}")
    
    def _on_scan_progress(self, current, total, message):
        """Handle scan progress updates."""
        self.statusBar().showMessage(f"Scanning: {message} ({current}/{total})")
    
    def _on_scan_finished(self, results):
        """Handle the completion of a scan."""
        self.statusBar().showMessage(
            f"Scan complete! Processed {len(results['successful_files'])}/{results['total_files']} files"
        )
    
    def _on_scan_error(self, error_message):
        """Handle errors that occur during scanning."""
        self.statusBar().showMessage(f"Scan error: {error_message}")
    
    def _load_config(self):
        """Load configuration settings."""
        # Load saved window geometry
        geometry = self.config.get("window_geometry")
        if geometry:
            self.setGeometry(*geometry)

    def _on_directory_selected(self, directory):
        """Handle directory selection."""
        if directory:
            self.statusBar().showMessage(f"Directory selected: {directory}")
            self.config.set("last_directory", directory)    
    
    def _set_window_title(self):
        """Update window title based on current playlist"""
        current_playlist = self.config.get("current_playlist", "No playlist loaded")
        self.setWindowTitle(f"Music Library Profiler -- {current_playlist}")

    def _on_track_added_to_request_list(self):
        """Handle tracks being added to the similar track request list."""
        tracks = self.similar_track_request_list.get_tracks()
        playlist = self.track_similarity.create_playlist_multitrack_interpolate(track_paths=tracks, num_tracks_between=5)
        track_metadata_list = [self.database.get_track_metadata_by_id(track_id) for track_id in playlist]
        self.similar_tracks_generate_list.clear()
        self.similar_tracks_generate_list.add_tracks(track_metadata_list)
