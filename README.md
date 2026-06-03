# voice-router-agent

A small voice-controlled hub for the home network and a handful of mock smart
appliances. Speak a command, the audio is transcribed by a cloud ASR service,
an LLM decides which tool to call, the tool fires, and a TTS voice talks
back.

It also keeps an eye on the home router: when the network drops it can ask
you (out loud) whether to restart the router and, on confirmation, SSH in and
reboot it.

## Status

This is a personal learning project. Treat the code as a working prototype,
not as something hardened for someone else's house.

- [x] Project skeleton, adapter interfaces, mock providers
- [x] FastAPI server, web dashboard, WebSocket audio channel
- [x] LLM tool-call orchestrator
- [x] Self-heal daemon (ping watcher + voice confirmation flow)
- [x] ESP32-S3 firmware sketch (push-to-talk over WebSocket)
- [ ] Tests — coming after the first end-to-end run on real hardware
- [ ] Wake-word integration (uses key press for now)

## Layout

```
server/        Python service that runs on the home PC
  adapters/    ASR / LLM / TTS / router / device providers (mock + real)
  intent/      LLM tool-call orchestration
  selfheal/    Network monitor and recovery flow
  transport/   WebSocket audio endpoint
  audio/       Local microphone capture (M0 fallback)
  web/         FastAPI routes + static dashboard
firmware/      ESP32-S3 sketch (PlatformIO) for the wireless mic node
scripts/       Helper launchers and a manual audio test
docs/          Architecture notes
```

## Quick start (M0: laptop microphone)

```powershell
# Activate your Python env first
pip install -e .
copy .env.example .env
# Fill in your provider credentials in .env
python -m server.main
```

Open <http://localhost:28080>. Press F2 in the dashboard to start recording,
release to stop. Or run `python scripts/mic_test.py` to push an audio file
through the pipeline.

## Configuration

All credentials live in `.env`. Never commit it. See `.env.example` for the
exact set of variables and where to obtain each value.

## Docs

- [Architecture](docs/architecture.md) — how the pieces fit together.
- [Hardware shopping list](docs/hardware-shopping-list.md) — BOM, sources,
  pitfalls for the ESP32 mic node and the optional OpenWrt router.
- [Testing plan](docs/testing-plan.md) — manual runbook for M0 / M1 / M2,
  including the fault-injection cases.

## License

Personal use, no warranty.
