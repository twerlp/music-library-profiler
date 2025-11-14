# features.py - The tracked features for each song. 
from dataclasses import dataclass
import numpy as np

@dataclass
class Features:
    """The features for a track"""
    hpcp: np.ndarray
    bpm: float
    genre: np.ndarray