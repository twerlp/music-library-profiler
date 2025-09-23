# database.py - Database interaction layer using SQLite. 
import sqlite3
import utils.constants as const
import utils.resource_manager as rm

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
            conn.execute(f'''
                CREATE TABLE IF NOT EXISTS tracks (
                    {',\n'.join([f'{field} {sql_type}' for field, sql_type in const.METADATA_FIELD_TYPES.items()])}
                )
            ''')
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

    def insert_track(self, metadata):
        """Insert a track's metadata into the database. (Worker thread)"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(f'''
                    INSERT OR IGNORE INTO tracks (
                        {", ".join(const.METADATA_FIELD_TYPES.keys())}
                    ) VALUES ({", ".join(["?"] * len(const.METADATA_FIELD_TYPES.keys()))})
                ''', (
                    [metadata.get(field) for field in const.METADATA_FIELD_TYPES.keys()]
                ))
        except Exception as e:
            print(f"Error inserting track {metadata.get("file_name")}: {e}")
    
    def fetch_all_tracks(self):
        """Fetch all tracks from the database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('SELECT * FROM tracks')
                tracks = []
                for row in cursor.fetchall():
                    track = {list(const.METADATA_FIELD_TYPES.keys())[i]: row[i] for i in range(len(const.METADATA_FIELD_TYPES.keys()))}
                    tracks.append(track)
                return tracks
        except Exception as e:
            print(f"Error fetching tracks: {e}")
            return []
    
    def count_number_of_tracks(self):
        """Return the total number of tracks in the database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('SELECT COUNT(*) FROM tracks')
                count = cursor.fetchone()[0]
                return count
        except Exception as e:
            print(f"Error counting tracks: {e}")
            return 0
        
    def get_range_of_tracks(self, offset, limit):
        """Fetch a range of tracks."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                print(f"Fetching tracks with offset {offset} and limit {limit}")
                cursor = conn.execute('SELECT * FROM tracks LIMIT ? OFFSET ?', (limit, offset))
                tracks = []
                for row in cursor.fetchall():
                    track = {list(const.METADATA_FIELD_TYPES.keys())[i]: row[i] for i in range(len(const.METADATA_FIELD_TYPES.keys()))}
                    tracks.append(track)
                return tracks
        except Exception as e:
            print(f"Error fetching range of tracks: {e}")
            return []
    
    def get_track_by_id(self, track_id):
        """Fetch a single track by its ID."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('SELECT * FROM tracks WHERE id = ?', (track_id,))
                row = cursor.fetchone()
                if row:
                    track = {const.METADATA_FIELD_TYPES.keys()[i]: row[i] for i in range(len(const.METADATA_FIELD_TYPES.keys()))}
                    return track
                return None
        except Exception as e:
            print(f"Error fetching track by ID {track_id}: {e}")
            return None

    def start_scan(self, directory):
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
    
    def end_scan(self, scan_id, total_files, successful_files, errors):
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
    
    # Generate SQL column definitions for a CREATE TABLE statement
    def generate_sql_columns():
        columns = []
        for field, sql_type in const.METADATA_FIELD_TYPES.items():
            columns.append(f"{field} {sql_type}")
        return ",\n    ".join(columns)