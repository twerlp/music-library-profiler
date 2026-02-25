# track_display.py - Custom widget for displaying a track with album art and title in the horizontal list.
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from core.metadata_reader import MetadataReader

class TrackDisplayWidget(QWidget):
    """Custom widget for displaying a track with album art and underneath title in the horizontal list."""
    def __init__(self, track_data):
        super().__init__()
        # Hovering over the element should show the full file path as a tooltip
        self.setToolTip(track_data.get("file_path", ""))
        self.setMinimumSize(120, 100)

        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        
        # Album art
        art_label = QLabel()
        art_label.setFixedSize(64, 64)
        art_label.setScaledContents(True)
        metadata_reader = MetadataReader()
        album_art = metadata_reader.read_album_art(track_data.get("file_path", None))
        if album_art is not None:
            art_label.setPixmap(album_art)
        else:
            art_label.setPixmap(QIcon.fromTheme("audio-x-generic").pixmap(64, 64))
        layout.addWidget(art_label, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Title
        title_label = QLabel(track_data["title"] if track_data.get("title") is not None else "Unknown")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setWordWrap(True)
        title_label.setFont(QFont("DejaVu Sans", 9))
        layout.addWidget(title_label)