from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    host: str = "127.0.0.1"
    port: int = 28080
    log_level: str = "INFO"

    asr_provider: Literal["aliyun", "mock"] = "mock"
    aliyun_ak_id: str = ""
    aliyun_ak_secret: str = ""
    aliyun_nls_appkey: str = ""
    aliyun_nls_region: str = "cn-shanghai"

    llm_provider: Literal["xfyun", "mock"] = "mock"
    xfyun_base_url: str = "https://maas-api.cn-huabei-1.xf-yun.com/v2"
    xfyun_api_key: str = ""
    xfyun_api_secret: str = ""
    xfyun_model_id: str = ""
    xfyun_resource_id: str = "0"

    tts_provider: Literal["edge", "mock"] = "edge"
    edge_tts_voice: str = "zh-CN-XiaoxiaoNeural"

    router_provider: Literal["mock", "openwrt"] = "mock"
    router_host: str = "192.168.1.1"
    router_port: int = 22
    router_user: str = "root"
    router_password: str = ""
    router_key_path: str = ""

    selfheal_ping_targets: str = "8.8.8.8,114.114.114.114"
    selfheal_interval_seconds: int = 30
    selfheal_failure_threshold: int = 3
    selfheal_require_confirmation: bool = True

    @property
    def ping_targets(self) -> list[str]:
        return [t.strip() for t in self.selfheal_ping_targets.split(",") if t.strip()]


settings = Settings()
