"""适配器工厂。

每个 build_* 函数根据 .env 里的 *_PROVIDER 配置，在启动时挑选一个具体实现返回。
其余代码只依赖这里导出的抽象基类，永远不直接 import 某个具体厂商的实现——
这样换厂商（或切到 mock）只需改一个环境变量。

具体实现都采用「按需 import」：只有真正用到某个厂商时才导入其 SDK，
避免为未使用的依赖付出导入开销、也方便缺少某个 SDK 时仍能跑 mock。
"""
from server.adapters.asr_base import ASRClient
from server.adapters.device_base import DeviceController
from server.adapters.llm_base import LLMClient, ToolCall
from server.adapters.router_base import RouterController
from server.adapters.tts_base import TTSClient
from server.config import settings


def build_asr() -> ASRClient:
    # ASR_PROVIDER=aliyun → 阿里云一句话识别；其余（含 mock）→ 固定文本
    if settings.asr_provider == "aliyun":
        from server.adapters.asr_aliyun import AliyunShortASR
        return AliyunShortASR()
    from server.adapters.asr_mock import MockASR
    return MockASR()


def build_llm() -> LLMClient:
    # LLM_PROVIDER=xfyun → 讯飞 MaaS；其余（含 mock）→ 正则规则匹配
    if settings.llm_provider == "xfyun":
        from server.adapters.llm_xfyun import XfyunMaaSLLM
        return XfyunMaaSLLM()
    from server.adapters.llm_mock import MockLLM
    return MockLLM()


def build_tts() -> TTSClient:
    # 目前只有 Edge 一种实现，故两个分支都返回 EdgeTTS（暂无独立的 mock TTS）
    if settings.tts_provider == "edge":
        from server.adapters.tts_edge import EdgeTTS
        return EdgeTTS()
    from server.adapters.tts_edge import EdgeTTS
    return EdgeTTS()


def build_router() -> RouterController:
    # ROUTER_PROVIDER=openwrt → 真实 SSH 控制；其余（含 mock）→ 仅打日志
    if settings.router_provider == "openwrt":
        from server.adapters.router_openwrt import OpenWRTRouter
        return OpenWRTRouter()
    from server.adapters.router_mock import MockRouter
    return MockRouter()


def build_devices() -> DeviceController:
    # 设备目前只有内存版模拟实现
    from server.adapters.device_mock import MockDeviceFleet
    return MockDeviceFleet()


__all__ = [
    "ASRClient",
    "DeviceController",
    "LLMClient",
    "RouterController",
    "TTSClient",
    "ToolCall",
    "build_asr",
    "build_devices",
    "build_llm",
    "build_router",
    "build_tts",
]
