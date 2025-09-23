# Librosa supported audio file extensions (aka codecs supported by soundfile or audioread)
# https://libsndfile.github.io/libsndfile/formats.html
SUPPORTED_AUDIO_EXTENSIONS = {".wav", ".aiff", "aif", ".aifc", ".m4a", ".aac", ".au", ".snd", \
                              ".dec", ".raw", ".paf", ".iff", ".svx", ".sf", ".voc", ".w64", \
                              ".mat4", ".mat5", ".pvf", ".xi", ".htk", ".caf", "sd2", ".flac", \
                              ".ogg", ".oga", ".opus", ".mp3"}

# Metadata fields and their SQL types 
# Stretch goal, add support for images embedded in tags ('APIC:' for ID3, 'covr' for MP4), type BLOB
METADATA_FIELD_TYPES = {
    "title": "TEXT",
    "artist": "TEXT",
    "album": "TEXT",
    "track_number": "TEXT",
    "genre": "TEXT",
    "year": "TEXT",
    "bpm": "INTEGER",
    "key": "TEXT",
    "duration": "INTEGER",
    "bitrate": "INTEGER",
    "sample_rate": "INTEGER",
    "channels": "INTEGER",
    "file_path": "TEXT",
    "file_name": "TEXT",
    "directory": "TEXT",
    "extension": "TEXT",
    "size_bytes": "INTEGER",
    "last_modified": "DOUBLE",
    "last_accessed": "DOUBLE",
    "created": "DOUBLE"
}