"""用 sounddevice 从本机麦克风采集音频。

这是 M0 阶段的兜底方案：没有任何 ESP32 硬件也能跑通管线。
如今浏览器看板已用 MediaRecorder 完成同样的事，因此本模块主要留给
手动脚本和快速调试使用。
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
    """定长录音：阻塞 duration_seconds 秒，返回原始 16 位 PCM 字节。

    注：函数名虽叫 until_silence，但当前实现是固定时长录音，并未做静音检测。
    """
    logger.info("Recording {}s @ {}Hz", duration_seconds, sample_rate)
    frames = int(duration_seconds * sample_rate)
    # 单声道、int16 录音；sd.wait() 阻塞到录满
    audio = sd.rec(frames, samplerate=sample_rate, channels=1, dtype="int16")
    sd.wait()
    return audio.tobytes()


def write_wav(path: str | Path, pcm: bytes, sample_rate: int = 16000) -> Path:
    """把原始 PCM 写成单声道 16 位 WAV 文件。"""
    path = Path(path)
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)      # 单声道
        f.setsampwidth(2)      # 16 位 = 2 字节
        f.setframerate(sample_rate)
        f.writeframes(pcm)
    return path


def read_wav(path: str | Path) -> tuple[bytes, int]:
    """读取 WAV，返回 (PCM 字节, 采样率)。"""
    with wave.open(str(path), "rb") as f:
        sample_rate = f.getframerate()
        frames = f.readframes(f.getnframes())
    return frames, sample_rate
