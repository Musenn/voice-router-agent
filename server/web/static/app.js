// 看板用到的所有 DOM 元素，集中缓存
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

let ws = null;          // WebSocket 连接
let audioCtx = null;    // Web Audio 上下文
let mediaStream = null; // 麦克风媒体流
let workletNode = null; // 把音频降采样为 PCM16 的 AudioWorklet 节点
let recording = false;  // 是否正在录音
let pcmChunks = [];      // 录音期间累积的 PCM 分片

// 根据当前页面协议推导 WebSocket 地址（https → wss）
function wsUrl() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${location.host}/ws/audio`;
}

// 确保有一个可用的 WebSocket 连接（已连接则复用）
function ensureSocket() {
  if (ws && ws.readyState <= 1) return ws;
  ws = new WebSocket(wsUrl());
  ws.binaryType = "arraybuffer";
  ws.onmessage = onWsMessage;
  ws.onclose = () => { ws = null; };
  ws.onerror = (e) => console.warn("ws error", e);
  return ws;
}

// 处理服务端推送的消息
function onWsMessage(ev) {
  if (typeof ev.data === "string") {
    // 文本帧 = JSON 控制/结果消息
    const msg = JSON.parse(ev.data);
    if (msg.event === "transcript") els.transcript.textContent = msg.text || "—";
    else if (msg.event === "reply") {
      // 回复到达：刷新设备与网络状态
      els.reply.textContent = msg.text || "—";
      refreshDevices();
      refreshNetwork();
    } else if (msg.event === "error") {
      els.reply.textContent = "出错了：" + msg.message;
    }
    return;
  }
  // 二进制帧 = TTS 合成的 MP3，转成 Blob 后播放
  const blob = new Blob([ev.data], { type: "audio/mpeg" });
  els.ttsPlayer.src = URL.createObjectURL(blob);
  els.ttsPlayer.hidden = false;
  els.ttsPlayer.play().catch(() => {});
}

// 开始录音：拿麦克风 → 建 16kHz 音频上下文 → 用 AudioWorklet 实时转 PCM16
async function startRecording() {
  if (recording) return;
  recording = true;
  els.talkBtn.classList.add("recording");
  els.talkBtn.textContent = "松开发送";

  mediaStream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1 } });
  audioCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
  const source = audioCtx.createMediaStreamSource(mediaStream);

  // AudioWorklet 处理器：把 [-1,1] 的浮点采样转成 16 位整型 PCM，回传到主线程
  const workletCode = `
    class PCM16Capture extends AudioWorkletProcessor {
      process(inputs) {
        const ch = inputs[0][0];
        if (!ch) return true;
        const out = new Int16Array(ch.length);
        for (let i = 0; i < ch.length; i++) {
          const s = Math.max(-1, Math.min(1, ch[i]));  // 钳位到 [-1,1]
          out[i] = s < 0 ? s * 0x8000 : s * 0x7fff;     // 映射到 int16 范围
        }
        this.port.postMessage(out.buffer, [out.buffer]); // 转移所有权，零拷贝回传
        return true;
      }
    }
    registerProcessor("pcm16-capture", PCM16Capture);
  `;
  // 把内联的 worklet 代码包成 Blob URL 再加载
  const blobUrl = URL.createObjectURL(new Blob([workletCode], { type: "text/javascript" }));
  await audioCtx.audioWorklet.addModule(blobUrl);

  workletNode = new AudioWorkletNode(audioCtx, "pcm16-capture");
  workletNode.port.onmessage = (e) => pcmChunks.push(new Uint8Array(e.data));
  source.connect(workletNode);

  // 发 start 事件告知服务端开始一轮（连接未就绪则等 open 再发）
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

// 停止录音：清理音频资源，把累积的 PCM 全部发出去，再发 stop
async function stopRecording() {
  if (!recording) return;
  recording = false;
  els.talkBtn.classList.remove("recording");
  els.talkBtn.textContent = "按住说话";

  // 释放音频管线与麦克风
  if (workletNode) workletNode.disconnect();
  if (audioCtx) await audioCtx.close().catch(() => {});
  if (mediaStream) mediaStream.getTracks().forEach((t) => t.stop());

  if (!ws || ws.readyState !== 1) return;
  for (const chunk of pcmChunks) ws.send(chunk);  // 逐块发送二进制 PCM
  ws.send(JSON.stringify({ event: "stop" }));      // 通知服务端开始处理
}

// 按住按钮说话、松开发送（同时支持鼠标与触屏）
els.talkBtn.addEventListener("mousedown", startRecording);
els.talkBtn.addEventListener("mouseup", stopRecording);
els.talkBtn.addEventListener("mouseleave", stopRecording);  // 指针移出也算松开，防卡死在录音态
els.talkBtn.addEventListener("touchstart", (e) => { e.preventDefault(); startRecording(); });
els.talkBtn.addEventListener("touchend", (e) => { e.preventDefault(); stopRecording(); });

// 快捷键：按住 F2 说话，松开发送（!e.repeat 防长按重复触发）
document.addEventListener("keydown", (e) => {
  if (e.key === "F2" && !e.repeat) { e.preventDefault(); startRecording(); }
});
document.addEventListener("keyup", (e) => {
  if (e.key === "F2") { e.preventDefault(); stopRecording(); }
});

// 文本调试表单：直接走 /api/text，不经麦克风
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

// 拉取并渲染设备列表
async function refreshDevices() {
  const resp = await fetch("/api/devices");
  const devices = await resp.json();
  els.deviceList.innerHTML = devices.map((d) => {
    // 开/开启状态用绿色，其余用灰色
    const stateClass = d.state === "on" || d.state === "open" ? "state-on" : "state-off";
    // 按设备类型拼接附加信息（亮度/温度/模式）
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

// 拉取并渲染网络状态（顶部指示灯 + 文字）
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

// 页面加载后先刷新一次，并每 10 秒轮询一次网络状态
refreshDevices();
refreshNetwork();
setInterval(refreshNetwork, 10000);
