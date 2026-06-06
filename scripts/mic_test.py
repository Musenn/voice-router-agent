"""从本机麦克风录 N 秒，经 ASR 适配器转写后送入编排器，并打印结果。

用于在不依赖浏览器/ESP32 的情况下，命令行快速验证 ASR → LLM → 工具调用一条龙。

用法：
    python scripts/mic_test.py [录音秒数]
"""
import asyncio
import sys
from pathlib import Path

# 把项目根目录加入 import 路径，使脚本可直接 import server 包
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from server.adapters import build_asr, build_devices, build_llm, build_router  # noqa: E402
from server.audio.local_mic import record_until_silence  # noqa: E402
from server.intent.orchestrator import IntentOrchestrator  # noqa: E402
from server.logging_setup import configure_logging  # noqa: E402


async def main(duration: float) -> None:
    configure_logging()
    # 1) 录音 → 2) 按 .env 装配适配器 → 3) 转写 → 4) 编排处理 → 5) 打印
    pcm = record_until_silence(duration_seconds=duration)
    asr = build_asr()
    llm = build_llm()
    devices = build_devices()
    router = build_router()
    orchestrator = IntentOrchestrator(llm=llm, devices=devices, router=router)

    text = await asr.transcribe(pcm)
    print(f"[transcript] {text}")
    result = await orchestrator.handle_text(text)
    print(f"[reply]      {result.reply_text}")
    for action in result.actions:
        print(f"[action]     {action}")


if __name__ == "__main__":
    # 命令行第一个参数为录音秒数，缺省 4 秒
    seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 4.0
    asyncio.run(main(seconds))
