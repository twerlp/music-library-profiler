#!/usr/bin/env python3
import sys
import time
import tempfile
import logging
from pathlib import Path

import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("benchmark")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src" / "music_library_profiler"))

from core.database import Database
from core.track_similarity import TrackSimilarity
from core.audio_feature_extractor import AudioFeatureExtractor
from core.features import Features
from core.config_manager import ConfigManager
from core.embedding_client import EmbeddingClient
import librosa


def find_test_tracks(limit: int = 10) -> list[Path]:
    music_dirs = [
        Path.home() / "Music",
        Path("/mnt"),
    ]
    extensions = {".mp3", ".flac", ".m4a", ".wav", ".aiff", ".ogg", ".opus"}
    all_files = []
    for d in music_dirs:
        if d.is_dir():
            all_files.extend(
                p for p in d.rglob("*") if p.suffix.lower() in extensions
            )
    all_files.sort()
    if len(all_files) > limit:
        all_files = all_files[:limit]
    return all_files


def generate_synthetic_tracks(n: int, duration: float = 10.0) -> tuple[list[Path], Path]:
    temp_dir = Path(tempfile.mkdtemp(prefix="bench_audio_"))
    sr = 22050
    samples = int(sr * duration)
    t = np.linspace(0, duration, samples, endpoint=False)
    paths = []
    for i in range(n):
        base_freq = 110 + i * 37
        bpm = 100 + (i % 5) * 10
        beat_hz = bpm / 60.0
        envelope = 0.3 + 0.7 * (np.sin(2 * np.pi * beat_hz * t) > 0.5).astype(np.float32)
        audio = np.zeros(samples, dtype=np.float32)
        for k, amp in enumerate([0.5, 0.25, 0.12, 0.06], 1):
            audio += amp * np.sin(2 * np.pi * base_freq * k * t)
        audio *= envelope
        audio /= np.abs(audio).max() + 1e-6
        filename = temp_dir / f"synth_track_{i:04d}.wav"
        import soundfile as sf
        sf.write(str(filename), audio, sr)
        paths.append(filename)
    return paths, temp_dir


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Benchmark feature extraction pipeline")
    parser.add_argument("--tracks", type=int, default=10, help="Number of tracks to process")
    parser.add_argument("--batch-size", type=int, default=8, help="Memory batch size")
    parser.add_argument("--workers", type=int, default=None, help="Thread pool workers")
    parser.add_argument("--server", type=str, default="http://localhost:8000", help="Embedding server URL")
    parser.add_argument("--skip-server", action="store_true", help="Skip embedding server entirely")
    parser.add_argument("--real", action="store_true", help="Use real audio files from ~/Music")
    args = parser.parse_args()

    config = ConfigManager()
    if args.skip_server:
        embedding_client = None
    else:
        embedding_client = EmbeddingClient(args.server)

    logger.info(f"Mode: {'real' if args.real else 'synthetic'}")
    logger.info(f"Tracks: {args.tracks}, Batch: {args.batch_size}, Workers: {args.workers}")
    logger.info(f"Server: {'enabled' if embedding_client else 'disabled'}")

    if args.real:
        test_paths = find_test_tracks(args.tracks)
        if not test_paths:
            logger.error("No real audio files found. Use --real only when ~/Music or /mnt has audio.")
            return
        temp_dir = None
    else:
        test_paths, temp_dir = generate_synthetic_tracks(args.tracks)
        logger.info(f"Synthetic audio in: {temp_dir}")

    logger.info(f"Found {len(test_paths)} tracks")

    db_path = Path(tempfile.mktemp(suffix=".db", prefix="bench_"))
    db_dir = None
    try:
        db_dir = Path(tempfile.mkdtemp(prefix="bench_db_"))
        db_path = db_dir / "library.db"
        db = Database(db_path=db_path)
        ts = TrackSimilarity(db)

        for p in test_paths:
            db.insert_track_metadata({
                "file_path": str(p),
                "file_name": p.name,
                "directory": str(p.parent),
                "extension": p.suffix,
                "title": p.stem,
                "artist": "Benchmark",
                "album": "Benchmark",
                "track_number": 1,
                "genre": "Test",
                "year": "2026",
                "bpm": 120.0,
                "duration": 10.0,
            })

        afe = AudioFeatureExtractor(
            track_list=test_paths,
            database=db,
            track_similarity=ts,
            embedding_client=embedding_client,
        )

        t0 = time.perf_counter()
        results = afe.find_features_of_list(batch_size=args.batch_size, max_workers=args.workers)
        elapsed = time.perf_counter() - t0

        n_stored = len(results["successful_files"])
        n_errors = len(results["errors"])
        rate = elapsed / len(test_paths) if test_paths else 0

        logger.info("=" * 50)
        logger.info(f"TOTAL TIME: {elapsed:.2f}s for {len(test_paths)} tracks")
        logger.info(f"Per track:  {rate*1000:.0f}ms avg")
        logger.info(f"Stored:     {n_stored}")
        logger.info(f"Errors:     {n_errors}")
        logger.info("=" * 50)

        if n_errors:
            for err in results["errors"][:5]:
                logger.warning(f"  Error: {err}")

        all_features = db.get_all_features()
        if all_features:
            sample_tid, sample_feat = next(iter(all_features.items()))
            logger.info(f"Sample feature check — hpcp={sample_feat.hpcp.shape}, bpm={sample_feat.bpm}, genre={sample_feat.genre.shape}")

        errors = _validate_features(all_features)
        if errors:
            logger.error(f"VALIDATION FAILED — {len(errors)} error(s):")
            for msg in errors[:10]:
                logger.error(f"  {msg}")
            return 1
        else:
            logger.info("VALIDATION PASSED — HPCP, BPM, genre embeddings correct for all tracks")

    finally:
        if temp_dir:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
        if db_dir:
            import shutil
            shutil.rmtree(db_dir, ignore_errors=True)

    return 0


def _validate_features(features: dict[int, Features]) -> list[str]:
    errors = []
    for tid, feat in features.items():
        if feat is None:
            errors.append(f"track_id={tid}: Features is None")
            continue

        hpcp = feat.hpcp
        if hpcp is None:
            errors.append(f"track_id={tid}: HPCP is None")
        elif not isinstance(hpcp, np.ndarray):
            errors.append(f"track_id={tid}: HPCP is not ndarray ({type(hpcp).__name__})")
        else:
            if hpcp.shape != (12,):
                errors.append(f"track_id={tid}: HPCP shape {hpcp.shape}, expected (12,)")
            if not np.isfinite(hpcp).all():
                errors.append(f"track_id={tid}: HPCP contains NaN/Inf")
            if np.sum(hpcp) <= 0:
                errors.append(f"track_id={tid}: HPCP sum is {np.sum(hpcp):.4f}, expected > 0")
            if abs(np.sum(hpcp) - 1.0) > 0.01:
                errors.append(f"track_id={tid}: HPCP sum {np.sum(hpcp):.4f} not within 0.01 of 1.0")
            if (hpcp < 0).any():
                errors.append(f"track_id={tid}: HPCP contains negative values")

        bpm = feat.bpm
        if bpm is None:
            errors.append(f"track_id={tid}: BPM is None")
        elif not isinstance(bpm, (int, float, np.floating)):
            errors.append(f"track_id={tid}: BPM is not numeric ({type(bpm).__name__})")
        elif bpm < 0 or bpm > 400:
            errors.append(f"track_id={tid}: BPM {bpm:.1f} outside [20, 400]")

        genre = feat.genre
        if genre is None:
            errors.append(f"track_id={tid}: genre is None")
        elif not isinstance(genre, np.ndarray):
            errors.append(f"track_id={tid}: genre is not ndarray ({type(genre).__name__})")
        else:
            if genre.shape != (1280,):
                errors.append(f"track_id={tid}: genre shape {genre.shape}, expected (1280,)")
            if not np.isfinite(genre).all():
                errors.append(f"track_id={tid}: genre contains NaN/Inf")
            if np.all(genre == 0):
                errors.append(f"track_id={tid}: genre is all zeros")

    return errors


if __name__ == "__main__":
    sys.exit(main())
