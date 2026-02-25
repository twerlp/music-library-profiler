# requested_song_list.py - Widget for displaying a grid list of requested songs with album art

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

# Widget for displaying a grid list of songs with album art
# To be used for showing tracks we want to find similar ones to
class RequestedSongListWidget(BaseSongListWidget):
    """Grid list of tracks. Dragging enabled."""
    
    track_double_clicked = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.database = parent.database if parent and hasattr(parent, "database") else None
        print("parent:", parent)
        print("RequestedSongListWidget initialized with database:", self.database)

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
            # Internal drop TODO: this doesn't work properly, internal drop treated as external drop, track duplicated instead of moved
            super().dropEvent(event)
        else:
            # External drop
            urls = event.mimeData().urls()
            for url in urls:
                if url.isLocalFile():
                    file_path = url.toLocalFile()

                    if self.database is not None:
                        track_data = self.database.get_track_metadata_by_id(self.database.get_track_id_by_path(file_path))
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