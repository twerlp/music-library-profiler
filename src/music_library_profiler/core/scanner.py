# scanner.py - Scans directory for audio files, extracts metadata, runs the audio analyzer, and stores info in database.
from typing import Optional, Callable
import logging
import datetime
from core.database import Database
from core.metadata_reader import MetadataReader
import utils.file_helpers as fh

class Scanner:
    def __init__(self, directory):
        self.directory = directory
        self.database = Database()
        self.metadata_reader = MetadataReader()
        self.feature_extractor = None  # Placeholder for audio feature extractor
        self.progress_callback: Optional[Callable] = None
    
    def set_progress_callback(self, callback: Callable):
        """Set a callback function for progress updates"""
        self.progress_callback = callback

    def scan_directory(self):
        """Scan the directory for audio files, extract metadata and features, and store in database."""
        #TODO: Implement database interactions--gather existing entries, insert new ones
        #TODO: Handle duplicates
        #TODO: Error handling and logging
        #TODO: Progress reporting
        #TODO: Multithreading for speed

        music_files = fh.find_music_files(self.directory)
        total_files = len(music_files)

        scan_id = self.database.start_scan(self.directory)

        results = {
            "total_files": total_files,
            "successful_files": 0,
            "failed_files": 0,
            "errors": [],
            "tracks_with_bpm": 0,
            "tracks_with_key": 0,
            "start_time": datetime.datetime.now(),
            "end_time": None
        }

        if self.progress_callback:
            self.progress_callback(0, total_files, "Finding music files...")

        logging.info(f"Found {total_files} music files in {self.directory}")
        # Process each file
        for i, file_path in enumerate(music_files):
            if self.progress_callback:
                self.progress_callback(i, total_files, f"Processing {file_path.name}")
            
            #TODO: Check if file already processed in database or if user is doing a full rescan

            try:
                # Read metadata
                metadata = self.metadata_reader.read_metadata(file_path)
                #TODO: Log missing metadata
                if metadata is None:
                    logging.warning(f"Skipping unreadable file: {file_path}")
                    results["failed_files"] += 1
                    continue
            except Exception as e:
                results["errors"].append(f"{str(file_path)}, {str(e)}")
                results["failed_files"] += 1
                logging.error(f"Error reading metadata for {file_path}: {e}")
                continue
            #TODO: Extract audio features
            # features = self.feature_extractor.extract_features(file_path)
            #TODO: Store metadata and features in database
            self.database.insert_track(metadata)
            results["successful_files"] += 1
            if metadata.get("bpm"):
                results["tracks_with_bpm"] += 1
            if metadata.get("key"):
                results["tracks_with_key"] += 1
        
        self.database.end_scan(
            scan_id=scan_id,
            total_files=results["total_files"],
            successful_files=results["successful_files"],
            errors=len(results["errors"])
        )
        logging.info("Scanning complete.")
        logging.info(f"Processed {total_files} files.")

        if self.progress_callback:
            self.progress_callback(total_files, total_files, "Scan complete!")

        return results