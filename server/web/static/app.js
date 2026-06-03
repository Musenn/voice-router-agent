const els = {
  talkBtn: document.getElementById("talk-btn"),
  transcript: document.getElementById("transcript"),
  reply: document.getElementById("reply"),
  ttsPlayer: document.getElementById("tts-player"),
  deviceList: document.getElementById("device-list"),
  netDot: document.getElementById("net-dot"),
  netText: document.getElementById("net-text"),
  textForm: document.getElementById("text-form"),
  textInput: document.getElementById("text-input"),
};

let ws = null;
let audioCtx = null;
let mediaStream = null;
let workletNode = null;
let recording = false;
let pcmChunks = [];

function wsUrl() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${location.host}/ws/audio`;
}

function ensureSocket() {
  if (ws && ws.readyState <= 1) return ws;
  ws = new WebSocket(wsUrl());
  ws.binaryType = "arraybuffer";
  ws.onmessage = onWsMessage;
  ws.onclose = () => { ws = null; };
  ws.onerror = (e) => console.warn("ws error", e);
  return ws;
}

function onWsMessage(ev) {
  if (typeof ev.data === "string") {
    const msg = JSON.parse(ev.data);
    if (msg.event === "transcript") els.transcript.textContent = msg.text || "—";
    else if (msg.event === "reply") {
      els.reply.textContent = msg.text || "—";
      refreshDevices();
      refreshNetwork();
    } else if (msg.event === "error") {
      els.reply.textContent = "出错了：" + msg.message;
    }
    return;
  }
  // binary frame = mp3 tts
  const blob = new Blob([ev.data], { type: "audio/mpeg" });
  els.ttsPlayer.src = URL.createObjectURL(blob);
  els.ttsPlayer.hidden = false;
  els.ttsPlayer.play().catch(() => {});
}

async function startRecording() {
  if (recording) return;
  recording = true;
  els.talkBtn.classList.add("recording");
  els.talkBtn.textContent = "松开发送";

  mediaStream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1 } });
  audioCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
  const source = audioCtx.createMediaStreamSource(mediaStream);

  const workletCode = `
    class PCM16Capture extends AudioWorkletProcessor {
      process(inputs) {
        const ch = inputs[0][0];
        if (!ch) return true;
        const out = new Int16Array(ch.length);
        for (let i = 0; i < ch.length; i++) {
          const s = Math.max(-1, Math.min(1, ch[i]));
          out[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
        }
        this.port.postMessage(out.buffer, [out.buffer]);
        return true;
      }
    }
    registerProcessor("pcm16-capture", PCM16Capture);
  `;
  const blobUrl = URL.createObjectURL(new Blob([workletCode], { type: "text/javascript" }));
  await audioCtx.audioWorklet.addModule(blobUrl);

  workletNode = new AudioWorkletNode(audioCtx, "pcm16-capture");
  workletNode.port.onmessage = (e) => pcmChunks.push(new Uint8Array(e.data));
  source.connect(workletNode);

  ensureSocket();
  const send = () => {
    ws.send(JSON.stringify({
      event: "start",
      sample_rate: audioCtx.sampleRate,
      format: "pcm_s16le",
    }));
  };
  if (ws.readyState === 1) send();
  else ws.addEventListener("open", send, { once: true });
  pcmChunks = [];
}

async function stopRecording() {
  if (!recording) return;
  recording = false;
  els.talkBtn.classList.remove("recording");
  els.talkBtn.textContent = "按住说话";

  if (workletNode) workletNode.disconnect();
  if (audioCtx) await audioCtx.close().catch(() => {});
  if (mediaStream) mediaStream.getTracks().forEach((t) => t.stop());

  if (!ws || ws.readyState !== 1) return;
  for (const chunk of pcmChunks) ws.send(chunk);
  ws.send(JSON.stringify({ event: "stop" }));
}

els.talkBtn.addEventListener("mousedown", startRecording);
els.talkBtn.addEventListener("mouseup", stopRecording);
els.talkBtn.addEventListener("mouseleave", stopRecording);
els.talkBtn.addEventListener("touchstart", (e) => { e.preventDefault(); startRecording(); });
els.talkBtn.addEventListener("touchend", (e) => { e.preventDefault(); stopRecording(); });

document.addEventListener("keydown", (e) => {
  if (e.key === "F2" && !e.repeat) { e.preventDefault(); startRecording(); }
});
document.addEventListener("keyup", (e) => {
  if (e.key === "F2") { e.preventDefault(); stopRecording(); }
});

els.textForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = els.textInput.value.trim();
  if (!text) return;
  els.textInput.value = "";
  const resp = await fetch("/api/text", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  const data = await resp.json();
  els.transcript.textContent = data.transcript || "—";
  els.reply.textContent = data.reply || "—";
  refreshDevices();
});

async function refreshDevices() {
  const resp = await fetch("/api/devices");
  const devices = await resp.json();
  els.deviceList.innerHTML = devices.map((d) => {
    const stateClass = d.state === "on" || d.state === "open" ? "state-on" : "state-off";
    const meta = [];
    if (d.brightness !== undefined) meta.push(`亮度 ${d.brightness}`);
    if (d.temperature !== undefined) meta.push(`${d.temperature}°C`);
    if (d.mode) meta.push(d.mode);
    return `
      <li>
        <span class="device-name">${d.name}</span>
        <span class="device-meta">
          <span class="${stateClass}">${d.state}</span>
          ${meta.length ? " · " + meta.join(" · ") : ""}
        </span>
      </li>`;
  }).join("");
}

async function refreshNetwork() {
  try {
    const resp = await fetch("/api/network");
    const data = await resp.json();
    els.netDot.classList.toggle("ok", data.online);
    els.netDot.classList.toggle("bad", !data.online);
    els.netText.textContent = data.online
      ? `在线 (via ${data.last_target_ok ?? "-"})`
      : `离线 (连续失败 ${data.consecutive_failures} 次)`;
  } catch {
    els.netText.textContent = "无法获取网络状态";
  }
}

refreshDevices();
refreshNetwork();
setInterval(refreshNetwork, 10000);
