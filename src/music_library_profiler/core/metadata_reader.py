# metadata_reader.py - Functions to read and extract ID3 tags from audio files among other things if possible.
import os
from pathlib import Path
import logging
from typing import List, Optional, Type
import mutagen
from mutagen import FileType
from utils.constants import SUPPORTED_AUDIO_EXTENSIONS
from PyQt6.QtGui import QPixmap

class MetadataReader:
    def read_metadata(self, file_path: Path) -> Optional[dict]:
        """Read metadata from an audio file using mutagen."""
        if file_path.suffix.lower() not in SUPPORTED_AUDIO_EXTENSIONS:
            logging.warning(f"Unsupported file extension: {file_path.suffix} for file {file_path}")
            return None
        
        try:
            audiofile: FileType = mutagen.File(file_path)
            if audiofile is None:
                logging.warning(f"Could not read metadata for file: {file_path}")
                return None
            stat = file_path.stat()

            metadata = {
                "title": self._get_tag(audiofile, ["TIT2", "title", "\xa9nam"]),
                "artist": self._get_tag(audiofile, ["TPE1", "artist", "\xa9ART"]),
                "album": self._get_tag(audiofile, ["TALB", "album", "\xa9alb"]),
                "track_number": self._get_tag(audiofile, ["TRCK", "tracknumber", "trkn"]),
                "genre": self._get_tag(audiofile, ["TCON", "genre", "\xa9gen"]),
                "year": self._get_tag(audiofile, ["TDRC", "date", "year", "\xa9day"]),
                "bpm": int(self._get_tag(audiofile, ["TBPM", "bpm", "tmpo"])) if self._get_tag(audiofile, ["TBPM", "bpm", "tmpo"]) else None,
                "key": self._get_tag(audiofile, ["TKEY", "key", "initialkey"]),
                "duration": int(audiofile.info.length) if audiofile.info else None,
                "bitrate": int(audiofile.info.bitrate / 1000) if audiofile.info and hasattr(audiofile.info, 'bitrate') else None,
                "sample_rate": int(audiofile.info.sample_rate) if audiofile.info and hasattr(audiofile.info, 'sample_rate') else None,
                "channels": int(audiofile.info.channels) if audiofile.info and hasattr(audiofile.info, 'channels') else None,
                "file_path": str(file_path.resolve()),
                "file_name": file_path.name,
                "directory": str(file_path.parent),
                "extension": file_path.suffix.lower(),
                "size_bytes": stat.st_size,
                "last_modified": stat.st_mtime,
                "last_accessed": stat.st_atime,
                "created": stat.st_ctime,
            }
            return metadata
        except Exception as e:
            logging.exception(f"Error reading metadata for file {file_path}: {e}")
            return None
    
    def _get_tag(self, audiofile: FileType, keys: List[str]) -> Optional[str]:
        """Helper to get the first available tag from a list of possible keys."""
        for key in keys:
            try:
                if key in audiofile.tags:
                    value = audiofile.tags[key]
                    if isinstance(value, list):
                        return str(value[0])
                    return str(value)
            except ValueError:
                # Vorbis gets cranky if you ask for a tag that isn't there
                continue
        return None
    
    def read_album_art(self, file_path: Path) -> Optional[bytes]:
        """Extract album art from the audio file if available."""
        try:
            print(f"Attempting to read album art from file: {file_path}")
            audiofile: FileType = mutagen.File(file_path)
            if audiofile is None or not audiofile.tags:
                return None
            
            # Check for common album art tags
            for tag in ["APIC:", "covr", "cover", "METADATA_BLOCK_PICTURE"]:
                if tag in audiofile.tags:
                    if isinstance(audiofile.tags[tag], list):
                        return self._convert_cover_to_pixmap(audiofile.tags[tag][0])
                    return self._convert_cover_to_pixmap(audiofile.tags[tag])
            
            # For ID3v2.3 and earlier, look for APIC frames
            if hasattr(audiofile, "tags") and hasattr(audiofile.tags, "getall"):
                for apic in audiofile.tags.getall("APIC"):
                    return self._convert_cover_to_pixmap(apic)
            
            return None
        except Exception as e:
            logging.exception(f"Error reading album art for file {file_path}: {e}")
            return None
        
    def _convert_cover_to_pixmap(self, cover_data: bytes) -> Optional[QPixmap]:
        """Convert raw album art data to a QPixmap."""
        try:
            pixmap = QPixmap()
            if isinstance(cover_data, mutagen.id3.APIC):
                cover_data = cover_data.data
            if pixmap.loadFromData(cover_data):
                return pixmap
            else:
                logging.warning("Failed to convert album art data to QPixmap")
                return None
        except Exception as e:
            logging.exception(f"Error converting album art to QPixmap: {e}")
            return None