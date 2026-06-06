# 测试计划

> 中文 · [English](testing-plan.md)

如何端到端验证每个里程碑。每一项检查都有**可观测的具体现象**——杜绝「看起来没问题」
这种判断。自动化测试以后再补；现阶段这是一份手动冒烟测试手册。

每个里程碑分三块：
- **前置条件** —— 先要准备好什么。
- **用例** —— 做什么、看什么。
- **故障注入** —— 故意搞坏某处，观察恢复路径。

## 约定

- 把 `<HUB>` 替换为中枢服务的 host:port（默认 `http://127.0.0.1:28080`）。
- curl 示例用的是 Windows 上的 git-bash。PowerShell 用户：把 `curl` 换成 `curl.exe`，
  以避开它对 `Invoke-WebRequest` 的别名。
- `<HUB>/` 看板会反映来自任意入口（语音、文本、REST）的状态变化。测试时在浏览器
  开着它。

---

## M0 —— 笔记本上的纯软件管线（无硬件）

**目标**：在没有 ESP32 和路由器的情况下，证明
ASR → LLM → 工具调用 → 状态变更 → TTS 这条回路能端到端跑通。

### 前置条件

```
- [ ] python -m venv .venv && .venv\Scripts\activate
- [ ] pip install -e .
- [ ] copy .env.example .env
- [ ] 在 .env 中：ASR_PROVIDER=mock, LLM_PROVIDER=mock, ROUTER_PROVIDER=mock
- [ ] python -m server.main 无报错启动
- [ ] http://127.0.0.1:28080 能打开看板
```

### 用例 —— 模拟服务商（零云端，可离线）

| # | 操作 | 可观测现象 |
|---|---|---|
| M0.1 | `curl <HUB>/health` | 返回 `{"status":"ok"}`（200） |
| M0.2 | `curl <HUB>/api/devices` | 返回 4 台设备：light_livingroom、light_bedroom、ac_livingroom、curtain_livingroom |
| M0.3 | `curl -X POST <HUB>/api/text -H "Content-Type: application/json" -d '{"text":"打开客厅的灯"}'` | 响应含 `"transcript":"打开客厅的灯"`、`"actions":[{"tool":"set_device_state","ok":true,...}]`；看板上「客厅主灯」翻为 `on` |
| M0.4 | 同 M0.3，文本改为 `关闭灯` | 灯翻回 `off` |
| M0.5 | 同上，文本 `重启路由器` | 动作返回 `已模拟重启路由器（mock 模式，未真实执行）`，服务端日志告警 `[mock] would SSH router and run reboot` |
| M0.6 | 看板「按住说话」，随便说一句，松开 | 界面显示模拟识别文本 `打开客厅的灯`，看板更新，浏览器播放 TTS 语音 |

### 用例 —— 真实服务商（接入云端账号）

把 `.env` 切到 `ASR_PROVIDER=aliyun`、`LLM_PROVIDER=xfyun`，填入凭据，重启服务。
重跑 M0.3——现象相同，但这次是 LLM 真正在挑工具。

| # | 操作 | 可观测现象 |
|---|---|---|
| M0.7 | `curl -X POST .../api/text -d '{"text":"晚上有点冷，把空调调到 25 度制热"}'` | LLM 对 `ac_livingroom` 调 `set_device_state`，`temperature=25`、`mode="heat"`；看板两个字段都更新 |
| M0.8 | 看板「按住说话」，说「打开卧室灯」 | 阿里云返回 `打开卧室灯`，LLM 路由到 `light_bedroom` 而非 `light_livingroom` |
| M0.9 | 联网时 `curl <HUB>/api/network` | `online: true`，`last_target_ok` 为配置的某个 ping 目标 |

### 故障注入

| # | 注入 | 预期行为 |
|---|---|---|
| M0.F1 | 把 `XFYUN_API_KEY` 设成明显错误的值 | 首个文本请求返回 HTTP 500 并带有意义的错误；服务不挂 |
| M0.F2 | 关闭笔记本 WiFi，持续 `SELFHEAL_INTERVAL × FAILURE_THRESHOLD` 秒 | `/api/network` 翻为 `online:false`；服务端日志输出 `Network outage detected (failures=3). Self-heal would prompt user.` |
| M0.F3 | 重新打开 WiFi | 下一次 ping 成功；服务端日志输出 `Network recovered via ...`；`online:true` 恢复 |
| M0.F4 | curl `/api/devices/does_not_exist/state -d '{"state":"on"}'` | 404 并提示 `unknown device`，无状态损坏 |

### M0 通过标准

所有 M0.1–M0.6 在 mock 下通过；至少 M0.7–M0.9 在真实云端下通过；F1–F4 表现符合描述。
M0 完成。

---

## M1 —— ESP32 无线麦克风节点

**目标**：用 ESP32 替换笔记本麦克风，其余一切保持 M0 原样——同一个看板、同一个 LLM、
同一批虚拟设备。

### 前置条件

```
- [ ] M0 全绿
- [ ] 按 docs/hardware-shopping-list.zh-CN.md 备齐并组装硬件
- [ ] firmware/include/config.h 填好 WiFi 凭据 + HUB_HOST = 运行中枢那台 PC 的局域网 IP
- [ ] `pio run -t upload` 无报错完成
- [ ] 中枢服务以 M0 的 .env（真实服务商）运行中
```

### 接线检查（运行任何东西之前先做）

```
- [ ] INMP441 VDD → ESP32 3.3V（不要接 5V——5V 会烧坏麦克风）
- [ ] INMP441 GND → ESP32 GND
- [ ] INMP441 L/R → GND（强制左声道）
- [ ] INMP441 WS → GPIO 5（LRCLK）
- [ ] INMP441 SCK → GPIO 4（BCLK）
- [ ] INMP441 SD → GPIO 6（DIN）
- [ ] 开发板上的 BOOT 按键可按到（或外接按钮到 GPIO 0）
```

### 用例

| # | 操作 | 可观测现象 |
|---|---|---|
| M1.1 | 插上 ESP32 USB，打开 `pio device monitor` | 串口打印 `voice-router-agent firmware boot`，随后 `WiFi ok, ip=192.168.x.x` |
| M1.2 | 等约 3 秒 | 串口打印 `ws connected`；状态灯变绿 |
| M1.3 | 看中枢服务日志 | 出现 `Audio session opened from ('192.168.x.x', <port>)` |
| M1.4 | 按住 BOOT，说「打开客厅的灯」，松开 | 串口：`recording…` → `…sent`。中枢日志显示有 PCM 字节进来（数量 > 0）。看板更新识别文本并切换灯状态。 |
| M1.5 | 短按 BOOT 但不说话 | 串口记录两个事件；中枢收到一小段音频；ASR 返回空或近空，回复为 `我没听清，请再说一遍。` |
| M1.6 | 把 ESP32 挪到另一个房间（仍在 WiFi 覆盖内） | 语音仍可用；从松开按钮到看板更新的延迟低于 3 秒 |

### 故障注入

| # | 注入 | 预期行为 |
|---|---|---|
| M1.F1 | 录音中途拔掉中枢 PC 的电 | ESP32 打印 `ws disconnected`，状态灯转红，每 2 秒重试，直到中枢回来 |
| M1.F2 | config.h 里 HUB_HOST 写错 | 串口反复打印 `ws disconnected` 错误；不崩溃；刷入正确值后恢复 |
| M1.F3 | 把 INMP441 的 L/R 接到 VDD | 音频帧能到达但全是静音；ASR 持续返回空——这是接线接反的诊断信号 |
| M1.F4 | 5 秒内按 BOOT 10 次 | 每次按下都开启一个新会话；不会卡在 `recording` 状态；中枢日志显示每个会话都干净地开启与关闭 |

### M1 通过标准

所有 M1.1–M1.6 通过；往返延迟稳定低于 3 秒；F1–F4 表现符合预期。此时你已拥有一个
能用的无线麦克风。

---

## M2 —— 路由器自愈闭环

**目标**：当网络断掉时，系统（用语音）询问要不要重启路由器；当用户语音回答
「好的」/「重启」时，SSH 登录并重启路由器。

### 前置条件

```
- [ ] M1 全绿
- [ ] 路由器运行 OpenWrt（或兼容系统）并已开启 SSH
- [ ] .env：ROUTER_PROVIDER=openwrt, ROUTER_HOST=<路由器局域网 IP>, ROUTER_USER=root, ROUTER_KEY_PATH=<id_ed25519 路径>
- [ ] 在你的笔记本上 `ssh -i <key> root@<router> echo ok` 返回 `ok`
- [ ] 中枢 PC 走有线连接，或者你已想清楚 WiFi 断掉时它如何存活（否则中枢会随网络一起消失）
```

### 用例

| # | 操作 | 可观测现象 |
|---|---|---|
| M2.1 | `curl -X POST <HUB>/api/text -d '{"text":"重启路由器"}'` | 中枢日志 `Rebooting router via SSH`。路由器真的重启（指示灯循环）。回复：`路由器已收到重启指令：...` |
| M2.2 | 路由器重启过程中 `curl <HUB>/api/network` | `online: false`，`consecutive_failures` 上升 |
| M2.3 | 路由器重新启动后 | 网络监控翻回 `online: true`，服务端日志输出 `Network recovered via ...` |
| M2.4 | `curl -X POST <HUB>/api/text -d '{"text":"重启 WiFi"}'` | 路由器上执行 `wifi reload`；WiFi 客户端重新关联；不整机重启 |

### 故障注入（这才是 M2 的重点）

| # | 注入 | 预期行为 |
|---|---|---|
| M2.F1 | 拔掉路由器 WAN 网线 | 在 `SELFHEAL_FAILURE_THRESHOLD` 次失败 ping 后（默认 3 × 30s = 90s）监控调用 `on_outage`。开启确认时，系统语音播报「网络不通，要不要重启路由器？」——*语音确认流程位于编排器钩子里；若你还没接好，日志那行就是可观测信号。* |
| M2.F2 | 在你说「好」之前把 WAN 网线插回 | 监控回到 `online`；断网询问被取消；不触发重启 |
| M2.F3 | SSH 私钥路径写错 | 首次重启尝试报错 `Router SSH needs either ROUTER_KEY_PATH or ROUTER_PASSWORD`；服务不挂；**不**回退到 mock（回退会掩盖 bug） |
| M2.F4 | 路由器不可达（已断电） | `router_ctrl.health_check()` 返回 False；重启工具返回错误而不是卡死 |

### M2 通过标准

M2.1–M2.4 通过；F1 产生断网通知（即便语音流程暂时只有文本）；F2/F3/F4 安全失败，
不把系统留在未定义状态。

---

## M2 之后

以下是「锦上添花」项，不属于上面的测试计划：

- 用 ESP-SR 唤醒词替换「按住说话」，让 ESP32 能环境监听。
- 把设备状态与审计日志持久化到 SQLite。
- 补上覆盖编排器、网络监控状态机、适配器工厂的自动化 pytest 用例。
- 加一个集成测试：用 mock 服务商启动 FastAPI 应用，并把一段固定 WAV 经 WebSocket 回放。

在那之前，本文档就是「能用」的定义契约。
