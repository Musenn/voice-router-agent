# Architecture

> English · [中文](architecture.zh-CN.md)

A short note on how the pieces fit together. Read this first if you want to
extend or fork the project.

## Layers

```
[Edge mic]          [Hub service (this repo)]                     [Targets]

browser MediaRec  ─┐
ESP32 + INMP441   ─┼── /ws/audio ──> AudioSession
laptop sounddev   ─┘                      │
                                          ▼
                                       ASR adapter ── transcript ──┐
                                                                   ▼
                                                          IntentOrchestrator
                                                                   │
                                                       ┌───────────┼───────────┐
                                                       ▼           ▼           ▼
                                                 LLM adapter   DeviceCtrl   RouterCtrl
                                                       │           │           │
                                                       ▼           ▼           ▼
                                                 tool call ─► state change ─► SSH cmd
                                                                   │
                                                                   ▼
                                                              TTS adapter
                                                                   │
                                                                   ▼
                                                              MP3 → client
```

A separate `NetworkMonitor` task pings public hosts every N seconds. After
the configured failure threshold it calls a recovery hook; in M2 that hook
will speak through the TTS path and wait for a "yes" before SSH-rebooting
the router.

## Why adapters everywhere

Every external dependency sits behind a base class with a tiny interface
(usually one or two methods). The factory in `server/adapters/__init__.py`
picks an implementation from environment variables at startup. The rest of
the code never imports a concrete provider.

This makes three things cheap:

- Swap a vendor (e.g. Aliyun → local Whisper) by adding a new adapter and
  flipping `ASR_PROVIDER=...`.
- Test without network: the `mock_*` adapters return canned data.
- Stub out hardware: `MockRouter` logs the SSH command it would have run.

## Milestone map

The same code supports three deployment shapes:

| Milestone | Edge mic            | Provider config        | Real router?  |
|-----------|---------------------|------------------------|---------------|
| M0        | Browser / laptop    | mock or real (your call) | mock          |
| M1        | ESP32-S3 + INMP441  | real cloud             | mock          |
| M2        | ESP32-S3 + INMP441  | real cloud             | OpenWrt SSH   |

No code structure change between milestones — only `.env` settings and the
hardware you point at it.

## Things deliberately left out

- Multi-turn conversation memory. Every request is standalone. The model
  cost stays low and debugging is easier.
- A database. Device state lives in memory; restart resets it. Add a
  SQLite layer once you actually need persistence.
- Authentication. The service binds to `127.0.0.1` by default. Don't
  expose it on the LAN until you've added an auth check.
- Wake-word detection on the server. The browser uses push-to-talk; the
  ESP32 firmware does push-to-talk too. Hook up ESP-SR or openWakeWord
  once the rest of the pipeline is solid.
