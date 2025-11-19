# track_similarity.py - Compute similarity between songs using audio features and known similarities from Last.fm
# LastFM song similarity paper: https://arxiv.org/pdf/1704.03844
# Audio based similarity: https://cosine.club uses https://repositori.upf.edu/bitstream/handle/10230/54158/Alonso_ismir_musi.pdf

import faiss
import numpy as np
from typing import List, Dict, Optional, Any
from pathlib import Path
from core.database import Database
import utils.resource_manager as rm
import logging

from core.features import Features

logger = logging.getLogger(__name__)

HPCP_DIMENSION=12 # HPCP is 1x12
GENRE_DIMENSION=1280 # Genre embeddings dimension from EFFNET reduced to 1x1280

class TrackSimilarity:
    def __init__(self, database: Database):
        self.database = database
        self._initialize_faiss()

    def _initialize_faiss(self):
        feature_dict = self.database.get_all_features()
        self.hpcp_index = faiss.IndexIDMap(faiss.IndexFlatL2(HPCP_DIMENSION))
        self.genre_index = faiss.IndexIDMap(faiss.IndexFlatIP(GENRE_DIMENSION))
        self.index_features(feature_dict=feature_dict)
    
    def find_similar_tracks_to(self, track_path: Path, num_tracks: int) -> tuple[np.ndarray[np.float32], np.ndarray[np.int64]]:
        try:
            track_id = self.database.get_track_id_by_path(file_path=track_path)
            
            # Gather tracks with HPCP similarity
            features = self.database.get_feature_by_id(track_id=track_id)
            if not features:
                return None

            # logger.info(f"HPCP shape: {features.hpcp.shape}")
            # logger.info(f"HPCP values: {features.hpcp}")
            # logger.info(f"HPCP length: {len(features.hpcp)}")

            # logger.info(f"Genre shape: {features.genre.shape}")
            # logger.info(f"Genre values: {features.genre}")
            # logger.info(f"Genre length: {len(features.genre)}")
            
            # # Check FAISS index state
            # logger.info(f"FAISS index dimension: {self.hpcp_index.d}")
            # logger.info(f"FAISS index total vectors: {self.hpcp_index.ntotal}")

            hpcp_distances, hpcp_track_ids = self.hpcp_index.search(np.float32(features.hpcp).reshape(1, -1), num_tracks)
            genre_distances, genre_track_ids = self.genre_index.search(np.float32(features.genre).reshape(1, -1), num_tracks)
            # TODO: Gather tracks with similar sound profiles

            hpcp_rankings = {}
            genre_rankings = {}

            hpcp_mean = np.mean(hpcp_distances)
            genre_mean = np.mean(genre_distances)

            # Populate HPCP rankings (lower distance = better)
            for rank, (distance, track_id_val) in enumerate(zip(hpcp_distances[0], hpcp_track_ids[0])):
                hpcp_rankings[track_id_val] = 1.0 / (1.0 + distance/hpcp_mean)  # Convert distance to similarity score
                
            # Populate genre rankings (higher cosine similarity = better)
            for rank, (distance, track_id_val) in enumerate(zip(genre_distances[0], genre_track_ids[0])):
                genre_rankings[track_id_val] = distance/genre_mean

            # Get all unique track IDs from both searches
            all_track_ids = set(hpcp_track_ids[0]) | set(genre_track_ids[0])
            all_track_ids = [int(tid) for tid in all_track_ids]  # This converts np.int64 to int

            bpm_compatible_tracks = set()
            feature_list = self.database.get_features_by_ids(track_ids=all_track_ids)
            
            for i, f in feature_list.items():
                if f.bpm <= (features.bpm * 1.05) and f.bpm >= (features.bpm * 0.95):
                    bpm_compatible_tracks.add(i)

            track_scores = []
            for track_id_val in all_track_ids:
                hpcp_score = hpcp_rankings.get(track_id_val)
                genre_score = genre_rankings.get(track_id_val)

                if genre_score and hpcp_score is None:
                    hpcp_score = 0.0
                elif hpcp_score and genre_score is None:
                    genre_score = 0.0
                elif hpcp_score is None and genre_score is None:
                    continue  # Skip tracks with no scores, should not happen

                # Combine scores (weights can be adjusted)
                combined_score = (0.6 * hpcp_score) + (0.4 * genre_score)

                if track_id_val in bpm_compatible_tracks:
                    combined_score *= 1.1  # Boost score for BPM compatible tracks

                track_scores.append((track_id_val, combined_score))
            
            # Sort tracks by combined score in descending order
            track_scores.sort(key=lambda x: x[1], reverse=True)
            
            print("track scores:", track_scores)
            return (track_scores)
        except Exception as e:
            logger.exception(f"Error finding similar tracks to {track_path}: {e}")
            return None
    
    def index_features(self, feature_dict: Dict[int, Features]):
        if not feature_dict:
            logger.warning("Empty feature dictionary provided")
            return
        
        # Convert to numpy arrays
        hpcp_list = []
        genre_list = []
        for features in feature_dict.values():
            hpcp_list.append(features.hpcp)
            genre_list.append(features.genre)

        np_hpcp_embeddings = np.array(hpcp_list, dtype=np.float32)
        np_genre_embeddings = np.array(genre_list, dtype=np.float32)
        ids_array = np.array(list(feature_dict.keys()), dtype=np.int64)
        
        # Validate shapes
        if np_hpcp_embeddings.shape[1] != HPCP_DIMENSION:
            logger.error(f"HPCP dimension mismatch: expected {HPCP_DIMENSION}, got {np_hpcp_embeddings.shape[1]}")
            return
        
        if np_genre_embeddings.shape[1] != GENRE_DIMENSION:
            logger.error(f"Genre dimension mismatch: expected {GENRE_DIMENSION}, got {np_genre_embeddings.shape[1]}")
            return
        
        if len(np_hpcp_embeddings) != len(ids_array):
            logger.error("Mismatch between number of HPCP vectors and IDs")
            return
        
        if len(np_genre_embeddings) != len(ids_array):
            logger.error("Mismatch between number of genre vectors and IDs")
            return

        self.hpcp_index.add_with_ids(np_hpcp_embeddings, ids_array)
        self.genre_index.add_with_ids(np_genre_embeddings, ids_array)

        logger.info(f"Indexed {len(np_hpcp_embeddings)} HPCP vectors and {len(np_genre_embeddings)} genre vectors")
        