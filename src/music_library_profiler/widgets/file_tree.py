"""
Custom widgets for displaying music library and playlists.
"""
import logging
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal, QMimeData, QUrl
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QTreeWidget, QTreeWidgetItem, QAbstractItemView
)

from core.metadata_reader import MetadataReader

logger = logging.getLogger(__name__)


# Widget for displaying the music library in a tree structure
# Grouped by artist, then album, then tracks
class FileTreeWidget(QTreeWidget):
    """Tree view of the music library grouped by artist, then album."""
    
    track_double_clicked = pyqtSignal(str)  # emits file path
    
    def __init__(self, database, parent=None):
        super().__init__(parent)
        self.database = database
        self.setHeaderLabel("Music Library")
        self.setAlternatingRowColors(True)
        self.setSortingEnabled(True)
        self.setDragEnabled(True)                     # enable dragging
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.itemDoubleClicked.connect(self._on_item_double_clicked)
        
        self.populate()
    
    def populate(self):
        """Load all tracks from the database and build the tree."""

        # Honestly suprising that this is performant enough for reasonably sized libraries
        #TODO: sort by album artist and not just artist
        #TODO: order by track number within albums
        
        self.clear()
    
        all_tracks = self.database.fetch_all_track_metadata()
        
        artists = {}
        for track in all_tracks:
            artist = artist = track["artist"] if track.get("artist", "Unknown Artist") is not None else "Unknown Artist"
            album = track["album"] if track.get("album") is not None else "Unknown Album"
            title = track["title"] if track.get("title") is not None else Path(track["file_path"]).stem
            file_path = track["file_path"]
            assert file_path is not None, f"Track {title} is missing a file path!"
            
            if artist not in artists:
                artists[artist] = {}
            if album not in artists[artist]:
                artists[artist][album] = []
            artists[artist][album].append((title, file_path))
        
        for artist, albums in sorted(artists.items()):
            artist_item = QTreeWidgetItem([artist])
            artist_item.setIcon(0, QIcon.fromTheme("system-users"))
            self.addTopLevelItem(artist_item)
            for album, tracks in sorted(albums.items()):
                album_item = QTreeWidgetItem([album])
                album_item.setIcon(0, QIcon.fromTheme("media-optical"))
                artist_item.addChild(album_item)
                for title, file_path in sorted(tracks):
                    track_item = QTreeWidgetItem([title])
                    track_item.setIcon(0, QIcon.fromTheme("audio-x-generic"))
                    track_item.setData(0, Qt.ItemDataRole.UserRole, file_path)
                    album_item.addChild(track_item)
        
        self.expandAll()
    
    def mimeData(self, items):
        """
        Return mime data for the selected track item.
        Only leaf nodes (tracks) have a file path, so we provide a URL for them.
        """
        # TODO: Support multi-selection later, including entire albums/artists
        if not items:
            return None
        # Use the first selected item (single selection)
        item = items[0]
        file_path = item.data(0, Qt.ItemDataRole.UserRole)
        if file_path:
            mime_data = QMimeData()
            mime_data.setUrls([QUrl.fromLocalFile(file_path)])
            return mime_data
        return super().mimeData(items)
    
    def _on_item_double_clicked(self, item, column):
        """Emit file path if the double-clicked item is a track."""
        file_path = item.data(0, Qt.ItemDataRole.UserRole)
        if file_path:
            self.track_double_clicked.emit(file_path)

