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

logger = logging.getLogger(__name__)

HPCP_DIMENSION=12 # HPCP is 1x12

class TrackSimilarity:
    def __init__(self, database: Database):
        self.database = database
        self._initialize_faiss_HPCP()

    def _initialize_faiss_HPCP(self):
        hpcp_dict = self.database.get_all_hpcp()
        self.hpcp_index = faiss.IndexIDMap(faiss.IndexFlatIP(HPCP_DIMENSION))
        self.index_HPCP(hpcp_dict=hpcp_dict)
    
    def find_similar_tracks_to(self, track_path: Path, num_tracks: int) -> tuple[np.ndarray[np.float32], np.ndarray[np.int64]]:
        try:
            track_id = self.database.get_track_id_by_path(file_path=track_path)
            
            # Gather tracks with HPCP similarity
            hpcp = self.database.get_hpcp(track_id=track_id)

            logger.info(f"HPCP shape: {hpcp.shape}")
            logger.info(f"HPCP values: {hpcp}")
            logger.info(f"HPCP length: {len(hpcp)}")
            
            # Check FAISS index state
            logger.info(f"FAISS index dimension: {self.hpcp_index.d}")
            logger.info(f"FAISS index total vectors: {self.hpcp_index.ntotal}")

            hpcp_distances, hpcp_track_ids = self.hpcp_index.search(np.float32(hpcp).reshape(1, -1), num_tracks)

            # TODO: Gather tracks with close BPM / nice BPM ratios

            # TODO: Gather tracks with similar sound profiles

            # TODO: Gather tracks with similar genres

            # TODO: 

            print(hpcp_distances)
            print(hpcp_track_ids)
            return (hpcp_distances, hpcp_track_ids)
        except Exception as e:
            logger.exception(f"Error finding similar tracks to {track_path}: {e}")
            return None
    
    def index_HPCP(self, hpcp_dict: Dict[int, np.ndarray]):
        if not hpcp_dict:
            logger.warning("Empty HPCP dictionary provided")
            return
        
        # Convert to numpy arrays
        np_embeddings = np.array(list(hpcp_dict.values()), dtype=np.float32)
        ids_array = np.array(list(hpcp_dict.keys()), dtype=np.int64)
        
        # Validate shapes
        if np_embeddings.shape[1] != HPCP_DIMENSION:
            logger.error(f"HPCP dimension mismatch: expected {HPCP_DIMENSION}, got {np_embeddings.shape[1]}")
            return
        
        if len(np_embeddings) != len(ids_array):
            logger.error("Mismatch between number of vectors and IDs")
            return

        self.hpcp_index.add_with_ids(np_embeddings, ids_array)
        logger.info(f"Indexed {len(np_embeddings)} HPCP vectors")
        