# audio_feature_extractor.py - Analyze audio files to extract features like tempo, key, and spectral characteristics.
# Previous work:
# RNN model for key detection: https://eurasip.org/Proceedings/Eusipco/Eusipco2024/pdfs/0000026.pdf
# SFTF https://medium.com/@oluyaled/detecting-musical-key-from-audio-using-chroma-feature-in-python-72850c0ae4b1, https://gist.github.com/bmcfee/1f66825cef2eb34c839b42dddbad49fd, https://arxiv.org/pdf/2505.17259, https://rnhart.net/articles/key-finding/ 
# Datasets https://github.com/ismir/mir-datasets/blob/master/mir-datasets.yaml
# Detecting both key and mode https://github.com/mrueda/music-key-detector/blob/main/music_key_detector.py
# Using Essentia to detect key and scale using HPCP: https://essentia.upf.edu/tutorial_tonal_hpcpkeyscale.html (no great general key profile)
# Someone building a similar project to mine: https://github.com/RDSoria/music-recommender/tree/main

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
from core.fingerprint import compute_fingerprint
from core.embedding_client import EmbeddingClient
from core.onnx_inference import compute_genre_embeddings, load_onnx_session
import utils.resource_manager as rm

logger = logging.getLogger(__name__)

CHROMATIC_SCALE = ['C', 'C#', 'D', 'D#', 'E', 'F',
                  'F#', 'G', 'G#', 'A', 'A#', 'B']
SAMPLING_RATE = 22050
EMBEDDING_MODEL_ONNX = rm.project_path("models/discogs-effnet-bsdynamic-1.onnx")

class AudioFeatureExtractor:
    def __init__(self, 
                 track_list: List[Path], 
                 database: Database, 
                 track_similarity: TrackSimilarity,
                 progress_callback: Callable = None,
                 embedding_client: EmbeddingClient = None,
                 ):
        self.track_list = track_list
        self.database = database
        self.track_similarity = track_similarity
        self.progress_callback = progress_callback
        self.embedding_client = embedding_client
    
    def find_features_of_list(self,
                              batch_size: int = 32, 
                              max_workers: int = None) -> Dict[str, Any]:
        track_mapping = self.database.get_track_ids_by_paths(self.track_list)

        if not track_mapping:
            logger.warning("Empty track mapping for feature extraction.")
            return {
                "successful_files": {},
                "errors": ["No track mappings for feature extraction."]
            }
        inverse_mapping = {value: key for key, value in track_mapping.items()}

        missing_hpcps, existing_hpcps = self.database.get_missing_features(track_ids=list(track_mapping.values()))

        missing_features = missing_hpcps
        existing_features = existing_hpcps
        if not missing_features:
            return {
                "successful_files": existing_features,
                "errors": []
            }

        total_missing = len(missing_features)
        missing_list = list(missing_features)
        errors = []
        successful_files = existing_hpcps
        current_feature_batch = {}
        total_stored = 0
        cache_hit_count = 0
        onnx_session = None

        def _flush_batch():
            nonlocal current_feature_batch, total_stored, successful_files
            if current_feature_batch:
                try:
                    stored = self._store_batch(feature_batch=current_feature_batch)
                    total_stored += len(stored)
                    successful_files |= stored
                except Exception as e:
                    logger.exception(f"Error storing batch: {e}")
                    errors.append(f"Batch store error: {e}")
                current_feature_batch.clear()

        offset = 0
        while offset < total_missing:
            chunk = missing_list[offset:offset + batch_size]
            audio_cache = {}
            loaded = 0

            for i, track_id in enumerate(chunk):
                file_path = inverse_mapping[track_id]
                if self.progress_callback:
                    self.progress_callback(offset + i, total_missing, f"Loading {file_path}")
                try:
                    audio, sampling_rate = load_audio_file(file_path)
                    audio_cache[track_id] = (audio, sampling_rate)
                    loaded += 1
                except Exception:
                    logger.warning(f"Failed to load audio for {file_path}")

            tracks_needing_genre = []
            fingerprint_map = {}

            for i, track_id in enumerate(chunk):
                if track_id not in audio_cache:
                    continue
                file_path = inverse_mapping[track_id]
                audio, sr = audio_cache[track_id]

                fingerprint = None
                if self.embedding_client:
                    try:
                        fingerprint, _ = compute_fingerprint(audio, sr)
                    except Exception:
                        pass

                if fingerprint and self.embedding_client:
                    if self.progress_callback and i % 10 == 0:
                        self.progress_callback(offset + i, total_missing, f"Looking up {file_path}")
                    try:
                        cached = self.embedding_client.lookup(fingerprint)
                        if cached:
                            logger.info(f"Cache hit for {file_path}")
                            cache_hit_count += 1
                            current_feature_batch[track_id] = cached
                            if len(current_feature_batch) >= batch_size:
                                _flush_batch()
                            continue
                    except Exception:
                        pass

                if fingerprint:
                    fingerprint_map[track_id] = fingerprint
                tracks_needing_genre.append(track_id)

            _flush_batch()

            if self.progress_callback:
                self.progress_callback(offset + loaded, total_missing, f"Cache: {cache_hit_count}, local: {len(tracks_needing_genre)}")

            genre_map = {}
            if tracks_needing_genre:
                if onnx_session is None:
                    onnx_session = load_onnx_session(str(EMBEDDING_MODEL_ONNX))
                audio_list = [audio_cache[tid][0] for tid in tracks_needing_genre if tid in audio_cache]
                valid_ids = [tid for tid in tracks_needing_genre if tid in audio_cache]
                if audio_list:
                    if self.progress_callback:
                        self.progress_callback(offset, total_missing, "Computing genre embeddings (ONNX)")
                    try:
                        embeddings = compute_genre_embeddings(audio_list, onnx_session)
                        for tid, emb in zip(valid_ids, embeddings):
                            genre_map[tid] = emb
                    except Exception as e:
                        logger.exception(f"ONNX inference failed: {e}")

            remaining = [tid for tid in tracks_needing_genre if tid in audio_cache]
            if remaining:
                if self.progress_callback:
                    self.progress_callback(offset, total_missing, f"HPCP + BPM: {len(remaining)} tracks")

                with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                    future_to_id = {}
                    for track_id in remaining:
                        audio, sr = audio_cache[track_id]
                        genre = genre_map.get(track_id)
                        future = executor.submit(
                            extract_hpcp_bpm, audio, sr, genre, inverse_mapping[track_id],
                        )
                        future_to_id[future] = track_id

                    completed = 0
                    for future in concurrent.futures.as_completed(future_to_id):
                        track_id = future_to_id[future]
                        file_path = inverse_mapping[track_id]

                        try:
                            feature_data = future.result()
                            if feature_data is not None:
                                current_feature_batch[track_id] = feature_data

                                if self.embedding_client and track_id in fingerprint_map:
                                    try:
                                        self.embedding_client.upload(
                                            fingerprint_map[track_id], feature_data,
                                        )
                                    except Exception:
                                        pass
                            else:
                                logger.warning(f"No feature data extracted for {file_path}")
                                errors.append(f"No feature data: {file_path}")
                        except Exception as e:
                            track_metadata = self.database.get_track_metadata_by_id(track_id)
                            file_name = track_metadata["file_name"] if track_metadata else "unknown"
                            error_msg = f"Error processing {file_name}: {e}"
                            errors.append(error_msg)
                            logger.exception(error_msg)
                            continue

                        completed += 1
                        if self.progress_callback and completed % 10 == 0:
                            self.progress_callback(offset + completed, total_missing, f"HPCP + BPM: {file_path}")

                        if len(current_feature_batch) >= batch_size:
                            _flush_batch()

            _flush_batch()
            audio_cache.clear()
            fingerprint_map.clear()
            genre_map.clear()

            offset += len(chunk)

        if self.progress_callback:
            self.progress_callback(total_missing, total_missing, "Feature extraction complete!")

        total_processed = total_stored + cache_hit_count
        logger.info(f"Feature extraction complete. Processed: {total_processed}, Stored: {total_stored}, Cache hits: {cache_hit_count}, Errors: {len(errors)}")

        if errors:
            logger.warning(f"Encountered {len(errors)} errors during feature extraction")

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


def extract_hpcp_bpm(
    audio_time_series: np.ndarray,
    sampling_rate: int,
    genre: np.ndarray | None,
    audio_file_path: Path,
) -> Features | None:
    if genre is None:
        return None

    audio_time_series_clean, _ = librosa.effects.trim(audio_time_series, top_db=20)
    hpcp = find_hpcp(audio_time_series=audio_time_series_clean, sampling_rate=sampling_rate)
    bpm, _ = find_bpm(audio_time_series=audio_time_series_clean, sampling_rate=sampling_rate)

    return Features(hpcp=hpcp, bpm=float(bpm), genre=genre)

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



