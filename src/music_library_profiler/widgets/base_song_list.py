# base_song_list.py - Base class for song list widgets (RequestedSongListWidget and GeneratedSongListWidget)

import logging

from PyQt6.QtCore import Qt, pyqtSignal, QSize, QMimeData, QUrl
from PyQt6.QtWidgets import (
    QListWidget, QListWidgetItem, QAbstractItemView, QListView
)

from widgets.track_display import TrackDisplayWidget

from pathlib import Path

logger = logging.getLogger(__name__)

# Widget for displaying a horizontal scrolling list of songs with album art
class BaseSongListWidget(QListWidget):
    """Horizontal scrolling list of tracks. Dragging enabled."""
    
    track_double_clicked = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFlow(QListView.Flow.LeftToRight)
        self.setWrapping(False)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setIconSize(QSize(64, 64))
        self.setGridSize(QSize(120, 100))
        self.setViewMode(QListView.ViewMode.IconMode)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        
        self.setDragEnabled(True)
        self.setAcceptDrops(False)
        
        self.itemDoubleClicked.connect(self._on_item_double_clicked)

    def add_track(self, track_data):
        """
        Add a track to the horizontal list.
        track_data: dict with keys 'file_path', 'title', 'album_art' (QPixmap)
        """
        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, track_data["file_path"])
        widget = TrackDisplayWidget(track_data)
        item.setSizeHint(self.gridSize())
        self.addItem(item)
        self.setItemWidget(item, widget)
    
    def mimeData(self, items):
        """Provide URLs for the dragged track."""
        if not items:
            return None
        item = items[0]
        file_path = item.data(Qt.ItemDataRole.UserRole)
        if file_path:
            mime_data = QMimeData()
            mime_data.setUrls([QUrl.fromLocalFile(file_path)])
            return mime_data
        return super().mimeData(items)
    
    def clear(self):
        """Remove all tracks."""
        super().clear()
    
    def _on_item_double_clicked(self, item):
        """Emit file path."""
        file_path = item.data(Qt.ItemDataRole.UserRole)
        if file_path:
            self.track_double_clicked.emit(file_path)