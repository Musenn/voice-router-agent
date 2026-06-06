from fastapi import APIRouter, HTTPException, Request, WebSocket

from server.transport.ws_audio import run_audio_session


router = APIRouter()


@router.get("/health")
async def health() -> dict:
    # 存活探针：供监控/启动检查使用
    return {"status": "ok"}


@router.get("/api/devices")
async def list_devices(request: Request) -> list[dict]:
    # 返回所有设备状态，供看板渲染
    return request.app.state.devices.list_devices()


@router.post("/api/devices/{device_id}/state")
async def set_device_state(device_id: str, request: Request) -> dict:
    # 直接改某个设备状态（绕过语音/LLM，便于调试）
    body = await request.json()
    try:
        return request.app.state.devices.set_state(device_id, **body)
    except KeyError:
        # 设备不存在 → 404；from None 隐去无意义的 KeyError 链
        raise HTTPException(status_code=404, detail="unknown device") from None


@router.get("/api/network")
async def network_status(request: Request) -> dict:
    # 返回网络监控的当前快照
    snap = request.app.state.network_monitor.snapshot
    return {
        "online": snap.online,
        "consecutive_failures": snap.consecutive_failures,
        "last_target_ok": snap.last_target_ok,
        "in_recovery": snap.in_recovery,
    }


@router.post("/api/text")
async def text_command(request: Request) -> dict:
    """纯文本入口：不接麦克风也能测试整条管线（直接给文字，跳过 ASR）。"""
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
    # WebSocket 音频入口：把连接交给会话处理器，注入已装配好的适配器
    app = websocket.app
    await run_audio_session(
        websocket,
        asr=app.state.asr,
        tts=app.state.tts,
        orchestrator=app.state.orchestrator,
    )
