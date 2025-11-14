# scanner.py - Scans directory for audio files, extracts metadata, runs the audio analyzer, and stores info in database.
from typing import Optional, Callable, List, Any, Dict, Set, Tuple
from pathlib import Path
import logging
import datetime

from core.database import Database
from core.metadata_reader import MetadataReader
from core.track_similarity import TrackSimilarity
from core.audio_feature_extractor import AudioFeatureExtractor
import utils.file_helpers as fh

class Scanner:
    def __init__(self, directory: Path, database: Database, track_similarity: TrackSimilarity):
        self.directory = directory
        self.database = database
        self.track_similarity = track_similarity
        self.metadata_reader = MetadataReader()
        self.feature_extractor = None  # Placeholder for audio feature extractor
        self.progress_callback: Optional[Callable] = None
        self.scan_id = -1
    
    def set_progress_callback(self, callback: Callable):
        """Set a callback function for progress updates"""
        self.progress_callback = callback

    def _start_scan(self) -> List[Path]:
        """
        Starts a music profiling scan

        Returns:
            The files to process
        """
        
        music_files = fh.find_music_files(self.directory)
        total_files = len(music_files)

        if self.progress_callback:
            self.progress_callback(0, total_files, "Finding music files...")

        logging.info(f"Found {total_files} music files in {self.directory}")

        self.scan_id = self.database.start_scan(self.directory)

        return music_files
    
    def _end_scan(self, overall_results: Dict[str, Any]):

        self.database.end_scan(
            scan_id=self.scan_id,
            total_files=overall_results["total_files"],
            successful_files=len(overall_results["successful_files"]),
            errors=len(overall_results["errors"])
        )

        logging.info("Scanning complete.")
        logging.info(f"Processed {overall_results["total_files"]} files.")

        if self.progress_callback:
            self.progress_callback(overall_results["total_files"], overall_results["total_files"], "Scan complete!")

    
    def _scan_metadata(self, music_files: List[Path]) -> Dict[str, Any]:
        logging.info(f"Scanning metadata")
        metadata_results = {
            "successful_files": set(),
            "errors": [],
        }

        missing_music_files, existing_music_files = self.database.get_missing_tracks(music_files)
        metadata_results["successful_files"] | existing_music_files

        # Process each file
        for i, file_path in enumerate(missing_music_files):
            if self.progress_callback:
                self.progress_callback(i, len(missing_music_files), f"Processing {file_path.name}")
            try:
                # Read metadata
                metadata = self.metadata_reader.read_metadata(file_path)
                #TODO: Log missing metadata
                if metadata is None:
                    logging.warning(f"Skipping unreadable file: {file_path}")
                    continue
            except Exception as e:
                metadata_results["errors"].append(f"{str(file_path)}, {str(e)}")
                logging.error(f"Error reading metadata for {file_path}: {e}")
                continue
            self.database.insert_track_metadata(metadata)
            metadata_results["successful_files"].add(file_path)

        logging.info(f"Finished scanning metadata")
        return metadata_results

    def scan_directory(self):
        """Scan the directory for audio files, extract metadata and features, and store in database."""
        music_files = self._start_scan()
        total_files = len(music_files)

        overall_results = {
            "total_files": total_files,
            "successful_files": set(),
            "failed_files": set(music_files),
            "errors": [],
        }

        metadata_results = self._scan_metadata(music_files=music_files)
        
        afe = AudioFeatureExtractor(track_list=music_files, database=self.database, progress_callback=self.progress_callback, track_similarity=self.track_similarity)
        hpcp_results = afe.find_features_of_list(batch_size=128, max_workers=8)

        if len(metadata_results["successful_files"]) and len(hpcp_results["successful_files"]):
            overall_results["successful_files"] = metadata_results["successful_files"] & hpcp_results["successful_files"]
            overall_results["failed_files"] = overall_results["failed_files"] - overall_results["successful_files"]
        else:
            logging.info("No successful files.")

        overall_results["errors"].extend(metadata_results["errors"])
        overall_results["errors"].extend(hpcp_results["errors"])

        self._end_scan(overall_results=overall_results)
        
        return overall_results