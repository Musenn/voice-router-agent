"""Capture audio from the local microphone using sounddevice.

This is the M0 fallback: lets you exercise the pipeline without any ESP32
hardware. The browser dashboard now uses MediaRecorder for the same job, so
this module mostly exists for manual scripts and quick debugging.
"""
from __future__ import annotations

import wave
from pathlib import Path

import numpy as np
import sounddevice as sd
from loguru import logger


def record_until_silence(
    duration_seconds: float = 5.0,
    sample_rate: int = 16000,
) -> bytes:
    """Block for `duration_seconds`, return raw 16-bit PCM bytes."""
    logger.info("Recording {}s @ {}Hz", duration_seconds, sample_rate)
    frames = int(duration_seconds * sample_rate)
    audio = sd.rec(frames, samplerate=sample_rate, channels=1, dtype="int16")
    sd.wait()
    return audio.tobytes()


def write_wav(path: str | Path, pcm: bytes, sample_rate: int = 16000) -> Path:
    path = Path(path)
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(sample_rate)
        f.writeframes(pcm)
    return path


def read_wav(path: str | Path) -> tuple[bytes, int]:
    with wave.open(str(path), "rb") as f:
        sample_rate = f.getframerate()
        frames = f.readframes(f.getnframes())
    return frames, sample_rate
