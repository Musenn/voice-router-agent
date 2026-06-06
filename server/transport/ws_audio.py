"""通过 WebSocket 流式接收音频帧。

客户端（浏览器或 ESP32）说话时按住按钮，服务端不断累积原始 PCM，直到松开按钮，
再跑完整条管线 ASR → LLM → TTS，并把合成的语音流式回传。

通信协议（除二进制 PCM 帧外，其余消息均为 JSON）：
  客户端 → 服务端：
    {"event": "start", "sample_rate": 16000, "format": "pcm_s16le"}
    <二进制帧>  原始 PCM，小端 16 位单声道
    {"event": "stop"}
  服务端 → 客户端：
    {"event": "transcript", "text": "..."}   识别文本
    {"event": "reply",      "text": "...", "actions": [...]}  回复 + 执行的动作
    {"event": "tts_audio",  "mime": "audio/mpeg", "size": 12345}  后随一帧 MP3
    <二进制 mp3 数据>
    {"event": "done"}        本轮结束
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
    """一次 WebSocket 音频会话的状态：采样率、累积的 PCM 缓冲、是否已开始录音。"""

    def __init__(self, ws: WebSocket) -> None:
        self.ws = ws
        self.sample_rate = 16000
        self.buffer = bytearray()  # 累积本轮的原始 PCM
        self.started = False

    async def send_json(self, payload: dict[str, Any]) -> None:
        # ensure_ascii=False 保证中文不被转义成 \uXXXX
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

            # 二进制帧：原始 PCM，直接追加到缓冲
            if (data := message.get("bytes")) is not None:
                session.buffer.extend(data)
                continue

            # 文本帧：控制事件
            if (text := message.get("text")) is not None:
                payload = json.loads(text)
                event = payload.get("event")
                if event == "start":
                    # 开始录音：清空上一轮残留，记录采样率
                    session.started = True
                    session.buffer.clear()
                    session.sample_rate = int(payload.get("sample_rate", 16000))
                elif event == "stop":
                    # 结束录音：没有音频则直接回 done，否则跑完整条管线
                    if not session.buffer:
                        await session.send_json({"event": "done"})
                        continue
                    await _process_turn(session, asr, tts, orchestrator)
                    session.buffer.clear()
                    session.started = False
                elif event == "ping":
                    # 心跳保活
                    await session.send_json({"event": "pong"})

    except WebSocketDisconnect:
        logger.info("Audio session closed by client")
    except Exception as e:
        # 兜底：会话异常时尽量回一条 error，再让连接自然结束
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
    # 一轮完整处理：ASR 转写 → 编排器处理 → TTS 合成 → 回传
    audio = bytes(session.buffer)
    sample_rate = session.sample_rate

    # 1) 语音识别，并把识别文本回传给前端展示
    transcript = await asr.transcribe(audio, sample_rate=sample_rate)
    await session.send_json({"event": "transcript", "text": transcript})

    # 2) 交给编排器：问 LLM、执行工具、得到回复与动作
    result = await orchestrator.handle_text(transcript)
    await session.send_json({
        "event": "reply",
        "text": result.reply_text,
        "actions": result.actions,
    })

    # 3) 合成语音并回传（先发元信息 JSON，再发二进制 MP3）
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
