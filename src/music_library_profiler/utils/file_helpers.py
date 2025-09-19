# file_helpers.py - Utility functions for file operations.
import os
from pathlib import Path
from typing import List
from utils.constants import SUPPORTED_AUDIO_EXTENSIONS

def find_music_files(directory: Path) -> List[Path]:
    """Recursively find all supported music files in the given directory."""
    music_files = []
    
    for root, _, files in os.walk(directory):
        for file in files:
            if Path(file).suffix.lower() in SUPPORTED_AUDIO_EXTENSIONS:
                music_files.append(Path(root) / file)
    
    return music_files