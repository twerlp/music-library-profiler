import logging
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtMultimedia import QMediaPlayer
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QSlider,
    QLabel, QSizePolicy,
)

import utils.resource_manager as rm

logger = logging.getLogger(__name__)


class PlayerWidget(QWidget):
    def __init__(self, player, parent=None):
        super().__init__(parent)
        self._player_core = player

        self._icon_play = QIcon(str(rm.project_path("assets/play.png")))
        self._icon_pause = QIcon(str(rm.project_path("assets/pause.png")))
        self._icon_prev = QIcon(str(rm.project_path("assets/backward.png")))
        self._icon_next = QIcon(str(rm.project_path("assets/forward.png")))
        self._icon_volume = QIcon(str(rm.project_path("assets/volume.png")))

        self._seeking = False
        self._is_muted = False
        self._pre_mute_volume = 1.0

        self._init_ui()
        self._connect_signals()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        progress_layout = QHBoxLayout()
        progress_layout.setSpacing(6)

        self.position_label = QLabel("0:00")
        self.position_label.setFixedWidth(40)
        self.position_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        progress_layout.addWidget(self.position_label)

        self.progress_slider = QSlider(Qt.Orientation.Horizontal)
        self.progress_slider.setRange(0, 0)
        self.progress_slider.sliderPressed.connect(self._on_slider_pressed)
        self.progress_slider.sliderReleased.connect(self._on_slider_released)
        self.progress_slider.sliderMoved.connect(self._on_slider_moved)
        progress_layout.addWidget(self.progress_slider)

        self.duration_label = QLabel("0:00")
        self.duration_label.setFixedWidth(40)
        self.duration_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        progress_layout.addWidget(self.duration_label)

        layout.addLayout(progress_layout)

        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(4)

        self.prev_button = QPushButton()
        self.prev_button.setIcon(self._icon_prev)
        self.prev_button.setToolTip("Previous")
        self.prev_button.setFixedSize(32, 32)
        self.prev_button.clicked.connect(self._player_core.play_previous)
        controls_layout.addWidget(self.prev_button)

        self.play_button = QPushButton()
        self.play_button.setIcon(self._icon_play)
        self.play_button.setToolTip("Play")
        self.play_button.setFixedSize(32, 32)
        self.play_button.clicked.connect(self._player_core.toggle_play_pause)
        controls_layout.addWidget(self.play_button)

        self.next_button = QPushButton()
        self.next_button.setIcon(self._icon_next)
        self.next_button.setToolTip("Next")
        self.next_button.setFixedSize(32, 32)
        self.next_button.clicked.connect(self._player_core.play_next)
        controls_layout.addWidget(self.next_button)

        controls_layout.addSpacing(12)

        self.mute_button = QPushButton()
        self.mute_button.setIcon(self._icon_volume)
        self.mute_button.setToolTip("Mute")
        self.mute_button.setFixedSize(32, 32)
        self.mute_button.clicked.connect(self._on_mute_toggled)
        controls_layout.addWidget(self.mute_button)

        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(100)
        self.volume_slider.setFixedWidth(100)
        self.volume_slider.valueChanged.connect(self._on_volume_changed)
        controls_layout.addWidget(self.volume_slider)

        controls_layout.addStretch()

        self.track_label = QLabel("No track playing")
        self.track_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        controls_layout.addWidget(self.track_label)

        layout.addLayout(controls_layout)

    def _connect_signals(self):
        self._player_core.track_changed.connect(self._on_track_changed)
        self._player_core.playback_state_changed.connect(self._on_playback_state_changed)
        self._player_core.position_changed.connect(self._on_position_changed)
        self._player_core.duration_changed.connect(self._on_duration_changed)
        self._player_core.error_occurred.connect(self._on_error_occurred)

    def _on_error_occurred(self, message):
        self.track_label.setText(f"[!] {message}")

    def _on_track_changed(self, file_path):
        self.track_label.setText(Path(file_path).stem)

    def _on_playback_state_changed(self, state):
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.play_button.setIcon(self._icon_pause)
            self.play_button.setToolTip("Pause")
        else:
            self.play_button.setIcon(self._icon_play)
            self.play_button.setToolTip("Play")

    def _on_position_changed(self, position_ms):
        if not self._seeking:
            self.progress_slider.setValue(position_ms)
        self.position_label.setText(self._format_time(position_ms))

    def _on_duration_changed(self, duration_ms):
        self.progress_slider.setRange(0, duration_ms)
        self.duration_label.setText(self._format_time(duration_ms))
        self.progress_slider.setEnabled(duration_ms > 0)

    def _on_slider_pressed(self):
        self._seeking = True

    def _on_slider_released(self):
        self._seeking = False
        position_ms = self.progress_slider.value()
        self._player_core._player.setPosition(position_ms)

    def _on_slider_moved(self, position_ms):
        self.position_label.setText(self._format_time(position_ms))

    def _on_volume_changed(self, value):
        volume = value / 100.0
        self._player_core.set_volume(volume)
        self._is_muted = volume <= 0

    def _on_mute_toggled(self):
        if self._is_muted:
            self._player_core.set_volume(self._pre_mute_volume)
            self.volume_slider.setValue(int(self._pre_mute_volume * 100))
            self._is_muted = False
        else:
            self._pre_mute_volume = self._player_core.volume()
            self._player_core.set_volume(0.0)
            self.volume_slider.setValue(0)
            self._is_muted = True

    @staticmethod
    def _format_time(ms):
        seconds = ms // 1000
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes}:{seconds:02}"
