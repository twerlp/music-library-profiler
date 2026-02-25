# generated_song_list.py - Widget for displaying a grid list of songs with album art

import logging

from widgets.base_song_list import BaseSongListWidget

logger = logging.getLogger(__name__)

# Widget for displaying a grid list of songs with album art
# To be used for showing similar tracks
class GeneratedSongListWidget(BaseSongListWidget):
    """Grid list of tracks. Dragging enabled."""
    pass