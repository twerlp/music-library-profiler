import logging

import numpy as np
import requests

from core.features import Features

logger = logging.getLogger(__name__)


class EmbeddingClient:
    def __init__(self, server_url: str):
        self.server_url = server_url.rstrip("/")

    def lookup(self, fingerprint: str) -> Features | None:
        try:
            r = requests.post(
                f"{self.server_url}/embeddings/lookup",
                json={"fingerprint": fingerprint},
                timeout=5,
            )
            if r.status_code == 200:
                data = r.json()
                return Features(
                    hpcp=np.array(data["hpcp"], dtype=np.float32),
                    bpm=float(data["bpm"]),
                    genre=np.array(data["genre_embedding"], dtype=np.float32),
                )
            return None
        except Exception:
            return None

    def upload(self, fingerprint: str, features: Features) -> bool:
        try:
            payload = {
                "fingerprint": fingerprint,
                "hpcp": features.hpcp.tolist(),
                "bpm": float(features.bpm),
                "genre_embedding": features.genre.tolist(),
            }
            r = requests.post(
                f"{self.server_url}/embeddings",
                json=payload,
                timeout=5,
            )
            return r.status_code == 201
        except Exception:
            return False
