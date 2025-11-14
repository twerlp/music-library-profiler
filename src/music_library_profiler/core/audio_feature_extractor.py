# audio_feature_extractor.py - Analyze audio files to extract features like tempo, key, and spectral characteristics.
# Previous work:
# RNN model for key detection: https://eurasip.org/Proceedings/Eusipco/Eusipco2024/pdfs/0000026.pdf
# SFTF https://medium.com/@oluyaled/detecting-musical-key-from-audio-using-chroma-feature-in-python-72850c0ae4b1, https://gist.github.com/bmcfee/1f66825cef2eb34c839b42dddbad49fd, https://arxiv.org/pdf/2505.17259, https://rnhart.net/articles/key-finding/ 
# Datasets https://github.com/ismir/mir-datasets/blob/master/mir-datasets.yaml
# Detecting both key and mode https://github.com/mrueda/music-key-detector/blob/main/music_key_detector.py
# Using Essentia to detect key and scale using HPCP: https://essentia.upf.edu/tutorial_tonal_hpcpkeyscale.html (no great general key profile)

from typing import Optional, Callable, List, Any, Dict, Set, Tuple
from dataclasses import dataclass
import librosa
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt
import logging
import concurrent.futures

from core.database import Database
from core.features import Features
from core.track_similarity import TrackSimilarity

logger = logging.getLogger(__name__)

CHROMATIC_SCALE = ['C', 'C#', 'D', 'D#', 'E', 'F',
                  'F#', 'G', 'G#', 'A', 'A#', 'B']
SAMPLING_RATE = 22050

class AudioFeatureExtractor:
    def __init__(self, 
                 track_list: List[Path], 
                 database: Database, 
                 track_similarity: TrackSimilarity,
                 progress_callback: Callable = None
                 ):
        self.track_list = track_list
        self.database = database
        self.track_similarity = track_similarity
        self.progress_callback = progress_callback
    
    def find_features_of_list(self,
                              batch_size: int = 128, 
                              max_workers: int = None) -> Dict[str, Any]:
        """
        Extract features for multiple files and store using track_ids.
        Multicore execution.
        
        Args:
            batch_size: Number of tracks to process before writing to database
            max_workers: Number of cores to use
        
        Returns:
            Processing data as a dictionary
                "successful_files": number of files which were successfully stored to the database,
                "errors": the errors we encountered
        """
        track_mapping = self.database.get_track_ids_by_paths(self.track_list)

        if not track_mapping:
            logger.warning("Empty track mapping for feature extraction.")
            return {
                "successful_files": {},
                "errors": ["No track mappings for feature extraction."]
            }
        inverse_mapping = {value: key for key, value in track_mapping.items()}

        # Find missing features
        missing_hpcps, existing_hpcps = self.database.get_missing_features(track_ids=list(track_mapping.values()))

        missing_features = missing_hpcps
        existing_features = existing_hpcps
        # If no features missing, skip feature extraction
        if not missing_features:
            return {
                "successful_files": existing_features,
                "errors": []
            }

        logger.info(f"Starting CPU-parallel feature extraction for {len(missing_features)} tracks with {max_workers} workers")

        with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
            # Submit HPCP work to the cores
            future_to_id = {
                executor.submit(find_features_of_file, inverse_mapping[track_id]): track_id 
                for track_id in missing_features
            }

            current_feature_batch = {} # Feature results for the current batch, indexed by file path
            total_processed = 0 # Total files which successfully gathered HPCP data
            total_stored = 0 # Total files which successfully stored HPCP data
            errors = [] # Errors generated during execution
            successful_files = existing_hpcps # Files that were successfully stored to the database

            for i, future in enumerate(concurrent.futures.as_completed(future_to_id)):
                track_id = future_to_id[future]
                if self.progress_callback and i % 10 == 0:
                    self.progress_callback(i, len(missing_hpcps), f"Processing {inverse_mapping[track_id]}")
                
                try:
                    feature_data = future.result()

                    if feature_data is not None:
                        current_feature_batch[track_id] = feature_data
                        total_processed += 1
                    else:
                        logger.warning(f"No feature data extracted for {inverse_mapping[track_id]}")
                        errors.append(f"No feature data: {inverse_mapping[track_id]}")
                    
                    # Store to database if we have reached the batch size
                    if len(current_feature_batch) >= batch_size:
                        stored_in_batch = self._store_batch(feature_batch=current_feature_batch)
                        total_stored += len(stored_in_batch)
                        successful_files | stored_in_batch
                        current_feature_batch.clear()
                        logger.debug(f"Processed batch: {i+1}/{len(missing_hpcps)} files, stored {len(stored_in_batch)} tracks' features.")

                except Exception as e:
                    error_msg = f"Error processing {self.database.get_track_metadata_by_id(track_id)["file_name"]}: {e}"
                    errors.append(error_msg)
                    logger.exception(error_msg)
                    continue
        
        # Store stragglers (final batch) to database
        if current_feature_batch:
            stored_in_batch = self._store_batch(feature_batch=current_feature_batch)
            total_stored += len(stored_in_batch)
            successful_files | stored_in_batch
            logger.debug(f"Processed batch: {i+1}/{len(missing_hpcps)} files, stored {len(stored_in_batch)} tracks' features")

        logger.info(f"Feature extraction complete. Processed: {total_processed}, Stored: {total_stored}, Errors: {len(errors)}")

        if errors:
            logger.warning(f"Encountered {len(errors)} errors during HPCP extraction")

        if self.progress_callback:
            self.progress_callback(len(missing_hpcps), len(missing_hpcps), "HPCP extraction complete!")

        return {
            "successful_files": successful_files,
            "errors": errors
        }
    
    def _store_batch(self, feature_batch: Dict[int, Features]) -> Set[Path]:
        """
        Store feature data in database.
        
        Returns:
            Files which successfully stored their features

        """
        # Store the batch
        logger.info(f"Storing {len(feature_batch)} HPCPs.")
        if feature_batch:
            successful_tracks = self.database.batch_insert_features(feature_data_dict=feature_batch)
            self.track_similarity.index_features(feature_dict=feature_batch)
            if successful_tracks is None:
                logger.warning("Batch: No valid features to store")
                return None
            if len(successful_tracks) != len(feature_batch):
                logger.warning(f"Batch storage: expected {len(feature_batch)}, got {len(successful_tracks)}")
            return successful_tracks


def find_features_of_file(audio_file_path: Path) -> Features:
    # Load audio file
    audio_time_series, sampling_rate = load_audio_file(audio_file_path)
    audio_time_series_clean, _ = librosa.effects.trim(audio_time_series, top_db=20) # Removes silence

    hpcp = find_hpcp(audio_time_series=audio_time_series_clean, sampling_rate=sampling_rate)
    bpm, beat_markers = find_bpm(audio_time_series=audio_time_series_clean, sampling_rate=sampling_rate)
    genre = find_genre(audio_file_path=audio_file_path)

    features = Features(hpcp=hpcp, bpm=float(bpm), genre=genre)
    return features

# TODO: Consider xenharmonics/microtonal music, unconventional scales. I want a system that works for everything! Not now, not now.
def find_hpcp(audio_time_series: np.ndarray, sampling_rate: int) -> np.ndarray:
    """
    Finds the harmonic pitch class profile (HPCP) of a file given the path

    Args:
        audio_file_path: The filepath to an audio file to find the HPCP of

    Returns:
        HPCP as a ndarray, element 0 being the note C

    """
    
    # Gather chromagram -- basically usage of each chromatic note throughout the song
    chroma = librosa.feature.chroma_cens(
        y=audio_time_series,
        sr=sampling_rate,
        n_chroma=12,
        n_octaves=7,
        bins_per_octave=36,
        tuning=librosa.pitch_tuning(audio_time_series)
    )

    # So with this, we have a chromagram that shows each note being used over time
    # Need to find how often that note is used. Take the mean? Or filter first.
    overall_dist = np.mean(chroma, axis=1)
    total = np.nansum(overall_dist)
    hpcp = overall_dist / total

    return hpcp

# Potentially Essentia has a better method
def find_bpm(audio_time_series: np.ndarray, sampling_rate: int) -> Tuple[np.float32, np.ndarray]:
    """
    Find the BPM of a file given the path.

    Args:
        audio_file_path: The filepath to an audio file to find the BPM of

    Returns:
        BPM as a tuple between global BPM and beat markers

    """
    # Potential improvement: use bpm gathered from metadata stage to estimate bpm
    bpm, beat_markers = librosa.beat.beat_track(y=audio_time_series, sr=sampling_rate)
    return bpm, beat_markers

def find_genre(audio_file_path: Path):
    pass

def load_audio_file(audio_file_path: Path):
    """
    Loads an audio file using librosa -- TODO: we rely on deprecated librosa loading functionality, fix this
    Args:
        audio_file_path: Path of the file to load

    Returns:
        audio_time_series: The audio time series as an np.ndarray
        sampling_rate: Sampling rate of audio_time_series
    """
    audio_time_series, sampling_rate = librosa.load(path=audio_file_path, sr=SAMPLING_RATE, mono=True)
    return audio_time_series, sampling_rate

#TODO: Implement cross-correlation for HPCP
def compare_hpcp(hpcp1, hpcp2):
    pass # return maximum similarity and the transposition

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



