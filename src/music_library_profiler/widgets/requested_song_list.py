# requested_song_list.py - Widget for displaying a horizontal scrolling list of requested songs with album art

import logging

from PyQt6.QtCore import Qt, pyqtSignal, QSize, QMimeData, QUrl
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWidgets import (
    QListWidget, QListWidgetItem, QWidget, QVBoxLayout, 
    QLabel, QAbstractItemView, QListView
)

from widgets.track_display import TrackDisplayWidget
from widgets.base_song_list import BaseSongListWidget

from pathlib import Path

logger = logging.getLogger(__name__)

# Widget for displaying a horizontal scrolling list of songs with album art
# To be used for showing tracks we want to find similar ones to
class RequestedSongListWidget(BaseSongListWidget):
    """Horizontal scrolling list of tracks. Dragging enabled."""
    
    track_double_clicked = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

    def supportedDropActions(self):
        """Allow both copy and move actions."""
        return Qt.DropAction.CopyAction | Qt.DropAction.MoveAction
    
    def dragEnterEvent(self, event):
        """Accept drags that contain local file URLs."""
        if event.mimeData().hasUrls():
            event.accept()
        else:
            super().dragEnterEvent(event)   # or event.ignore()

    def dropEvent(self, event):
        """
        Handle drops: if from same widget -> internal move (reorder);
        if from external source (file manager or other widgets) -> add tracks.
        """
        print("Drop event in RequestedSongListWidget")
        if event.source() == self and event.dropAction() == Qt.DropAction.MoveAction:
            # Internal reordering: let base class handle it
            super().dropEvent(event)
        else:
            # External drop: extract URLs and add tracks
            urls = event.mimeData().urls()
            for url in urls:
                if url.isLocalFile():
                    file_path = url.toLocalFile()
                    # Here you should fetch full metadata from the database.
                    # For simplicity, we create minimal track_data; you can enhance this.
                    track_data = {
                        "file_path": file_path,
                        "title": Path(file_path).stem,
                        "artist": "Unknown Artist",
                        "album": "Unknown Album",
                        "album_art": None
                    }
                    # Optional: look up in database to get richer metadata
                    # (you might need to pass the database reference)
                    self.add_track(track_data)
            event.accept()