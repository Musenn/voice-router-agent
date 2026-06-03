# Testing plan

How to verify each milestone end-to-end. Every check has a concrete
observable — none of the "looks fine" judgments. Automated tests will
arrive later; for now this is a manual smoke-test runbook.

Each milestone has three blocks:
- **Pre-conditions** — what must be set up first.
- **Cases** — what to do and what to look for.
- **Fault injection** — deliberately break something and watch the
  recovery path.

## Conventions

- Replace `<HUB>` with the host:port of the hub service (default
  `http://127.0.0.1:28080`).
- Curl examples use git-bash on Windows. PowerShell users: swap `curl`
  for `curl.exe` to avoid the alias to `Invoke-WebRequest`.
- The dashboard at `<HUB>/` reflects state changes from any entry point
  (voice, text, REST). Keep it open in a browser tab while you test.

---

## M0 — software pipeline on the laptop (no hardware)

**Goal**: prove the ASR → LLM → tool-call → state-change → TTS loop runs
end-to-end without an ESP32 or router.

### Pre-conditions

```
- [ ] python -m venv .venv && .venv\Scripts\activate
- [ ] pip install -e .
- [ ] copy .env.example .env
- [ ] In .env: ASR_PROVIDER=mock, LLM_PROVIDER=mock, ROUTER_PROVIDER=mock
- [ ] python -m server.main starts without errors
- [ ] http://127.0.0.1:28080 loads the dashboard
```

### Cases — mock providers (zero cloud, runs offline)

| # | Action | Observable |
|---|---|---|
| M0.1 | `curl <HUB>/health` | Returns `{"status":"ok"}` (200) |
| M0.2 | `curl <HUB>/api/devices` | Returns 4 devices: light_livingroom, light_bedroom, ac_livingroom, curtain_livingroom |
| M0.3 | `curl -X POST <HUB>/api/text -H "Content-Type: application/json" -d '{"text":"打开客厅的灯"}'` | Response contains `"transcript":"打开客厅的灯"`, `"actions":[{"tool":"set_device_state","ok":true,...}]`; dashboard shows `客厅主灯` flipped to `on` |
| M0.4 | Same as M0.3 with text `关闭灯` | Light flips back to `off` |
| M0.5 | Same with text `重启路由器` | Action returns `已模拟重启路由器（mock 模式，未真实执行）` and server log warns `[mock] would SSH router and run reboot` |
| M0.6 | Dashboard "按住说话", say anything, release | UI shows mock transcript `打开客厅的灯`, dashboard updates, TTS audio plays in browser |

### Cases — real providers (cloud accounts wired in)

Switch `.env` to `ASR_PROVIDER=aliyun`, `LLM_PROVIDER=xfyun`, fill in
credentials, restart the service. Re-run M0.3 — same observable, but now
the LLM is actually picking the tool.

| # | Action | Observable |
|---|---|---|
| M0.7 | `curl -X POST .../api/text -d '{"text":"晚上有点冷，把空调调到 25 度制热"}'` | LLM picks `set_device_state` on `ac_livingroom` with `temperature=25`, `mode="heat"`; dashboard reflects both fields |
| M0.8 | Dashboard "按住说话", speak "打开卧室灯" | Aliyun returns `打开卧室灯`, LLM routes to `light_bedroom` not `light_livingroom` |
| M0.9 | `curl <HUB>/api/network` while connected | `online: true`, `last_target_ok` is one of the configured ping targets |

### Fault injection

| # | Inject | Expected behaviour |
|---|---|---|
| M0.F1 | Set `XFYUN_API_KEY` to an obviously wrong value | First text request returns HTTP 500 with a meaningful error; service stays up |
| M0.F2 | Disable your laptop WiFi for `SELFHEAL_INTERVAL × FAILURE_THRESHOLD` seconds | `/api/network` flips to `online:false`; server log emits `Network outage detected (failures=3). Self-heal would prompt user.` |
| M0.F3 | Re-enable WiFi | Next ping succeeds; server log emits `Network recovered via ...`; `online:true` returns |
| M0.F4 | Curl `/api/devices/does_not_exist/state -d '{"state":"on"}'` | 404 with `unknown device`, no state corruption |

### Exit criteria for M0

All M0.1–M0.6 pass with mocks; at least M0.7–M0.9 pass with real cloud
providers; F1–F4 behave as described. M0 done.

---

## M1 — ESP32 wireless mic node

**Goal**: replace the laptop mic with an ESP32, leave everything else as
M0. The same dashboard, same LLM, same fake devices.

### Pre-conditions

```
- [ ] M0 fully green
- [ ] Hardware from docs/hardware-shopping-list.md assembled
- [ ] firmware/include/config.h filled in with WiFi creds + HUB_HOST = LAN IP of the PC running the hub
- [ ] `pio run -t upload` finishes with no errors
- [ ] Hub service running with .env from M0 (real providers)
```

### Wiring check (do this BEFORE running anything)

```
- [ ] INMP441 VDD → ESP32 3.3 V (NOT 5 V — 5 V will fry the mic)
- [ ] INMP441 GND → ESP32 GND
- [ ] INMP441 L/R → GND (forces left channel)
- [ ] INMP441 WS → GPIO 5 (LRCLK)
- [ ] INMP441 SCK → GPIO 4 (BCLK)
- [ ] INMP441 SD → GPIO 6 (DIN)
- [ ] BOOT button on the dev board is reachable (or external button on GPIO 0)
```

### Cases

| # | Action | Observable |
|---|---|---|
| M1.1 | Plug ESP32 USB, open `pio device monitor` | Serial prints `voice-router-agent firmware boot`, then `WiFi ok, ip=192.168.x.x` |
| M1.2 | Wait ~3 s | Serial prints `ws connected`; status LED turns green |
| M1.3 | Hub server log | Shows `Audio session opened from ('192.168.x.x', <port>)` |
| M1.4 | Press and hold BOOT, say "打开客厅的灯", release | Serial: `recording…` → `…sent`. Hub log shows incoming PCM bytes (count > 0). Dashboard updates transcript and toggles light. |
| M1.5 | Press BOOT briefly with no speech | Serial logs both events; hub gets a short audio buffer; ASR returns empty or near-empty, reply is `我没听清，请再说一遍。` |
| M1.6 | Move ESP32 to a different room (still in WiFi range) | Voice still works; latency from button-release to dashboard update under 3 s |

### Fault injection

| # | Inject | Expected behaviour |
|---|---|---|
| M1.F1 | Pull power from the hub PC mid-recording | ESP32 prints `ws disconnected`, status LED turns red, retries every 2 s until hub returns |
| M1.F2 | Wrong HUB_HOST in config.h | Serial prints repeated `ws disconnected` errors; no crash; flashing the correct value recovers |
| M1.F3 | Swap INMP441 L/R pin to VDD | Audio frames arrive but are silent; ASR returns empty consistently — diagnostic signal that the wiring is reversed |
| M1.F4 | Press BOOT 10 times in 5 s | Each press starts a new session; no stuck `recording` state; hub log shows each session opened and closed cleanly |

### Exit criteria for M1

All M1.1–M1.6 pass; round-trip latency stays under 3 s; F1–F4 behave as
expected. Now you have a working wireless mic.

---

## M2 — router self-heal closed loop

**Goal**: when the network goes down, the system asks (out loud) whether
to reboot the router; on a voice "好的" / "重启" it SSHes in and reboots.

### Pre-conditions

```
- [ ] M1 fully green
- [ ] Router runs OpenWrt (or compatible) with SSH enabled
- [ ] .env: ROUTER_PROVIDER=openwrt, ROUTER_HOST=<router LAN IP>, ROUTER_USER=root, ROUTER_KEY_PATH=<path to id_ed25519>
- [ ] `ssh -i <key> root@<router> echo ok` returns `ok` from your laptop
- [ ] The hub PC is on a wired connection OR you've thought about how it survives WiFi going down (otherwise the hub disappears with the network)
```

### Cases

| # | Action | Observable |
|---|---|---|
| M2.1 | `curl -X POST <HUB>/api/text -d '{"text":"重启路由器"}'` | Hub logs `Rebooting router via SSH`. Router actually reboots (lights cycle). Reply: `路由器已收到重启指令：...` |
| M2.2 | While router is rebooting, `curl <HUB>/api/network` | `online: false`, `consecutive_failures` rises |
| M2.3 | After router boots back | Network monitor flips back to `online: true`, server log emits `Network recovered via ...` |
| M2.4 | `curl -X POST <HUB>/api/text -d '{"text":"重启 WiFi"}'` | `wifi reload` runs on the router; WiFi clients re-associate; no full reboot |

### Fault injection (this is the whole point of M2)

| # | Inject | Expected behaviour |
|---|---|---|
| M2.F1 | Unplug router WAN cable | After `SELFHEAL_FAILURE_THRESHOLD` failed pings (default 3 × 30 s = 90 s) the monitor calls `on_outage`. With confirmation enabled, the system speaks (TTS) "网络不通，要不要重启路由器？" — *the spoken-confirmation flow lives in the orchestrator hook; if you haven't wired it yet, the log line is the observable.* |
| M2.F2 | Plug WAN back in before saying yes | Monitor returns to `online`; the outage prompt is cancelled; no reboot fires |
| M2.F3 | Wrong SSH key path | First reboot attempt errors with `Router SSH needs either ROUTER_KEY_PATH or ROUTER_PASSWORD`; service stays up; mock fallback NOT used (would mask the bug) |
| M2.F4 | Router unreachable (powered off) | `router_ctrl.health_check()` returns False; reboot tool returns an error rather than hanging |

### Exit criteria for M2

M2.1–M2.4 pass; F1 produces the outage notification (even if voice-flow
is text-only for now); F2/F3/F4 fail safely without leaving the system
in an undefined state.

---

## After M2

These are the "would be nice" items, not part of the testing plan above:

- Replace push-to-talk with ESP-SR wake-word so the ESP32 listens
  ambiently.
- Persist device state and audit log to SQLite.
- Add automated pytest cases covering the orchestrator, the network
  monitor's state machine, and the adapter factory.
- Add an integration test that boots the FastAPI app with mock providers
  and replays a fixture WAV through the WebSocket.

Until then this document is the contract for what "working" means.
