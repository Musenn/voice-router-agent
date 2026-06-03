from fastapi import APIRouter, HTTPException, Request, WebSocket

from server.transport.ws_audio import run_audio_session


router = APIRouter()


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.get("/api/devices")
async def list_devices(request: Request) -> list[dict]:
    return request.app.state.devices.list_devices()


@router.post("/api/devices/{device_id}/state")
async def set_device_state(device_id: str, request: Request) -> dict:
    body = await request.json()
    try:
        return request.app.state.devices.set_state(device_id, **body)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown device") from None


@router.get("/api/network")
async def network_status(request: Request) -> dict:
    snap = request.app.state.network_monitor.snapshot
    return {
        "online": snap.online,
        "consecutive_failures": snap.consecutive_failures,
        "last_target_ok": snap.last_target_ok,
        "in_recovery": snap.in_recovery,
    }


@router.post("/api/text")
async def text_command(request: Request) -> dict:
    """Text-only entry point. Lets you test the whole pipeline without a mic."""
    body = await request.json()
    text = (body.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="empty text")
    result = await request.app.state.orchestrator.handle_text(text)
    return {
        "transcript": result.transcript,
        "reply": result.reply_text,
        "actions": result.actions,
    }


@router.websocket("/ws/audio")
async def ws_audio(websocket: WebSocket) -> None:
    app = websocket.app
    await run_audio_session(
        websocket,
        asr=app.state.asr,
        tts=app.state.tts,
        orchestrator=app.state.orchestrator,
    )
