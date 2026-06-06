from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from loguru import logger

from server.adapters import build_asr, build_devices, build_llm, build_router, build_tts
from server.config import PROJECT_ROOT, settings
from server.intent.orchestrator import IntentOrchestrator
from server.logging_setup import configure_logging
from server.selfheal.network_monitor import HealthSnapshot, NetworkMonitor
from server.web.routes import router as api_router


# 前端静态资源目录（看板页面）
STATIC_DIR = PROJECT_ROOT / "server" / "web" / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时装配各适配器与后台任务，关闭时优雅停止。

    FastAPI 在服务启动/退出时分别执行 yield 之前/之后的代码。
    """
    configure_logging()
    logger.info(
        "Starting service: asr={} llm={} tts={} router={}",
        settings.asr_provider,
        settings.llm_provider,
        settings.tts_provider,
        settings.router_provider,
    )

    # 根据 .env 配置装配各路适配器，挂到 app.state 上供请求处理时取用
    app.state.asr = build_asr()
    app.state.llm = build_llm()
    app.state.tts = build_tts()
    app.state.router_ctrl = build_router()
    app.state.devices = build_devices()
    app.state.orchestrator = IntentOrchestrator(
        llm=app.state.llm,
        devices=app.state.devices,
        router=app.state.router_ctrl,
    )

    # 断网回调：连续失败达到阈值时触发（M2 里会在此发起语音确认并重启路由器）
    async def on_outage(snap: HealthSnapshot) -> None:
        logger.warning(
            "Network outage detected (failures={}). Self-heal would prompt user.",
            snap.consecutive_failures,
        )

    # 恢复回调：网络重新连通时触发
    async def on_recovery(snap: HealthSnapshot) -> None:
        logger.info("Network recovered via {}", snap.last_target_ok)

    # 启动后台网络监控任务
    monitor = NetworkMonitor(on_outage=on_outage, on_recovery=on_recovery)
    app.state.network_monitor = monitor
    await monitor.start()

    try:
        yield  # ← 服务运行期间停在这里
    finally:
        # 退出时停掉后台任务
        await monitor.stop()
        logger.info("Service stopped")


def create_app() -> FastAPI:
    # 组装 FastAPI 应用：先挂 API 路由，再把静态看板挂到根路径
    app = FastAPI(title="voice-router-agent", lifespan=lifespan)
    app.include_router(api_router)
    if STATIC_DIR.exists():
        # html=True：访问 / 时自动返回 index.html
        app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
    return app


app = create_app()


def main() -> None:
    # 命令行入口：python -m server.main
    uvicorn.run(
        "server.main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
        reload=False,
    )


if __name__ == "__main__":
    main()
