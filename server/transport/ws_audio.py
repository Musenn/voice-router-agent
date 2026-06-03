"""Audio frames stream in over a WebSocket. The client (browser or ESP32)
holds a button while talking; we accumulate the raw PCM until it releases,
then run the full ASR → LLM → TTS pipeline and stream the TTS audio back.

Wire protocol (all messages JSON except for binary PCM frames):
  client → server:
    {"event": "start", "sample_rate": 16000, "format": "pcm_s16le"}
    <binary frame>  raw PCM, little-endian 16-bit mono
    {"event": "stop"}
  server → client:
    {"event": "transcript", "text": "..."}
    {"event": "reply",      "text": "...", "actions": [...]}
    {"event": "tts_audio",  "mime": "audio/mpeg", "size": 12345}
    <binary mp3 chunk>
    {"event": "done"}
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from loguru import logger

from server.adapters import ASRClient, TTSClient
from server.intent.orchestrator import IntentOrchestrator


class AudioSession:
    def __init__(self, ws: WebSocket) -> None:
        self.ws = ws
        self.sample_rate = 16000
        self.buffer = bytearray()
        self.started = False

    async def send_json(self, payload: dict[str, Any]) -> None:
        await self.ws.send_text(json.dumps(payload, ensure_ascii=False))


async def run_audio_session(
    ws: WebSocket,
    asr: ASRClient,
    tts: TTSClient,
    orchestrator: IntentOrchestrator,
) -> None:
    await ws.accept()
    session = AudioSession(ws)
    logger.info("Audio session opened from {}", ws.client)

    try:
        while True:
            message = await ws.receive()
            if message["type"] == "websocket.disconnect":
                break

            if (data := message.get("bytes")) is not None:
                session.buffer.extend(data)
                continue

            if (text := message.get("text")) is not None:
                payload = json.loads(text)
                event = payload.get("event")
                if event == "start":
                    session.started = True
                    session.buffer.clear()
                    session.sample_rate = int(payload.get("sample_rate", 16000))
                elif event == "stop":
                    if not session.buffer:
                        await session.send_json({"event": "done"})
                        continue
                    await _process_turn(session, asr, tts, orchestrator)
                    session.buffer.clear()
                    session.started = False
                elif event == "ping":
                    await session.send_json({"event": "pong"})

    except WebSocketDisconnect:
        logger.info("Audio session closed by client")
    except Exception as e:
        logger.exception("Audio session crashed: {}", e)
        try:
            await session.send_json({"event": "error", "message": str(e)})
        except Exception:
            pass


async def _process_turn(
    session: AudioSession,
    asr: ASRClient,
    tts: TTSClient,
    orchestrator: IntentOrchestrator,
) -> None:
    audio = bytes(session.buffer)
    sample_rate = session.sample_rate

    transcript = await asr.transcribe(audio, sample_rate=sample_rate)
    await session.send_json({"event": "transcript", "text": transcript})

    result = await orchestrator.handle_text(transcript)
    await session.send_json({
        "event": "reply",
        "text": result.reply_text,
        "actions": result.actions,
    })

    tts_task = asyncio.create_task(tts.synthesize(result.reply_text))
    audio_bytes = await tts_task
    if audio_bytes:
        await session.send_json({
            "event": "tts_audio",
            "mime": "audio/mpeg",
            "size": len(audio_bytes),
        })
        await session.ws.send_bytes(audio_bytes)
    await session.send_json({"event": "done"})
