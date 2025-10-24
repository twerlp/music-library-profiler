# audio_feature_extractor.py - Analyze audio files to extract features like tempo, key, and spectral characteristics.
# Previous work:
# RNN model for key detection: https://eurasip.org/Proceedings/Eusipco/Eusipco2024/pdfs/0000026.pdf
# SFTF https://medium.com/@oluyaled/detecting-musical-key-from-audio-using-chroma-feature-in-python-72850c0ae4b1, https://gist.github.com/bmcfee/1f66825cef2eb34c839b42dddbad49fd, https://arxiv.org/pdf/2505.17259, https://rnhart.net/articles/key-finding/ 
# Datasets https://github.com/ismir/mir-datasets/blob/master/mir-datasets.yaml
# Detecting both key and mode https://github.com/mrueda/music-key-detector/blob/main/music_key_detector.py
# Using Essentia to detect key and scale using HPCP: https://essentia.upf.edu/tutorial_tonal_hpcpkeyscale.html (no great general key profile)

from typing import Optional, Callable, List, Any, Dict
import librosa
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt
import logging

from core.database import Database

logger = logging.getLogger(__name__)

CHROMATIC_SCALE = ['C', 'C#', 'D', 'D#', 'E', 'F',
                  'F#', 'G', 'G#', 'A', 'A#', 'B']
SAMPLING_RATE = 44100

# Potentially Essentia has a better method
def find_bpm_of_file(audio_file_path: Path):
    """
    Find the BPM of a file given the path.

    Args:
        audio_file_path: The filepath to an audio file to find the BPM of

    Returns:
        BPM as a tuple between global BPM and beat markers

    """
    #TODO: if BPM exists in file metadata, use it as estimate e.g, librosa.beat.beat_track(..., start_bpm=XX)
    audio_time_series, sampling_rate = load_audio_file(audio_file_path)
    bpm = librosa.beat.beat_track(y=audio_time_series, sr=sampling_rate)
    return bpm

# TODO: Consider xenharmonics/microtonal music, unconventional scales. I want a system that works for everything! Not now, not now.
def find_hpcp_of_file(audio_file_path: Path) -> np.ndarray:
    """
    Finds the harmonic pitch class profile (HPCP) of a file given the path

    Args:
        audio_file_path: The filepath to an audio file to find the HPCP of

    Returns:
        HPCP as a ndarray, element 0 being the note C

    """
    # Load audio file
    audio_time_series, sampling_rate = load_audio_file(audio_file_path)
    audio_time_series_clean, _ = librosa.effects.trim(audio_time_series, top_db=20) # Removes silence

    chroma = librosa.feature.chroma_cens(
        y=audio_time_series_clean,
        sr=sampling_rate,
        n_chroma=12,
        n_octaves=9,
        bins_per_octave=48,
        tuning=librosa.pitch_tuning(audio_time_series_clean)
    )

    # So with this, we have a chromagram that shows each note being used over time
    # Need to find how often that note is used. Take the mean? Or filter first.
    overall_dist = np.mean(chroma, axis=1)
    total = np.nansum(overall_dist)
    hpcp = overall_dist / total
    # plot_hpcp(hpcp)

    return hpcp

# Profile a given list of tracks and place them in our database
def find_hpcp_of_file_list(track_list: List[Path], 
                           database: Database, 
                           track_mapping: Dict[str, int] = None, 
                           batch_size: int = 128, 
                           progress_callback: Callable = None) -> Dict[str, int]:
    """
    Extract HPCP for multiple files and store using track_ids in a streaming fashion.
    
    Args:
        track_list: List of file paths to process
        database: Database instance for storage
        track_mapping: Optional pre-computed {file_path: track_id} mapping
        batch_size: Number of tracks to process before writing to database
        progress_callback: Optional callback for progress updates
    
    Returns:
        Processing data as a dictionary
            "total_files": number of files,
            "processed": number of files successfully processed,
            "stored": number of files successfully stored,
            "errors": number of errors
    """

    # TODO: Load/parse data in parallel (also the option of streaming the data with essentia if we really want to lower memory usage...)
    current_batch = {}
    total_processed = 0
    total_stored = 0
    errors = []

    if track_mapping is None:
        track_mapping = {}

    logger.info(f"Starting HPCP extraction for {len(track_list)} tracks with batch size {batch_size}")

    # Process in batches and store results to database
    for i, file_path in enumerate(track_list):
        try:
            if progress_callback and i % 10 == 0:  # Report progress every 10 files
                progress_callback(i, len(track_list), f"Processing {file_path.name}")
            
            # Extract the HPCP for current file
            hpcp_data = find_hpcp_of_file(file_path)

            if hpcp_data is not None:
                current_batch[file_path] = hpcp_data
                total_processed += 1
            else:
                logger.warning(f"No HPCP data extracted for {file_path}")
                errors.append(f"No HPCP data: {file_path}")
            
            # Store to database if we have reached the batch size
            if len(current_batch) >= batch_size:
                stored_in_batch = _process_and_store_batch(current_batch, database, track_mapping)
                total_stored += stored_in_batch
                current_batch.clear()
                logger.debug(f"Processed batch: {i+1}/{len(track_list)} files, stored {stored_in_batch} HPCP fingerprints")
        
        except Exception as e:
            error_msg = f"Error extracting HPCP for {file_path}: {e}"
            logger.exception(error_msg)
            errors.append(error_msg)
            continue
    
    # Store stragglers (final batch) to database
    if current_batch:
        stored_in_batch = _process_and_store_batch(current_batch, database, track_mapping)
        total_stored += stored_in_batch
        logger.debug(f"Processed batch: {i+1}/{len(track_list)} files, stored {stored_in_batch} HPCP fingerprints")

    logger.info(f"HPCP extraction complete. Processed: {total_processed}, Stored: {total_stored}, Errors: {len(errors)}")

    if errors:
        logger.warning(f"Encountered {len(errors)} errors during HPCP extraction")

    if progress_callback:
        progress_callback(len(track_list), len(track_list), "HPCP extraction complete!")

    return {
        "total_files": len(track_list),
        "processed": total_processed,
        "stored": total_stored,
        "errors": len(errors)
    }

def _process_and_store_batch(hpcp_batch: Dict[Path, np.ndarray], 
                             database: Database, 
                             track_mapping: Dict[str, int]) -> int:
    """
    Process a batch of HPCP data and store in database.
    
    Returns:
        Number of successfully stored HPCP fingerprints

    """
    # Get file paths that aren't in our pre-computed track_mapping
    missing_paths = [str(path) for path in hpcp_batch.keys() if str(path) not in track_mapping]
    
    # Look up missing track_ids
    if missing_paths:
        new_mapping = database.get_track_ids_by_paths(missing_paths)
        track_mapping.update(new_mapping)
    
    # Convert to track_id-based dictionary
    track_hpcp_data = {}  # {track_id: hpcp_data}
    missing_tracks = []
    
    for file_path, hpcp_data in hpcp_batch.items():
        track_id = track_mapping.get(str(file_path))
        if track_id:
            track_hpcp_data[track_id] = hpcp_data
        else:
            missing_tracks.append(str(file_path))
    
    # Report missing tracks
    if missing_tracks:
        logger.warning(f"Batch: {len(missing_tracks)} tracks not found in database")
        for path in missing_tracks[:3]:  # Log first 3 missing tracks
            logger.debug(f"Missing track: {path}")
    
    # Store the batch
    if track_hpcp_data:
        success_count = database.batch_insert_hpcp(track_hpcp_data)
        if success_count != len(track_hpcp_data):
            logger.warning(f"Batch storage: expected {len(track_hpcp_data)}, got {success_count}")
        return success_count
    else:
        logger.warning("Batch: No valid HPCP data to store")
        return 0

#TODO: Implement cross-correlation for HPCP
def compare_hpcp(hpcp1, hpcp2):
    pass # return maximum similarity and the transposition

def load_audio_file(audio_file_path: Path):
    """
    Loads an audio file using librosa -- TODO: we rely on deprecated librosa loading functionality, fix this
    Args:
        audio_file_path: Path of the file to load

    Returns:
        audio_time_series: The audio time series as an np.ndarray
        sampling_rate: Sampling rate of audio_time_series
    """
    audio_time_series, sampling_rate = librosa.load(audio_file_path, sr=SAMPLING_RATE)
    return audio_time_series, sampling_rate

def plot_fft(frequencies, magnitudes):
    plt.figure(figsize=(12, 7))
    plt.plot(frequencies, magnitudes, color='blue', label='FFT Magnitude')
    plt.title('FFT Magnitude Spectrum with Notes')
    plt.xlabel('Frequency (Hz)')
    plt.ylabel('Magnitude')
    plt.grid(True)

    # Map frequencies to notes for the secondary axis
    displayed_notes = []
    for freq in frequencies:
        if 20 <= freq <= 20000:  # Only process within a musical range
            midi = 69 + 12 * np.log2(freq / 440.0)
            pitch_class = int(round(midi)) % 12
            note = CHROMATIC_SCALE[pitch_class]
            if not displayed_notes or freq - displayed_notes[-1][0] > 1000:
                displayed_notes.append((freq, note))

    # Add a secondary axis with spaced notes
    ax = plt.gca()
    ax.set_xlim(20, 5000)
    ax2 = ax.twiny()
    ax2.set_xlim(ax.get_xlim())
    ax2.set_xticks([item[0] for item in displayed_notes])
    ax2.set_xticklabels([item[1] for item in displayed_notes], fontsize=10, rotation=45)
    ax2.set_xlabel('Notes')
    
    plt.show()

def plot_hpcp(hpcp):
    plt.figure(figsize=(12, 7))
    plt.plot(range(0,12), hpcp, color='blue', label='HPCP')
    plt.title('HPCP with Notes')
    plt.xlabel('Note')
    plt.ylabel('Magnitude')
    plt.grid(True)

    # Add a secondary axis with spaced notes
    ax = plt.gca()
    ax.set_xlim(0, 11)
    ax2 = ax.twiny()
    ax2.set_xlim(ax.get_xlim())
    ax2.set_xticks(range(0,12))
    ax2.set_xticklabels(CHROMATIC_SCALE, fontsize=10, rotation=45)
    ax2.set_xlabel('Notes')
    
    plt.show()


audio_files = []
audio_files.append("/home/twerp/Music/Tatsuro Yamashita - Spacy/1-04 - Candy.aiff")
audio_files.append("/home/twerp/Music/BeautyWorld - Beautiful World/BeautyWorld - Beautiful World - 04 Pine Bristle.m4a") # A minor (hum ode to joy)
audio_files.append("/home/twerp/Downloads/A4.mp3")
audio_files.append("/home/twerp/Music/Clannad - Fuaim/04 - Clannad - La Brea Fan Dtuath.mp3")
audio_files.append("/home/twerp/Music/Michael Bolton - Soul Provider/03 - Michael Bolton - It's Only My Heart.mp3")



