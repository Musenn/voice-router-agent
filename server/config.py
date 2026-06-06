"""全局配置。

所有配置项都从项目根目录的 .env 文件读取（找不到则用这里的默认值）。
字段名大小写不敏感，例如 .env 里的 ASR_PROVIDER 对应下面的 asr_provider。
凭据类配置一律放在 .env，切勿提交进仓库。
"""
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# 项目根目录：本文件位于 server/ 下，向上两级即仓库根
PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",          # 忽略 .env 中多余的未知变量
        case_sensitive=False,    # 变量名大小写不敏感
    )

    # --- 服务监听 ---
    host: str = "127.0.0.1"      # 默认只绑定本机，未加鉴权前不要暴露到局域网
    port: int = 28080
    log_level: str = "INFO"

    # --- ASR：语音识别厂商 ---
    asr_provider: Literal["aliyun", "mock"] = "mock"
    aliyun_ak_id: str = ""               # 阿里云 AccessKey ID
    aliyun_ak_secret: str = ""           # 阿里云 AccessKey Secret
    aliyun_nls_appkey: str = ""          # 智能语音交互项目 AppKey
    aliyun_nls_region: str = "cn-shanghai"  # 地域，默认上海

    # --- LLM：大模型厂商 ---
    llm_provider: Literal["xfyun", "mock"] = "mock"
    xfyun_base_url: str = "https://maas-api.cn-huabei-1.xf-yun.com/v2"
    xfyun_api_key: str = ""
    xfyun_api_secret: str = ""
    xfyun_model_id: str = ""             # MaaS 控制台上的模型 ID
    xfyun_resource_id: str = "0"

    # --- TTS：语音合成厂商 ---
    tts_provider: Literal["edge", "mock"] = "edge"
    edge_tts_voice: str = "zh-CN-XiaoxiaoNeural"  # Edge TTS 音色

    # --- 路由器控制 ---
    router_provider: Literal["mock", "openwrt"] = "mock"
    router_host: str = "192.168.1.1"
    router_port: int = 22
    router_user: str = "root"
    router_password: str = ""            # 密码与私钥二选一，优先用私钥
    router_key_path: str = ""

    # --- 网络自愈 ---
    selfheal_ping_targets: str = "8.8.8.8,114.114.114.114"  # 逗号分隔的探测目标
    selfheal_interval_seconds: int = 30  # 探测间隔（秒）
    selfheal_failure_threshold: int = 3  # 连续失败多少次判定为断网
    selfheal_require_confirmation: bool = True  # 执行不可逆操作前是否需语音确认

    @property
    def ping_targets(self) -> list[str]:
        # 把逗号分隔的字符串拆成去空白、去空项的列表
        return [t.strip() for t in self.selfheal_ping_targets.split(",") if t.strip()]


settings = Settings()
