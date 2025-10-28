# database.py - Database interaction layer using SQLite. 
from pathlib import Path
import sqlite3
import logging
from typing import List, Dict, Optional, Any
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
    def insert_track_metadata(self, metadata: Dict[str, Any]) -> bool:
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
            print(f"Error inserting track {metadata.get("file_name")}: {e}")

    # HPCP Methods
    def insert_hpcp(self, track_id: int, hpcp_data: np.ndarray) -> bool:
        """Store HPCP fingerprint for a single track."""
        try:
            if hpcp_data is None:
                print(f"No HPCP data provided for track {track_id}")
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
            print(f"Error storing HPCP for track {track_id}: {e}")
            return False

    def batch_insert_hpcp(self, hpcp_data_dict: Dict[int, np.ndarray]) -> int:
        """Store HPCP data for multiple tracks efficiently in a single transaction.
        
        Args:
            hpcp_data_dict: Dictionary with {track_id: hpcp_array} pairs
        """
        try:
            if not hpcp_data_dict:
                print("No HPCP data provided to batch_insert_hpcp")
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
                        print(f"Error converting HPCP for track {track_id}: {e}")
                        continue
            
            if not data_tuples:
                print("No valid HPCP data to store")
                return 0
                
            # Single transaction for all inserts
            with sqlite3.connect(self.db_path) as conn:
                conn.executemany('''
                    INSERT OR REPLACE INTO track_hpcp (track_id, hpcp_data)
                    VALUES (?, ?)
                ''', data_tuples)
                
            print(f"Successfully stored HPCP data for {len(data_tuples)} tracks")
            return len(data_tuples)
                
        except sqlite3.Error as e:
            print(f"Database error in batch_insert_hpcp: {e}")
            return 0
        except Exception as e:
            print(f"Unexpected error in batch_insert_hpcp: {e}")
            return 0
    
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
            print(f"Error retrieving HPCP for track {track_id}: {e}")
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
            print(f"Error fetching tracks: {e}")
            return []
        
    def get_range_of_track_metadata(self, offset: int, limit: int) -> List[Dict]:
        """Fetch a range of tracks."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                print(f"Fetching tracks with offset {offset} and limit {limit}")
                cursor = conn.execute('SELECT * FROM track_metadata LIMIT ? OFFSET ?', (limit, offset))
                tracks = []
                for row in cursor.fetchall():
                    # row[i+1] to avoid first id column
                    track = {list(const.METADATA_FIELD_TYPES.keys())[i]: row[i+1] for i in range(len(const.METADATA_FIELD_TYPES.keys()))}
                    tracks.append(track)
                return tracks
        except Exception as e:
            print(f"Error fetching range of tracks: {e}")
            return []
    
    def get_track_metadata_by_id(self, track_id: int) -> Optional[Dict]:
        """Fetch a single track by its ID."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('SELECT * FROM track_metadata WHERE id = ?', (track_id,))
                row = cursor.fetchone()
                if row:
                    # row[i+1] to avoid first id column
                    track = {const.METADATA_FIELD_TYPES.keys()[i]: row[i+1] for i in range(len(const.METADATA_FIELD_TYPES.keys()))}
                    return track
                return None
        except Exception as e:
            print(f"Error fetching track by ID {track_id}: {e}")
            return None
        
    def get_track_ids_by_paths(self, file_paths: List[str]) -> Dict[str, int]:
        """Get multiple track_ids at once."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Use IN clause for multiple paths
                placeholders = ','.join(['?'] * len(file_paths))
                cursor = conn.execute(
                    f'SELECT id, file_path FROM track_metadata WHERE file_path IN ({placeholders})',
                    file_paths
                )
                return {row[1]: row[0] for row in cursor.fetchall()}  # {file_path: track_id}
        except Exception as e:
            print(f"Error finding track_ids: {e}")
            return {}
        
    def get_track_id_by_path(self, file_path: str) -> Optional[int]:
        """Get track_id using the file path (most reliable identifier)."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    'SELECT id FROM track_metadata WHERE file_path = ?', 
                    (file_path,)
                )
                result = cursor.fetchone()
                return result[0] if result else None
        except Exception as e:
            print(f"Error finding track_id for {file_path}: {e}")
            return None
        
    def track_metadata_exists(self, track_id: int) -> bool:
        """Check if a track_id exists in the tracks table."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    'SELECT 1 FROM track_metadata WHERE id = ?', 
                    (track_id,)
                )
                return cursor.fetchone() is not None
        except Exception as e:
            print(f"Error checking track existence {track_id}: {e}")
            return False
        
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
            print(f"Error starting scan log: {e}")
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
            print(f"Error ending scan log: {e}")
    
    def count_number_of_tracks(self) -> int:
        """Return the total number of tracks in the database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('SELECT COUNT(*) FROM track_metadata')
                count = cursor.fetchone()[0]
                return count
        except Exception as e:
            print(f"Error counting tracks: {e}")
            return 0