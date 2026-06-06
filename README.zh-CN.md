# voice-router-agent（语音路由智能体）

> 中文 · [English](README.md)

一个小型的语音控制中枢，用来管家庭网络和几台「模拟」的智能家电。对它说一句话，
音频会先被云端语音识别（ASR）转写成文字，大模型（LLM）据此决定调用哪个工具，
工具执行后再由语音合成（TTS）把结果念出来。

它还会盯着家里的路由器：当网络中断时，可以（用语音）问你要不要重启路由器，
得到确认后通过 SSH 登录并重启它。

## 项目定位

这是一个个人学习项目。请把代码当作一个**能跑通的原型**，而不是一套可以直接搬进
别人家、经过安全加固的成品。

- [x] 项目骨架、适配器接口、模拟（mock）实现
- [x] FastAPI 服务、Web 看板、WebSocket 音频通道
- [x] 基于 LLM 工具调用（function calling）的意图编排
- [x] 自愈守护进程（ping 监测 + 语音确认流程）
- [x] ESP32-S3 固件示例（通过 WebSocket 实现「按住说话」）
- [ ] 单元测试 —— 待在真实硬件上首次端到端跑通后补充
- [ ] 唤醒词集成（目前用按键代替）

## 目录结构

```
server/        运行在家庭 PC 上的 Python 服务
  adapters/    ASR / LLM / TTS / 路由器 / 设备 各类适配器（mock + 真实）
  intent/      LLM 工具调用编排
  selfheal/    网络监控与恢复流程
  transport/   WebSocket 音频端点
  audio/       本机麦克风采集（M0 阶段兜底）
  web/         FastAPI 路由 + 静态看板页面
firmware/      ESP32-S3 固件（PlatformIO），即无线麦克风节点
scripts/       辅助启动脚本与一个手动音频测试
docs/          架构说明等文档
```

## 快速开始（M0：用笔记本麦克风）

```powershell
# 请先激活你的 Python 环境（建议用 conda 新建一个独立环境）
pip install -e .
copy .env.example .env
# 在 .env 中填入各服务商的凭据
python -m server.main
```

打开 <http://localhost:28080>。在看板里按住 <kbd>F2</kbd> 开始录音，松开结束。
或者运行 `python scripts/mic_test.py`，把一段录音推过整条管线。

> 想完全离线、零云端账号跑通？把 `.env` 里的 `ASR_PROVIDER`、`LLM_PROVIDER`、
> `ROUTER_PROVIDER` 都设为 `mock` 即可——此时识别结果是固定文本、由正则规则
> 匹配工具、路由器操作只打日志。

## 整体流程

```
说话（按住按钮）
   │  原始 PCM 音频
   ▼
ASR 适配器  ──► 识别文本
   │
   ▼
意图编排器 IntentOrchestrator
   │  把文本 + 工具清单交给 LLM
   ▼
LLM 适配器  ──► 文本回复 和/或 工具调用
   │
   ├─► set_device_state / list_devices  → 改设备状态（内存）
   └─► router_reboot / router_restart_wifi → SSH 控制路由器
   │
   ▼
TTS 适配器  ──► MP3 语音 ──► 回传客户端播放
```

另有一个独立的 `NetworkMonitor` 任务，每隔 N 秒 ping 公网主机；连续失败达到阈值后
触发恢复钩子（M2 里该钩子会走 TTS 语音确认，确认后再 SSH 重启路由器）。

## 配置

所有凭据都放在 `.env`，**切勿提交到仓库**。`.env.example` 列出了全部变量及各值的
获取位置。主要分组：

| 分组 | 关键变量 | 说明 |
|------|----------|------|
| 服务 | `HOST` / `PORT` / `LOG_LEVEL` | 默认只绑定 `127.0.0.1`，未加鉴权前不要暴露到局域网 |
| ASR | `ASR_PROVIDER` + 阿里云密钥 | `aliyun` 走阿里云一句话识别，`mock` 返回固定文本 |
| LLM | `LLM_PROVIDER` + 讯飞密钥 | `xfyun` 走讯飞 MaaS，`mock` 用正则规则匹配 |
| TTS | `TTS_PROVIDER` / `EDGE_TTS_VOICE` | `edge` 用微软 Edge 在线合成，免费无需密钥 |
| 路由器 | `ROUTER_PROVIDER` + SSH 配置 | `openwrt` 真实 SSH 控制，`mock` 仅打日志 |
| 自愈 | `SELFHEAL_*` | ping 目标、间隔、失败阈值、是否需语音确认 |

## 为什么到处都是「适配器」

每个外部依赖都藏在一个只有一两个方法的基类后面。`server/adapters/__init__.py` 里的
工厂会在启动时根据环境变量挑选具体实现，其余代码永远不直接 import 某个具体服务商。
这让三件事变得很便宜：

- **换服务商**：只需新增一个适配器并切换 `ASR_PROVIDER=...` 之类的变量。
- **离线测试**：`mock_*` 适配器返回预置数据，无需联网。
- **空跑硬件**：`MockRouter` 只把它「本应执行」的 SSH 命令打到日志。

## 里程碑

同一套代码支持三种部署形态，里程碑之间**无需改动代码结构**，只改 `.env` 和你接入的硬件：

| 里程碑 | 边缘麦克风 | 服务商配置 | 真实路由器？ |
|--------|-----------|-----------|-------------|
| M0 | 浏览器 / 笔记本 | mock 或真实（自选） | mock |
| M1 | ESP32-S3 + INMP441 | 真实云端 | mock |
| M2 | ESP32-S3 + INMP441 | 真实云端 | OpenWrt SSH |

## 刻意没做的事

- **多轮对话记忆**：每次请求都独立，模型成本低、调试简单。
- **数据库**：设备状态只存内存，重启即重置。真有持久化需求时再加 SQLite。
- **鉴权**：服务默认绑定 `127.0.0.1`，加上鉴权前别暴露到局域网。
- **服务端唤醒词**：浏览器和 ESP32 都用「按住说话」。整条管线稳定后再接
  ESP-SR 或 openWakeWord。

## 文档

- [架构说明](docs/architecture.zh-CN.md) —— 各部分如何拼装到一起。
- [硬件采购清单](docs/hardware-shopping-list.zh-CN.md) —— ESP32 麦克风节点与可选
  OpenWrt 路由器的物料清单、购买渠道与避坑要点。
- [测试计划](docs/testing-plan.zh-CN.md) —— M0 / M1 / M2 的手动测试手册，含故障注入用例。
- [固件说明](firmware/README.zh-CN.md) —— ESP32-S3 麦克风节点固件。

## 许可

个人使用，不提供任何担保。
