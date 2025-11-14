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

class TrackSimilarity:
    def __init__(self, database: Database):
        self.database = database
        self._initialize_faiss()

    def _initialize_faiss(self):
        feature_dict = self.database.get_all_features()
        self.hpcp_index = faiss.IndexIDMap(faiss.IndexFlatL2(HPCP_DIMENSION))
        self.index_features(feature_dict=feature_dict)
    
    def find_similar_tracks_to(self, track_path: Path, num_tracks: int) -> tuple[np.ndarray[np.float32], np.ndarray[np.int64]]:
        try:
            track_id = self.database.get_track_id_by_path(file_path=track_path)
            
            # Gather tracks with HPCP similarity
            features = self.database.get_feature_by_id(track_id=track_id)
            if not features:
                return None
            hpcp = features.hpcp

            logger.info(f"HPCP shape: {hpcp.shape}")
            logger.info(f"HPCP values: {hpcp}")
            logger.info(f"HPCP length: {len(hpcp)}")
            
            # Check FAISS index state
            logger.info(f"FAISS index dimension: {self.hpcp_index.d}")
            logger.info(f"FAISS index total vectors: {self.hpcp_index.ntotal}")

            hpcp_distances, hpcp_track_ids = self.hpcp_index.search(np.float32(hpcp).reshape(1, -1), num_tracks)

            print(str(type(hpcp_track_ids)))
            print(str(type(hpcp_track_ids.tolist())))
            # TODO: Gather tracks with similar sound profiles

            # TODO: Gather tracks with similar genres

            # TODO: Gather tracks with close BPM / nice BPM ratios
            feature_list = self.database.get_features_by_ids(track_ids=hpcp_track_ids[0].tolist())

            bpm_range_set = set()
            for i, f in feature_list.items():
                if f.bpm <= (features.bpm * 1.05) and f.bpm >= (features.bpm * 0.95):
                    print(i, "bpm diff", f.bpm, " ", features.bpm)
                    bpm_range_set.add(i)

            filtered_list = []
            for track_id in hpcp_track_ids[0].tolist():
                if track_id in bpm_range_set:
                    filtered_list.append(track_id)
            
            print(hpcp_distances)
            print(hpcp_track_ids)
            print(filtered_list)
            return (hpcp_distances, hpcp_track_ids)
        except Exception as e:
            logger.exception(f"Error finding similar tracks to {track_path}: {e}")
            return None
    
    def index_features(self, feature_dict: Dict[int, Features]):
        if not feature_dict:
            logger.warning("Empty feature dictionary provided")
            return
        
        # Convert to numpy arrays
        hpcp_list = []
        for features in feature_dict.values():
            hpcp_list.append(features.hpcp)

        np_hpcp_embeddings = np.array(hpcp_list, dtype=np.float32)
        ids_array = np.array(list(feature_dict.keys()), dtype=np.int64)
        
        # Validate shapes
        if np_hpcp_embeddings.shape[1] != HPCP_DIMENSION:
            logger.error(f"HPCP dimension mismatch: expected {HPCP_DIMENSION}, got {np_hpcp_embeddings.shape[1]}")
            return
        
        if len(np_hpcp_embeddings) != len(ids_array):
            logger.error("Mismatch between number of vectors and IDs")
            return

        self.hpcp_index.add_with_ids(np_hpcp_embeddings, ids_array)

        logger.info(f"Indexed {len(np_hpcp_embeddings)} HPCP vectors")
        