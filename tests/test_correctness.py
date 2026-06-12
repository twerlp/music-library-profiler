#!/usr/bin/env python3
import sys
import unittest
import logging
from pathlib import Path

import numpy as np

logging.basicConfig(level=logging.WARNING)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src" / "music_library_profiler"))

from core.audio_feature_extractor import (
    find_hpcp, find_bpm, load_audio_file,
)
from core.onnx_inference import (
    compute_genre_embeddings, compute_mel, load_onnx_session,
)
from core.features import Features

SR = 22050
CHROMATIC_SCALE = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


class BPMTests(unittest.TestCase):
    def test_metronome_120(self):
        duration = 6.0
        bpm_expected = 120
        beat_interval = 60.0 / bpm_expected
        samples = int(SR * duration)
        audio = np.zeros(samples, dtype=np.float32)
        pos = 0
        while pos < samples:
            end = min(pos + int(0.02 * SR), samples)
            audio[pos:end] = 0.8
            pos += int(beat_interval * SR)
        detected, _ = find_bpm(audio, SR)
        bpm_val = detected.item() if hasattr(detected, "item") else float(detected)
        self.assertAlmostEqual(bpm_val, bpm_expected, delta=15,
                               msg=f"Detected BPM {bpm_val:.1f} far from expected {bpm_expected}")

    def test_metronome_140(self):
        duration = 6.0
        bpm_expected = 140
        beat_interval = 60.0 / bpm_expected
        samples = int(SR * duration)
        audio = np.zeros(samples, dtype=np.float32)
        pos = 0
        while pos < samples:
            end = min(pos + int(0.02 * SR), samples)
            audio[pos:end] = 0.8
            pos += int(beat_interval * SR)
        detected, _ = find_bpm(audio, SR)
        bpm_val = detected.item() if hasattr(detected, "item") else float(detected)
        self.assertAlmostEqual(bpm_val, bpm_expected, delta=15,
                               msg=f"Detected BPM {bpm_val:.1f} far from expected {bpm_expected}")

    def test_bpm_positive_rich_signal(self):
        duration = 6.0
        bpm = 120
        beat_interval = 60.0 / bpm
        samples = int(SR * duration)
        t = np.linspace(0, duration, samples, endpoint=False)
        audio = (
            np.sin(2 * np.pi * 440 * t)
            * (0.5 + 0.5 * np.sin(2 * np.pi * (bpm / 60) * t) > 0.7)
        ).astype(np.float32)
        detected, _ = find_bpm(audio, SR)
        bpm_val = detected.item() if hasattr(detected, "item") else float(detected)
        self.assertGreater(bpm_val, 10, f"BPM should be reasonable for amplitude-modulated audio, got {bpm_val:.1f}")


class HPCPTests(unittest.TestCase):
    def test_sine_a4_peaks_at_a(self):
        duration = 3.0
        t = np.linspace(0, duration, int(SR * duration), endpoint=False)
        audio = (np.sin(2 * np.pi * 440 * t) * 0.8).astype(np.float32)
        hpcp = find_hpcp(audio, SR)
        peak_idx = int(np.argmax(hpcp))
        peak_note = CHROMATIC_SCALE[peak_idx]
        self.assertEqual(peak_note, "A",
                         msg=f"A4 sine HPCP peak at {peak_note}, expected A. HPCP={hpcp}")

    def test_sine_c5_peaks_at_c(self):
        duration = 3.0
        t = np.linspace(0, duration, int(SR * duration), endpoint=False)
        audio = (np.sin(2 * np.pi * 523.25 * t) * 0.8).astype(np.float32)
        hpcp = find_hpcp(audio, SR)
        peak_idx = int(np.argmax(hpcp))
        peak_note = CHROMATIC_SCALE[peak_idx]
        self.assertEqual(peak_note, "C",
                         msg=f"C5 sine HPCP peak at {peak_note}, expected C. HPCP={hpcp}")

    def test_octave_invariance(self):
        duration = 3.0
        t = np.linspace(0, duration, int(SR * duration), endpoint=False)
        audio_a3 = (np.sin(2 * np.pi * 220 * t) * 0.8).astype(np.float32)
        audio_a4 = (np.sin(2 * np.pi * 440 * t) * 0.8).astype(np.float32)
        hpcp_a3 = find_hpcp(audio_a3, SR)
        hpcp_a4 = find_hpcp(audio_a4, SR)
        self.assertEqual(np.argmax(hpcp_a3), np.argmax(hpcp_a4),
                         msg="A3 and A4 should have same HPCP peak (octave invariance)")

    def test_hpcp_shape_and_norm(self):
        duration = 1.0
        t = np.linspace(0, duration, int(SR * duration), endpoint=False)
        audio = (np.sin(2 * np.pi * 330 * t) * 0.5).astype(np.float32)
        hpcp = find_hpcp(audio, SR)
        self.assertEqual(hpcp.shape, (12,), msg="HPCP must be 12-dimensional")
        self.assertAlmostEqual(np.sum(hpcp), 1.0, delta=0.01,
                               msg="HPCP should sum to ~1.0")

    def test_silence_uniform(self):
        duration = 1.0
        audio = np.ones(int(SR * duration), dtype=np.float32) * 1e-6
        audio += np.random.randn(len(audio)).astype(np.float32) * 1e-8
        hpcp = find_hpcp(audio, SR)
        self.assertFalse(np.any(np.isnan(hpcp)), "Silence HPCP should not contain NaN")
        self.assertLess(np.max(hpcp) - np.min(hpcp), 0.15,
                        msg="Near-silence should produce near-uniform HPCP")


class EmbeddingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        model_path = (
            Path(__file__).resolve().parent.parent
            / "src" / "models" / "discogs-effnet-bsdynamic-1.onnx"
        )
        cls._session = load_onnx_session(str(model_path))

    def _make_audio(self, freq, duration=3.0):
        t = np.linspace(0, duration, int(SR * duration), endpoint=False)
        audio = (np.sin(2 * np.pi * freq * t) * 0.5).astype(np.float32)
        return audio

    def test_determinism(self):
        audio = self._make_audio(440)
        emb1 = compute_genre_embeddings([audio], self._session)[0]
        emb2 = compute_genre_embeddings([audio], self._session)[0]
        np.testing.assert_array_equal(emb1, emb2, "Same audio must yield identical embeddings")

    def test_embedding_shape(self):
        audio = self._make_audio(440)
        emb = compute_genre_embeddings([audio], self._session)[0]
        self.assertEqual(emb.shape, (1280,), "Embedding must be 1280-dimensional")

    def test_different_frequencies_different_embedding(self):
        audio_a = self._make_audio(440)
        audio_b = self._make_audio(330)
        emb_a = compute_genre_embeddings([audio_a], self._session)[0]
        emb_b = compute_genre_embeddings([audio_b], self._session)[0]
        sim = np.dot(emb_a, emb_b) / (np.linalg.norm(emb_a) * np.linalg.norm(emb_b) + 1e-10)
        self.assertLess(sim, 0.99, f"Different frequencies should produce different embeddings (sim={sim:.4f})")

    def test_same_frequency_similar(self):
        audio_1 = self._make_audio(440, duration=3.0)
        audio_2 = self._make_audio(440, duration=3.0)
        emb_1 = compute_genre_embeddings([audio_1], self._session)[0]
        emb_2 = compute_genre_embeddings([audio_2], self._session)[0]
        np.testing.assert_array_almost_equal(emb_1, emb_2, decimal=4,
                                             err_msg="Same signal should give near-identical embeddings")

    def test_batched_equal_to_single(self):
        audio = self._make_audio(440)
        single = compute_genre_embeddings([audio], self._session)[0]
        batched = compute_genre_embeddings([audio, audio], self._session)
        np.testing.assert_array_almost_equal(
            single, batched[0], decimal=4,
            err_msg="Batch inference must match single inference"
        )
        np.testing.assert_array_almost_equal(
            batched[0], batched[1], decimal=4,
            err_msg="Same input in batch must yield same output"
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
