import logging

from PyQt6.QtCore import QObject, QTimer, QUrl, pyqtSignal
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput

logger = logging.getLogger(__name__)

_STALL_TIMEOUT_MS = 5000


class Player(QObject):
    track_changed = pyqtSignal(str)
    playback_state_changed = pyqtSignal(QMediaPlayer.PlaybackState)
    position_changed = pyqtSignal('qint64')
    duration_changed = pyqtSignal('qint64')
    error_occurred = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._player = QMediaPlayer()
        self._audio_output = QAudioOutput()
        self._player.setAudioOutput(self._audio_output)

        self._playlist = []
        self._current_index = -1
        self._stall_timer = QTimer(self)
        self._stall_timer.setSingleShot(True)
        self._stall_timer.timeout.connect(self._on_stall_timeout)

        self._player.mediaStatusChanged.connect(self._on_media_status_changed)
        self._player.playbackStateChanged.connect(self.playback_state_changed)
        self._player.positionChanged.connect(self.position_changed)
        self._player.durationChanged.connect(self.duration_changed)
        self._player.errorChanged.connect(self._on_error_changed)

    @property
    def playlist(self):
        return list(self._playlist)

    @property
    def current_index(self):
        return self._current_index

    def set_playlist_and_play(self, file_path, playlist):
        self._playlist = list(playlist)
        try:
            self._current_index = self._playlist.index(file_path)
        except ValueError:
            self._current_index = 0
            if file_path:
                self._playlist.insert(0, file_path)
        self._play_current()

    def play_file(self, file_path):
        self._playlist = [file_path]
        self._current_index = 0
        self._play_current()

    def _play_current(self):
        if self._current_index < 0 or self._current_index >= len(self._playlist):
            return
        self._stall_timer.stop()
        file_path = self._playlist[self._current_index]
        self._player.stop()
        self._player.setSource(QUrl.fromLocalFile(file_path))
        self._player.play()
        self.track_changed.emit(file_path)

    def play_next(self):
        if not self._playlist:
            return
        self._current_index += 1
        if self._current_index < len(self._playlist):
            self._play_current()
        else:
            self._player.stop()

    def play_previous(self):
        if not self._playlist:
            return
        self._current_index -= 1
        if self._current_index >= 0:
            self._play_current()
        else:
            self._current_index = 0
            self._play_current()

    def toggle_play_pause(self):
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
        else:
            self._player.play()

    def stop(self):
        self._stall_timer.stop()
        self._player.stop()

    def set_volume(self, volume):
        self._audio_output.setVolume(max(0.0, min(1.0, volume)))

    def volume(self):
        return self._audio_output.volume()

    def position(self):
        return self._player.position()

    def duration(self):
        return self._player.duration()

    def _on_media_status_changed(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self._stall_timer.stop()
            self.play_next()
        elif status == QMediaPlayer.MediaStatus.StalledMedia:
            progress = self._player.bufferProgress() * 100
            logger.warning(f"Playback stalled at {progress:.0f}% buffered")
            self._stall_timer.start(_STALL_TIMEOUT_MS)
        elif status == QMediaPlayer.MediaStatus.InvalidMedia:
            logger.warning(f"Cannot play {self._playlist[self._current_index]}: invalid media")
            self._stall_timer.stop()
            self.error_occurred.emit(f"Cannot play: {self._player.errorString()}")
            self.play_next()
        elif status == QMediaPlayer.MediaStatus.BufferedMedia:
            self._stall_timer.stop()
        elif status == QMediaPlayer.MediaStatus.LoadedMedia:
            self._stall_timer.stop()

    def _on_stall_timeout(self):
        logger.warning(f"Stall timeout reached, skipping track")
        self.error_occurred.emit("Playback stalled, skipping...")
        self.play_next()

    def _on_error_changed(self):
        if self._player.error() != QMediaPlayer.Error.NoError:
            logger.warning(f"Media error: {self._player.errorString()}")
            self.error_occurred.emit(self._player.errorString())
