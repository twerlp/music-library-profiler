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
        self.database = parent.database if parent and hasattr(parent, "database") else None

    def supportedDropActions(self):
        """Allow both copy and move actions."""
        return Qt.DropAction.CopyAction | Qt.DropAction.MoveAction
    
    def dragEnterEvent(self, event):
        """Accept drags that contain local file URLs."""
        if event.mimeData().hasUrls():
            event.accept()
        else:
            super().dragEnterEvent(event)   # or event.ignore()

    def dragMoveEvent(self, event):
        """Accept drags that contain local file URLs."""
        if event.mimeData().hasUrls():
            event.accept()
        else:
            super().dragMoveEvent(event)
        

    def dropEvent(self, event):
        """
        Handle drops: if from same widget -> internal move (reorder);
        if from external source (file manager or other widgets) -> add tracks.
        """
        if event.source() == self and event.dropAction() == Qt.DropAction.MoveAction:
            # Internal drop
            super().dropEvent(event)
        else:
            # External drop
            urls = event.mimeData().urls()
            for url in urls:
                if url.isLocalFile():
                    file_path = url.toLocalFile()

                    if self.database:
                        track_data = self.database.get_track_by_path(file_path)
                        if track_data is None:
                            logger.warning(f"Track not found in database for path: {file_path}")
                            track_data = {
                                "file_path": file_path,
                                "title": Path(file_path).stem,
                                "artist": "Unknown Artist",
                                "album": "Unknown Album",
                                "album_art": None
                            }
                    else: 
                        track_data = {
                            "file_path": file_path,
                            "title": Path(file_path).stem,
                            "artist": "Unknown Artist",
                            "album": "Unknown Album",
                            "album_art": None
                        }
                    self.add_track(track_data)
            event.accept()