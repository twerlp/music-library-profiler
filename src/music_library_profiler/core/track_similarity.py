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
        self.hpcp_index_path = rm.project_path("indexes/hpcp.index")
        self.hpcp_index = self._initialize_faiss_HPCP()

    def _initialize_faiss_HPCP(self) -> faiss.IndexIDMap:
        if Path.exists(self.hpcp_index_path):
            return self.load_index()
        return faiss.IndexIDMap(faiss.IndexFlatIP(HPCP_DIMENSION))
    
    def find_similar_tracks_to(self, track_path: Path, num_tracks: int) -> tuple[np.ndarray[np.float32], np.ndarray[np.int64]]:
        try:
            track_id = self.database.get_track_id_by_path(file_path=track_path)
            hpcp = self.database.get_hpcp(track_id=track_id)
            distances, track_ids = self.hpcp_index.search(np.float32(hpcp).reshape(1, -1), num_tracks)
            print(distances)
            print(track_ids)
            return (distances, track_ids)
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

    def save_index(self):
        self.hpcp_index_path.parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.hpcp_index, str(self.hpcp_index_path))
    
    def load_index(self) -> faiss.Index:
        return faiss.read_index(str(self.hpcp_index_path))
        