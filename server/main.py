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


STATIC_DIR = PROJECT_ROOT / "server" / "web" / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    logger.info(
        "Starting service: asr={} llm={} tts={} router={}",
        settings.asr_provider,
        settings.llm_provider,
        settings.tts_provider,
        settings.router_provider,
    )

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

    async def on_outage(snap: HealthSnapshot) -> None:
        logger.warning(
            "Network outage detected (failures={}). Self-heal would prompt user.",
            snap.consecutive_failures,
        )

    async def on_recovery(snap: HealthSnapshot) -> None:
        logger.info("Network recovered via {}", snap.last_target_ok)

    monitor = NetworkMonitor(on_outage=on_outage, on_recovery=on_recovery)
    app.state.network_monitor = monitor
    await monitor.start()

    try:
        yield
    finally:
        await monitor.stop()
        logger.info("Service stopped")


def create_app() -> FastAPI:
    app = FastAPI(title="voice-router-agent", lifespan=lifespan)
    app.include_router(api_router)
    if STATIC_DIR.exists():
        app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
    return app


app = create_app()


def main() -> None:
    uvicorn.run(
        "server.main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
        reload=False,
    )


if __name__ == "__main__":
    main()
