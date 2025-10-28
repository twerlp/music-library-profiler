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
    "file_path": "TEXT UNIQUE",
    "file_name": "TEXT",
    "directory": "TEXT",
    "extension": "TEXT",
    "size_bytes": "INTEGER",
    "last_modified": "DOUBLE",
    "last_accessed": "DOUBLE",
    "created": "DOUBLE"
}

# Twelve-tone scale
CHROMATIC_SCALE = ['C', 'C#', 'D', 'D#', 'E', 'F',
                  'F#', 'G', 'G#', 'A', 'A#', 'B']

# 7-note subsets of chromatic scale, listed with number of semitones between each note in scale
HEPTATONIC_SCALES = {
    "Major": [2, 2, 1, 2, 2, 2, 1],
    "Natural Minor": [2, 1, 2, 2, 1, 2, 2],
    "Harmonic Minor": [2, 1, 2, 2, 1, 3, 1],
    "Melodic Minor": [2, 1, 2, 2, 2, 2, 1],
    "Dorian": [2, 1, 2, 2, 2, 1, 2],
    "Phrygian": [1, 2, 2, 2, 1, 2, 2],
    "Lydian": [2, 2, 2, 1, 2, 2, 1],
    "Mixolydian": [2, 2, 1, 2, 2, 1, 2],
    "Locrian": [1, 2, 2, 1, 2, 2, 2]
}


 
# Weights for major/natural minor from Kumhansl and Schmuckler
MAJOR_PROFILE = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
MINOR_PROFILE = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]

