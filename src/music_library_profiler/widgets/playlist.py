import logging
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal, QSize, QMimeData, QUrl
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWidgets import (
    QListWidget, QListWidgetItem, QWidget, QHBoxLayout,
    QVBoxLayout, QLabel, QAbstractItemView,
)

logger = logging.getLogger(__name__)

class PlaylistListWidget(QListWidget):
    """Vertical list of tracks with album art. Supports drag & drop for reordering and adding tracks."""
    
    track_double_clicked = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlternatingRowColors(True)
        self.setIconSize(QSize(48, 48))
        
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        
        self.itemDoubleClicked.connect(self._on_item_double_clicked)
    
    def add_track(self, track_data):
        """
        Add a track to the playlist.
        track_data: dict with keys 'file_path', 'title', 'artist', 'album', 'album_art' (QPixmap)
        """
        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, track_data["file_path"])
        
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)
        
        # Album art
        art_label = QLabel()
        art_label.setFixedSize(48, 48)
        art_label.setScaledContents(True)
        if track_data.get("album_art"):
            art_label.setPixmap(track_data["album_art"])
        else:
            art_label.setPixmap(QIcon.fromTheme("audio-x-generic").pixmap(48, 48))
        layout.addWidget(art_label)
        
        # Text info
        text_widget = QWidget()
        text_layout = QVBoxLayout(text_widget)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)
        
        title_label = QLabel(track_data.get("title", "Unknown"))
        title_label.setFont(QFont("DejaVu Sans", 10, QFont.Weight.Bold))
        text_layout.addWidget(title_label)
        
        artist_label = QLabel(track_data.get("artist", "Unknown Artist"))
        artist_label.setFont(QFont("DejaVu Sans", 9))
        artist_label.setStyleSheet("color: gray;")
        text_layout.addWidget(artist_label)
        
        layout.addWidget(text_widget, 1)
        layout.addStretch()
        
        widget.setLayout(layout)
        item.setSizeHint(widget.sizeHint())
        
        self.addItem(item)
        self.setItemWidget(item, widget)
    
    def mimeData(self, items):
        """
        Provide URLs for the dragged items so they can be dropped elsewhere.
        """
        urls = []
        for item in items:
            file_path = item.data(Qt.ItemDataRole.UserRole)
            if file_path:
                urls.append(QUrl.fromLocalFile(file_path))
        if urls:
            mime_data = QMimeData()
            mime_data.setUrls(urls)
            return mime_data
        return super().mimeData(items)
    
    def supportedDropActions(self):
        """Allow both copy and move actions."""
        return Qt.DropAction.CopyAction | Qt.DropAction.MoveAction
    
    def dragEnterEvent(self, event):
        """Accept drags that contain local file URLs."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

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
    
    def clear(self):
        """Remove all tracks from the playlist."""
        super().clear()
    
    def _on_item_double_clicked(self, item):
        """Emit file path for the double-clicked track."""
        file_path = item.data(Qt.ItemDataRole.UserRole)
        if file_path:
            self.track_double_clicked.emit(file_path)
