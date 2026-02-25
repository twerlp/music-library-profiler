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
    INTERPOLATE_MODE_LINEAR = 0
    INTERPOLATE_MODE_GRADIENT = 1

    def __init__(self, database: Database):
        self.database = database
        self._initialize_faiss()

    def _initialize_faiss(self):
        feature_dict = self.database.get_all_features()
        self.hpcp_index = faiss.IndexIDMap(faiss.IndexFlatL2(HPCP_DIMENSION))
        self.genre_index = faiss.IndexIDMap(faiss.IndexFlatL2(GENRE_DIMENSION))
        self.index_features(feature_dict=feature_dict)
    
    def create_playlist_gradient(self, source_track_path: Path, destination_track_path: Path, num_tracks: int, mode: int) -> Optional[List[int]]:
        """
        Create a playlist of songs that form a gradient between two tracks.
        """
        source_track_id = self.database.get_track_id_by_path(file_path=source_track_path)
        destination_track_id = self.database.get_track_id_by_path(file_path=destination_track_path)
        
        if source_track_id is None or destination_track_id is None:
            logger.error("Source or destination track not found in database")
            return None
        
        # Get features
        source_features = self.database.get_feature_by_id(track_id=source_track_id)
        target_features = self.database.get_feature_by_id(track_id=destination_track_id)
        
        if source_features is None or target_features is None:
            logger.error("Source or destination track features not found in database")
            return None
        
        # Calculate interpolation steps
        playlist = [source_track_id]
        current_track_id = source_track_id

        for step in range(1, num_tracks + 1):
            alpha = step / (num_tracks + 1)
            current_features = self.database.get_feature_by_id(track_id=current_track_id)

            # Interpolate HPCP and genre features
            if mode == self.INTERPOLATE_MODE_LINEAR:
                interpolated_hpcp = (1 - alpha) * source_features.hpcp + alpha * target_features.hpcp
                interpolated_genre = (1 - alpha) * source_features.genre + alpha * target_features.genre
            if mode == self.INTERPOLATE_MODE_GRADIENT:
                interpolated_hpcp = current_features.hpcp + alpha * (target_features.hpcp - current_features.hpcp)
                interpolated_genre = current_features.genre + alpha * (target_features.genre - current_features.genre)

            target_point = Features(
                hpcp=interpolated_hpcp,
                genre=interpolated_genre,
                bpm=current_features.bpm
            )

            # Find the closest track to the interpolated features
            similar_tracks = self.find_similar_tracks_to(
                track_path=None,
                track_id=current_track_id,
                features=target_point,
                num_tracks=50
            )

            if not similar_tracks:
                logger.warning(f"No similar tracks found for interpolation step {step}")
                continue

            # Select the best candidate that is not already in the playlist
            best_candidate = None
            for track_id, score in similar_tracks:
                if track_id not in playlist:
                    best_candidate = track_id
                    current_track_id = track_id
                    print(f"Selected track ID {track_id} with score {score} for step {step}")
                    break
            
            if best_candidate is not None:
                playlist.append(best_candidate)
            else:
                logger.warning(f"No unique track found for interpolation step {step}")


        return playlist
    
    def create_playlist_include_track_direction(self, source_track_path: Path, destination_track_path: Path, 
                                        num_tracks: int) -> Optional[List[int]]:
        """
        
        """
        source_track_id = self.database.get_track_id_by_path(file_path=source_track_path)
        destination_track_id = self.database.get_track_id_by_path(file_path=destination_track_path)
        
        if source_track_id is None or destination_track_id is None:
            logger.error("Source or destination track not found")
            return None
        
        source_features = self.database.get_feature_by_id(track_id=source_track_id)
        dest_features = self.database.get_feature_by_id(track_id=destination_track_id)
        
        if source_features is None or dest_features is None:
            logger.error("Features not found")
            return None
        
        # Calculate total vector difference
        total_hpcp_diff = np.linalg.norm(dest_features.hpcp - source_features.hpcp)
        total_genre_diff = np.linalg.norm(dest_features.genre - source_features.genre)
        
        # Step sizes (equal magnitude reduction)
        hpcp_step = total_hpcp_diff / (num_tracks)
        genre_step = total_genre_diff / (num_tracks)
        
        playlist = [source_track_id]
        current_id = source_track_id
        
        for step in range(1, num_tracks + 1):
            # Progress from 0 (start) to 1 (end)
            progress = step / (num_tracks + 1)

            current_features = self.database.get_feature_by_id(track_id=current_id)
            current_hpcp = current_features.hpcp
            current_genre = current_features.genre
            current_bpm = current_features.bpm

            current_hpcp_dist = np.linalg.norm(current_hpcp - dest_features.hpcp)
            current_genre_dist = np.linalg.norm(current_genre - dest_features.genre)

            hpcp_direction = (dest_features.hpcp - current_hpcp) / current_hpcp_dist if current_hpcp_dist != 0 else np.zeros_like(current_hpcp)
            genre_direction = (dest_features.genre - current_genre) / current_genre_dist if current_genre_dist != 0 else np.zeros_like(current_genre)

            target_hpcp = current_hpcp + hpcp_step * hpcp_direction
            target_genre = current_genre + genre_step * genre_direction
            target_bpm = current_bpm
            
            target_features = Features(
                hpcp=target_hpcp,
                genre=target_genre,
                bpm=target_bpm
            )
            
            # Number of neighbors to search also decreases with randomness
            search_size = int(50 + 50 * (1 - progress))  # 100 early, 50 late
            
            similar_tracks = self.find_similar_tracks_to(
                track_id=current_id,
                features=target_features,
                num_tracks=search_size
            )
            
            if not similar_tracks:
                # Try broader search if needed
                similar_tracks = self.find_similar_tracks_to(
                    track_id=current_id,
                    features=target_features,
                    num_tracks=search_size * 2
                )
            
            if not similar_tracks:
                logger.warning(f"No tracks found at step {step}")
                break
                        
            for candidate_id, _ in similar_tracks:
                if candidate_id not in playlist and candidate_id != destination_track_id:
                    best_track_id = candidate_id
                    break
            
            if best_track_id is None:
                logger.warning(f"No suitable track at step {step}")
                break
            
            # Add track and update
            playlist.append(best_track_id)
            current_id = best_track_id
        
        # Add destination
        if destination_track_id not in playlist:
            playlist.append(destination_track_id)
        
        return playlist
    
    def create_playlist_multitrack_interpolate(self, track_paths: List[Path], num_tracks_between: int) -> Optional[List[int]]:
        if len(track_paths) < 2:
            logger.error("At least two tracks are required to create a playlist")
            return None
        
        playlist = []
        for i in range(len(track_paths) - 1):
            segment = self.create_playlist_include_track_direction(
                source_track_path=track_paths[i],
                destination_track_path=track_paths[i + 1],
                num_tracks=num_tracks_between
            )
            if segment is None:
                continue
            playlist.extend(segment[:-1])  # Exclude last track to avoid duplicates
        
        final_track = self.database.get_track_id_by_path(file_path=track_paths[-1])
        playlist.append(final_track)  # Add final track
        return playlist
    
    def create_playlist_multitrack_related(self, track_paths: List[Path], num_tracks_per_track: int) -> Optional[List[int]]:
        if len(track_paths) == 0:
            logger.error("At least one track is required to create a playlist")
            return None
        
        playlist = []
        for track_path in track_paths:
            track_id = self.database.get_track_id_by_path(file_path=track_path)
            if track_id is None:
                logger.warning(f"Track not found for path: {track_path}")
                continue
            
            similar_tracks = self.find_similar_tracks_to(
                track_id=track_id,
                num_tracks=num_tracks_per_track
            )
            if similar_tracks is None:
                continue
            
            # Add the original track and its similar tracks
            playlist.append(track_id)
            for similar_track_id, _ in similar_tracks:
                if similar_track_id != track_id and similar_track_id not in playlist:
                    playlist.append(similar_track_id)
        
        return playlist


    def get_weighted_score(self, hpcp_score: Optional[float], genre_score: Optional[float]) -> float:
        if genre_score and hpcp_score is None:
            hpcp_score = 0.0
        elif hpcp_score and genre_score is None:
            genre_score = 0.0
        elif hpcp_score is None and genre_score is None:
            return 0.0  # No scores available

        # Combine scores (weights can be adjusted)
        combined_score = (0.6 * hpcp_score) + (0.4 * genre_score)
        return combined_score

    def find_similar_tracks_to(self, track_path: Optional[Path]=None, track_id: Optional[int]=None, features: Optional[Features]=None, num_tracks: int=10) -> List[tuple[int, np.float32]]:
        try:
            if track_id is None and track_path is None:
                logger.error("Either track_path or track_id must be provided")
                return None
            if track_id is None:
                track_id = self.database.get_track_id_by_path(file_path=track_path)
            if track_path is None:
                track_path = self.database.get_track_metadata_by_id(track_id=track_id)["file_path"]
            
            # Gather tracks with HPCP similarity
            if features is None:
                features = self.database.get_feature_by_id(track_id=track_id)
            if not features:
                logger.error(f"No features found for track ID {track_id}")
                return None

            hpcp_distances, hpcp_track_ids = self.hpcp_index.search(np.float32(features.hpcp).reshape(1, -1), num_tracks)
            genre_distances, genre_track_ids = self.genre_index.search(np.float32(features.genre).reshape(1, -1), num_tracks)

            hpcp_rankings = {}
            genre_rankings = {}

            # Populate HPCP rankings (lower distance = better)
            for rank, (distance, track_id_val) in enumerate(zip(hpcp_distances[0], hpcp_track_ids[0])):
                hpcp_rankings[track_id_val] = 1.0 / (1.0 + distance)  # Convert distance to similarity score
                
            # Populate genre rankings (higher cosine similarity = better)
            for rank, (distance, track_id_val) in enumerate(zip(genre_distances[0], genre_track_ids[0])):
                genre_rankings[track_id_val] = 1.0 / (1.0 + distance)

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

                combined_score = self.get_weighted_score(hpcp_score, genre_score)

                if track_id_val in bpm_compatible_tracks:
                    combined_score *= 1.1  # Boost score for BPM compatible tracks

                track_scores.append((track_id_val, combined_score))
            
            # Sort tracks by combined score in descending order
            track_scores.sort(key=lambda x: x[1], reverse=True)
            
            # print("track scores:", track_scores)
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
        