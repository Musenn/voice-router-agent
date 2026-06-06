# Hardware shopping list

> English · [中文](hardware-shopping-list.zh-CN.md)

For the M1 wireless mic node and the optional M2 router-rescue setup.
Prices are RMB and reflect typical 2026 Taobao listings; check before
buying — they drift.

## Required for M1 (~110–150 元)

| Item | Spec to match | Approx. price | Notes |
|---|---|---|---|
| ESP32-S3 dev board | DevKitC-1 N16R8 (16 MB flash, 8 MB PSRAM) | 55–80 | The N8 variant works too; PSRAM is the part that matters for audio buffering. Avoid the bare ESP32 (no S3) — its I2S microphone driver is fiddly. |
| INMP441 I2S MEMS mic | Through-hole breakout, 6 pins (VDD/GND/L/R/WS/SCK/SD) | 7–12 | Pick the version with header pins already soldered unless you enjoy soldering 0.65 mm pads. |
| Dupont jumper wires | Female-female, 20 cm | 5 | One pack covers a dozen builds. |
| USB-C cable | Data-capable (not charge-only) | already have one? | Charge-only cables cause "device not detected" — verify yours can carry data. |
| Small breadboard | 400-tie or half-size | 8–15 | Skip if you plan to solder direct. |

**Sub-total: ~75–120 元**

### Where to buy

- **Taobao / 淘宝**: search "ESP32-S3-DevKitC-1 N16R8" and "INMP441 模块". Stick to sellers with >2000 sales and ≥4.9 rating; clone boards from no-name shops sometimes ship with the wrong USB-to-UART chip.
- **嘉立创商城 (lcsc.com)**: official Espressif modules, slightly higher price, ships fast, no fake risk.
- **AliExpress**: only if you're outside China; in-China shipping is slower than Taobao.

### Pitfalls

1. **Two USB ports on the dev board.** Use the one labelled **UART**, not USB. The USB port works for native USB but PlatformIO's default upload flow expects the UART CP210x/CH340.
2. **PSRAM build flag.** This repo's `platformio.ini` already sets `-DBOARD_HAS_PSRAM` and the cache fix flag — don't strip them or the audio buffers will silently drop frames.
3. **Mic L/R pin.** Tie INMP441's L/R pin to GND (left channel). If you wire it to VDD you get right-channel only, and the firmware reads zeros from the left slot.
4. **Power.** USB delivers enough for board + mic. Don't run a speaker off the same USB if your laptop port is 500 mA — use a powered hub or add a wall adapter.

## Optional for local TTS playback (~15–30 元)

Skip unless you want the ESP32 to talk back without a browser open. The hub
already plays TTS through the dashboard.

| Item | Spec | Approx. price |
|---|---|---|
| MAX98357A I2S DAC + amplifier breakout | 3 W class-D, mono | 10–15 |
| 4 Ω 3 W speaker | 40 mm cone | 5–10 |
| Extra jumper wires | — | — |

Wire MAX98357A to a second I2S port (`I2S_NUM_1`) and stream the MP3 →
PCM decoded TTS frames into it. The firmware currently ignores the
`tts_audio` payload — add the playback path when you've got the hardware.

## Optional for M2 (router self-heal)

If you don't already have a router that runs OpenWrt, the cheapest path
is to repurpose one you've retired. Confirm before buying anything new:

- **Already on OpenWrt?** Done. Make sure SSH is enabled (`uci set dropbear.@dropbear[0].PasswordAuth='on'`) or copy your SSH key to `/etc/dropbear/authorized_keys`.
- **GL.iNet travel router** (GL-MT300N-V2, GL-AR300M16): ships with OpenWrt, ~150–250 元 new, ~80–120 元 used. Easiest path.
- **Xiaomi AX3000T / Redmi AX6000**: official OpenWrt builds exist but flashing requires unlocking; only do this if you enjoy that kind of thing.
- **TP-Link Archer C7 v5**: solid supported target, but second-hand only — TP-Link locked down newer firmware.

The repo's `OpenWRTRouter` adapter assumes vanilla OpenWrt SSH. If you
use ImmortalWrt or a vendor fork, the `reboot` and `wifi reload` commands
are usually the same — confirm with `ssh root@router /sbin/wifi --help`.

## What you do NOT need

- A separate WiFi module. The ESP32-S3 has 2.4 GHz built in.
- A dedicated audio codec chip. INMP441 outputs 24-bit I2S directly; the firmware downshifts to int16 in software — cheap, good enough at 16 kHz.
- A wake-word IC. ESP-SR runs on the same S3. Wire it up after the rest of the pipeline is solid.
- A Raspberry Pi. The hub runs on your existing PC. Add a Pi only if you want it always-on without leaving the PC running.

## Sanity check before ordering

```
- [ ] ESP32-S3-DevKitC-1 with PSRAM (N8R8 or N16R8)
- [ ] INMP441 breakout with header pins pre-soldered
- [ ] Female-female dupont wires, at least 6
- [ ] A USB-C data cable you've tested before
```

That's enough to reach end-to-end on M1. Defer the speaker and OpenWrt
router until M1 is actually working — keeping the BOM small while you
debug is the fastest path.
