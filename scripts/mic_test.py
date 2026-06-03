"""Record N seconds from the local mic, push the PCM through the running
server's HTTP text endpoint via the ASR adapter, and print the result.

Usage:
    python scripts/mic_test.py [duration_seconds]
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from server.adapters import build_asr, build_devices, build_llm, build_router  # noqa: E402
from server.audio.local_mic import record_until_silence  # noqa: E402
from server.intent.orchestrator import IntentOrchestrator  # noqa: E402
from server.logging_setup import configure_logging  # noqa: E402


async def main(duration: float) -> None:
    configure_logging()
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
    seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 4.0
    asyncio.run(main(seconds))
