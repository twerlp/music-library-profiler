# database.py - Database interaction layer using SQLite. 
from pathlib import Path
import sqlite3
import logging
from typing import List, Dict, Optional, Any, Set, Tuple
import numpy as np

import utils.constants as const
import utils.resource_manager as rm

logger = logging.getLogger(__name__)

#TODO: Prevent SQL injection (artist/track/album names could fuck it up I think)

class Database:
    def __init__(self):
        self.db_path = rm.project_path("database/library.db")
        if not self.db_path.parent.exists():
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._create_tables()

    def _create_tables(self):
        """Create necessary tables if they don't exist. (Main thread)"""
        with sqlite3.connect(self.db_path) as conn:
            # Metadata (tracks) table
            conn.execute(f'''
                CREATE TABLE IF NOT EXISTS track_metadata (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    {',\n'.join([f'{field} {sql_type}' for field, sql_type in const.METADATA_FIELD_TYPES.items()])}
                )
            ''')
            # Scan History table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS scan_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    end_time TIMESTAMP,
                    directory TEXT,
                    total_files INTEGER,
                    successful_files INTEGER,
                    errors INTEGER
                )
            ''')
            # HPCP table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS track_hpcp (
                    track_id INTEGER PRIMARY KEY,
                    hpcp_data BLOB NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (track_id) REFERENCES track_metadata(id) ON DELETE CASCADE
                )
            ''')

    # Metadata Insertion Methods
    def insert_track_metadata(self, metadata: Dict[str, Any]) -> int:
        """Insert a track's metadata into the database. (Worker thread)"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(f'''
                    INSERT OR IGNORE INTO track_metadata (
                        {", ".join(const.METADATA_FIELD_TYPES.keys())}
                    ) VALUES ({", ".join(["?"] * len(const.METADATA_FIELD_TYPES.keys()))})
                ''', (
                    [metadata.get(field) for field in const.METADATA_FIELD_TYPES.keys()]
                ))
        except Exception as e:
            logger.error(f"Error inserting track {metadata.get("file_name")}: {e}")

    # HPCP Methods
    def insert_hpcp(self, track_id: int, hpcp_data: np.ndarray) -> bool:
        """Store HPCP fingerprint for a single track."""
        try:
            if hpcp_data is None:
                logger.warning(f"No HPCP data provided for track {track_id}")
                return False
                
            # Convert to binary
            hpcp_array = np.array(hpcp_data, dtype=np.float32)
            hpcp_binary = sqlite3.Binary(hpcp_array.tobytes())
            
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO track_hpcp (track_id, hpcp_data)
                    VALUES (?, ?)
                ''', (track_id, hpcp_binary))
                
            return True
            
        except Exception as e:
            logger.error(f"Error storing HPCP for track {track_id}: {e}")
            return False

    def batch_insert_hpcp(self, hpcp_data_dict: Dict[int, np.ndarray]) -> Set:
        """Store HPCP data for multiple tracks efficiently in a single transaction.
        
        Args:
            hpcp_data_dict: Dictionary with {track_id: hpcp_array} pairs
        Returns:
            Set of the successfully stored files
        """
        try:
            if not hpcp_data_dict:
                logger.warning("No HPCP data provided to batch_insert_hpcp")
                return 0
                
            # Convert all HPCP arrays to binary format
            data_tuples = []
            for track_id, hpcp_array in hpcp_data_dict.items():
                if hpcp_array is not None:
                    try:
                        hpcp_array = np.array(hpcp_array, dtype=np.float32)
                        hpcp_binary = sqlite3.Binary(hpcp_array.tobytes())
                        data_tuples.append((track_id, hpcp_binary))
                    except Exception as e:
                        logger.error(f"Error converting HPCP for track {track_id}: {e}")
                        continue
            
            if not data_tuples:
                logger.warning("No valid HPCP data to store")
                return 0
                
            # Single transaction for all inserts
            with sqlite3.connect(self.db_path) as conn:
                conn.executemany('''
                    INSERT OR REPLACE INTO track_hpcp (track_id, hpcp_data)
                    VALUES (?, ?)
                ''', data_tuples)
                
            logger.info(f"Successfully stored HPCP data for {len(data_tuples)} tracks")
            return {data_tuple[0] for data_tuple in data_tuples}
                
        except sqlite3.Error as e:
            logger.error(f"Database error in batch_insert_hpcp: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in batch_insert_hpcp: {e}")
            return None
    
    def get_hpcp(self, track_id: int) -> Optional[np.ndarray]:
        """Retrieve HPCP fingerprint for a track."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('''
                    SELECT hpcp_data FROM track_hpcp WHERE track_id = ?
                ''', (track_id,))
                result = cursor.fetchone()
                if result:
                    # Convert binary back to numpy array
                    return np.frombuffer(result[0], dtype=np.float32)
                return None
        except Exception as e:
            logger.error(f"Error retrieving HPCP for track {track_id}: {e}")
            return None
        
    def get_missing_hpcps(self, track_ids: List[int]) -> Tuple[Set[int], Set[int]]:
        if not track_ids:
            return set()
        try:
            with sqlite3.connect(self.db_path) as conn:
                placeholders = ','.join(['?'] * len(track_ids))

                cursor = conn.execute(
                    f'SELECT track_id FROM track_hpcp WHERE track_id IN ({placeholders})', 
                    track_ids
                )
                found_ids = {row[0] for row in cursor.fetchall()}
                return set(track_ids) - found_ids, set(found_ids)
        except Exception as e:
            logger.error(f"Error checking track existence {track_ids}: {e}")
            return set(track_ids), set()  # Assume all are missing on error
    
    def get_all_hpcp(self) -> Dict[int, np.ndarray]:
        """Retrieve all HPCP fingerprints."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('''SELECT * FROM track_hpcp''')
                results = cursor.fetchall()
                if results:
                    return {result[0]: np.frombuffer(result[1], dtype=np.float32) for result in results}
                return None
        except Exception as e:
            logger.error(f"Error retrieving HPCPs: {e}")
            return None
    
    # Metadata Retrieval Methods
    def fetch_all_track_metadata(self) -> List[Dict]:
        """Fetch all tracks from the database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('SELECT * FROM track_metadata')
                tracks = []
                for row in cursor.fetchall():
                    # row[i+1] to avoid first id column
                    track = {list(const.METADATA_FIELD_TYPES.keys())[i]: row[i+1] for i in range(len(const.METADATA_FIELD_TYPES.keys()))}
                    tracks.append(track)
                return tracks
        except Exception as e:
            logger.error(f"Error fetching tracks: {e}")
            return []
        
    def get_range_of_track_metadata(self, offset: int, limit: int) -> List[Dict]:
        """Fetch a range of tracks."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                logger.info(f"Fetching tracks with offset {offset} and limit {limit}")
                cursor = conn.execute('SELECT * FROM track_metadata LIMIT ? OFFSET ?', (limit, offset))
                tracks = []
                for row in cursor.fetchall():
                    # row[i+1] to avoid first id column
                    field_names = list(const.METADATA_FIELD_TYPES.keys())
                    track = {field_names[i]: row[i+1] for i in range(len(field_names))}
                    tracks.append(track)
                return tracks
        except Exception as e:
            logger.error(f"Error fetching range of tracks: {e}")
            return []
    
    def get_track_metadata_by_id(self, track_id: int) -> Optional[Dict]:
        """Fetch a single track by its ID."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('SELECT * FROM track_metadata WHERE id = ?', (track_id,))
                row = cursor.fetchone()
                if row:
                    # row[i+1] to avoid first id column
                    field_names = list(const.METADATA_FIELD_TYPES.keys())
                    track = {field_names[i]: row[i+1] for i in range(len(field_names))}
                    return track
                return None
        except Exception as e:
            logger.error(f"Error fetching track by ID {track_id}: {e}")
            return None
        
    def get_track_ids_by_paths(self, file_paths: List[Path]) -> Dict[str, int]:
        """Get multiple track_ids at once."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Use IN clause for multiple paths
                path_strings = [str(path) for path in file_paths]
                placeholders = ','.join(['?'] * len(file_paths))
                cursor = conn.execute(
                    f'SELECT id, file_path FROM track_metadata WHERE file_path IN ({placeholders})',
                    path_strings
                )
                return {row[1]: row[0] for row in cursor.fetchall()}  # {file_path: track_id}
        except Exception as e:
            logger.error(f"Error finding track_ids: {e}")
            return {}
        
    def get_track_id_by_path(self, file_path: Path) -> Optional[int]:
        """Get track_id using the file path (most reliable identifier)."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    'SELECT id FROM track_metadata WHERE file_path = ?', 
                    (str(file_path),)
                )
                result = cursor.fetchone()
                return result[0] if result else None
        except Exception as e:
            logger.error(f"Error finding track_id for {file_path}: {e}")
            return None
        
    def get_missing_tracks(self, track_paths: List[Path]) -> Tuple[Set[Path], Set[Path]]:
        if not track_paths:
            return set()
        try:
            with sqlite3.connect(self.db_path) as conn:
                path_strings = [str(path) for path in track_paths]
                placeholders = ','.join(['?'] * len(track_paths))

                cursor = conn.execute(
                    f'SELECT file_path FROM track_metadata WHERE file_path IN ({placeholders})', 
                    path_strings
                )
                found_paths = {Path(row[0]) for row in cursor.fetchall()}
                return set(track_paths) - found_paths, set(found_paths)
        except Exception as e:
            logger.error(f"Error checking track existence {track_paths}: {e}")
            return set(track_paths), {}  # Assume all are missing on error
        
    # Scan History Methods
    def start_scan(self, directory: Path) -> Optional[int]:
        """Log the start of a scan session."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('''
                    INSERT INTO scan_history (directory, total_files, successful_files, errors)
                    VALUES (?, 0, 0, 0)
                ''', (str(directory),))
                return cursor.lastrowid
        except Exception as e:
            logger.error(f"Error starting scan log: {e}")
            return None
    
    def end_scan(self, scan_id: int, total_files: int, successful_files: int, errors: int):
        """Log the end of a scan session."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    UPDATE scan_history
                    SET end_time = CURRENT_TIMESTAMP, total_files = ?, successful_files = ?, errors = ?
                    WHERE id = ?
                ''', (total_files, successful_files, errors, scan_id))
        except Exception as e:
            logger.error(f"Error ending scan log: {e}")
    
    def count_number_of_tracks(self) -> int:
        """Return the total number of tracks in the database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('SELECT COUNT(*) FROM track_metadata')
                count = cursor.fetchone()[0]
                return count
        except Exception as e:
            logger.error(f"Error counting tracks: {e}")
            return 0