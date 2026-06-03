from server.adapters.asr_base import ASRClient
from server.adapters.device_base import DeviceController
from server.adapters.llm_base import LLMClient, ToolCall
from server.adapters.router_base import RouterController
from server.adapters.tts_base import TTSClient
from server.config import settings


def build_asr() -> ASRClient:
    if settings.asr_provider == "aliyun":
        from server.adapters.asr_aliyun import AliyunShortASR
        return AliyunShortASR()
    from server.adapters.asr_mock import MockASR
    return MockASR()


def build_llm() -> LLMClient:
    if settings.llm_provider == "xfyun":
        from server.adapters.llm_xfyun import XfyunMaaSLLM
        return XfyunMaaSLLM()
    from server.adapters.llm_mock import MockLLM
    return MockLLM()


def build_tts() -> TTSClient:
    if settings.tts_provider == "edge":
        from server.adapters.tts_edge import EdgeTTS
        return EdgeTTS()
    from server.adapters.tts_edge import EdgeTTS
    return EdgeTTS()


def build_router() -> RouterController:
    if settings.router_provider == "openwrt":
        from server.adapters.router_openwrt import OpenWRTRouter
        return OpenWRTRouter()
    from server.adapters.router_mock import MockRouter
    return MockRouter()


def build_devices() -> DeviceController:
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
